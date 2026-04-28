import json
import logging
import os
import tempfile
import threading
import time

from django.contrib.auth.decorators import login_required
from django.db import close_old_connections, connections, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from accounts.models import CPPUser
from .models import AccuracyTestCase, AccuracyTestRun, DatabaseFile, QueryLog
from tools.gcs_storage import (
    upload_file as gcs_upload_file,
    upload_from_string as gcs_upload_from_string,
    delete_file as gcs_delete_file,
)
from tools.rag_files import (
    list_files as rag_list_files,
    import_files as rag_import_files,
    delete_file as rag_delete_file,
)
from tools.text_cleaner import clean_text
from tools.description_summary import summarize_for_description
from tools.source_text_extract import extract_text_from_upload

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.json'}


def allowed_visitor(user: CPPUser):
    return user.is_superuser


def allowed_developer_visitor(user: CPPUser):
    return user.is_superuser or user.is_developer


@login_required
def index(request):
    if not allowed_developer_visitor(request.user):
        return redirect('home.index')
    template_data = {}
    template_data['title'] = 'Developer Tools'
    return render(request, 'developer/index.html', {'template_data': template_data})


def _validate_file_extension(uploaded_file):
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, ext
    return True, ext


def _gcs_destination_from_name(name: str, ext: str) -> str:
    safe = slugify((name or '').strip()) or 'untitled'
    return f'rag_dataset/{safe}{ext}'


def _import_to_rag(gcs_uri, db_file):
    try:
        existing_names = {f.name for f in rag_list_files()}
        result = rag_import_files([gcs_uri])
        if result.imported_count > 0:
            current_files = rag_list_files()
            for f in current_files:
                if f.name not in existing_names:
                    db_file.rag_resource_name = f.name
                    db_file.save(update_fields=['rag_resource_name'])
                    break
    except Exception:
        logger.exception('RAG import failed for %s', gcs_uri)


def _background_rag_import(db_file_id: int, gcs_uri: str) -> None:
    close_old_connections()
    try:
        db_file = DatabaseFile.objects.get(pk=db_file_id)
        _import_to_rag(gcs_uri, db_file)
    except DatabaseFile.DoesNotExist:
        logger.warning(
            'Background RAG import skipped; DatabaseFile id=%s missing', db_file_id
        )
    except Exception:
        logger.exception('Background RAG import failed for id=%s', db_file_id)
    finally:
        connections.close_all()


def _schedule_rag_import(db_file: DatabaseFile, gcs_uri: str) -> None:
    def start_thread() -> None:
        threading.Thread(
            target=_background_rag_import,
            args=(db_file.pk, gcs_uri),
            name=f'rag-import-{db_file.pk}',
            daemon=True,
        ).start()

    transaction.on_commit(start_thread)


def _display_name_for_rag_file(rag_file) -> str:
    name = (getattr(rag_file, 'display_name', '') or '').strip()
    if name:
        return name
    resource = (getattr(rag_file, 'name', '') or '').strip()
    if resource:
        return resource.rsplit('/', 1)[-1]
    return '(unnamed corpus file)'


def _delete_from_rag_corpus(rag_resource_name: str) -> bool:
    resource = (rag_resource_name or '').strip()
    if not resource:
        return False
    try:
        rag_delete_file(resource)
        return True
    except Exception:
        logger.exception('RAG delete failed for %s', resource)
        return False


def _managed_file_rows() -> list[dict]:
    db_rows = list(
        DatabaseFile.objects.select_related('uploader').all().order_by('-date_added')
    )
    by_rag_name = {row.rag_resource_name: row for row in db_rows if row.rag_resource_name}

    merged: list[dict] = []
    seen_db_ids: set[int] = set()

    try:
        rag_files = rag_list_files()
    except Exception:
        logger.exception('Could not list RAG corpus files for manage-db page')
        rag_files = []

    for rag_file in rag_files:
        db_row = by_rag_name.get(rag_file.name)
        if db_row is not None:
            seen_db_ids.add(db_row.pk)
            merged.append(
                {
                    'pk': db_row.pk,
                    'name': db_row.name,
                    'description': db_row.description,
                    'source_type': db_row.source_type,
                    'source_type_display': db_row.get_source_type_display(),
                    'date_added': db_row.date_added,
                    'uploader': db_row.uploader,
                    'file_url': db_row.file.url if db_row.file else '',
                    'can_delete': True,
                    'placeholder': False,
                }
            )
            continue

        merged.append(
            {
                'pk': None,
                'name': _display_name_for_rag_file(rag_file),
                'description': 'No description (not in database table).',
                'source_type': 'file',
                'source_type_display': 'RAG Corpus Only',
                'date_added': None,
                'uploader': None,
                'file_url': '',
                'can_delete': True,
                'rag_resource_name': rag_file.name,
                'placeholder': True,
            }
        )

    for db_row in db_rows:
        if db_row.pk in seen_db_ids:
            continue
        merged.append(
            {
                'pk': db_row.pk,
                'name': db_row.name,
                'description': db_row.description,
                'source_type': db_row.source_type,
                'source_type_display': db_row.get_source_type_display(),
                'date_added': db_row.date_added,
                'uploader': db_row.uploader,
                'file_url': db_row.file.url if db_row.file else '',
                'can_delete': True,
                'rag_resource_name': db_row.rag_resource_name,
                'placeholder': False,
            }
        )

    return merged


def _split_required_terms(raw_terms: str) -> list[str]:
    if not raw_terms:
        return []
    pieces = raw_terms.replace('\r', '\n').replace(',', '\n').split('\n')
    return [piece.strip() for piece in pieces if piece.strip()]


def _run_accuracy_case(test_case: AccuracyTestCase) -> AccuracyTestRun:
    from home.views import _rag_documents_system_prompt_suffix
    from tools.prompt_router import build_chat_system_prompt_suffix
    from tools.vertex_chat import run_chat

    question = (test_case.question or '').strip()
    doc_index = _rag_documents_system_prompt_suffix()
    start = time.time()
    result = run_chat(
        question,
        system_prompt_suffix=build_chat_system_prompt_suffix(question, doc_index),
    )
    elapsed = int((time.time() - start) * 1000)

    reply = (result.get('reply') or '').strip()
    error = (result.get('error') or '').strip()
    terms = _split_required_terms(test_case.required_terms)
    missing_terms = []
    status = AccuracyTestRun.Status.REVIEW

    if error:
        status = AccuracyTestRun.Status.ERROR
    elif terms:
        reply_text = reply.casefold()
        missing_terms = [term for term in terms if term.casefold() not in reply_text]
        if missing_terms:
            status = AccuracyTestRun.Status.FAIL
        else:
            status = AccuracyTestRun.Status.PASS

    return AccuracyTestRun.objects.create(
        test_case=test_case,
        actual_answer=reply,
        error_message=error,
        missing_terms=', '.join(missing_terms),
        response_time_ms=elapsed,
        status=status,
    )


@login_required
def database_files(request):
    if not allowed_visitor(request.user):
        return redirect('home.index')

    error = None
    success = None

    if request.method == 'POST':
        subfield = request.POST.get('subfield', '')

        if subfield == 'file_add':
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            uploaded_file = request.FILES.get('file_upload')

            if not name:
                error = 'Name is required.'
            elif not description:
                error = (
                    'Description is required. It tells the model what this source is about '
                    'so answers stay accurate and on-topic.'
                )
            elif not uploaded_file:
                error = 'Please select a file to upload.'
            else:
                valid, ext = _validate_file_extension(uploaded_file)
                if not valid:
                    error = f'Unsupported file type "{ext}". Only PDF, TXT, and JSON files are allowed.'
                else:
                    db_file = DatabaseFile(
                        name=name,
                        description=description,
                        source_type=DatabaseFile.SOURCE_FILE,
                        uploader=request.user,
                    )
                    db_file.file = uploaded_file
                    db_file.save()

                    tmp_path = None
                    try:
                        with tempfile.NamedTemporaryFile(
                            delete=False, suffix=ext
                        ) as tmp:
                            for chunk in uploaded_file.chunks():
                                tmp.write(chunk)
                            tmp_path = tmp.name

                        gcs_uri = gcs_upload_file(
                            tmp_path,
                            destination_name=_gcs_destination_from_name(name, ext),
                        )
                        db_file.gcs_uri = gcs_uri
                        db_file.save(update_fields=['gcs_uri'])

                        _schedule_rag_import(db_file, gcs_uri)
                        success = (
                            f'File "{name}" saved to storage. '
                            'RAG indexing is running in the background and may take several minutes.'
                        )
                    except Exception as exc:
                        logger.exception('File upload failed')
                        db_file.delete()
                        error = f'Upload failed: {exc}'
                    finally:
                        if tmp_path and os.path.exists(tmp_path):
                            os.unlink(tmp_path)

        elif subfield == 'text_add':
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            raw_text = request.POST.get('raw_text', '').strip()

            if not name:
                error = 'Name is required.'
            elif not description:
                error = (
                    'Description is required. It tells the model what this source is about '
                    'so answers stay accurate and on-topic.'
                )
            elif not raw_text:
                error = 'Text content is required.'
            else:
                db_file = DatabaseFile(
                    name=name,
                    description=description,
                    source_type=DatabaseFile.SOURCE_TEXT,
                    uploader=request.user,
                )
                db_file.save()

                try:
                    dest_name = _gcs_destination_from_name(name, '.txt')
                    gcs_uri = gcs_upload_from_string(
                        raw_text.encode('utf-8'),
                        dest_name,
                        content_type='text/plain',
                    )
                    db_file.gcs_uri = gcs_uri
                    db_file.save(update_fields=['gcs_uri'])

                    _schedule_rag_import(db_file, gcs_uri)
                    success = (
                        f'Text source "{name}" saved. '
                        'RAG indexing is running in the background and may take several minutes.'
                    )
                except Exception as exc:
                    logger.exception('Text upload failed')
                    db_file.delete()
                    error = f'Upload failed: {exc}'

    template_data = {
        'title': 'Database',
        'files': _managed_file_rows(),
        'error': error,
        'success': success,
    }
    return render(request, 'developer/files.html', {'template_data': template_data})


@login_required
@require_POST
def delete_database_file(request, file_id):
    if not allowed_visitor(request.user):
        return redirect('home.index')

    try:
        db_file = DatabaseFile.objects.get(pk=file_id)
    except DatabaseFile.DoesNotExist:
        return redirect('developer.files')

    if db_file.rag_resource_name:
        _delete_from_rag_corpus(db_file.rag_resource_name)

    if db_file.gcs_uri:
        try:
            blob_name = db_file.gcs_uri.split('/', 3)[-1] if '/' in db_file.gcs_uri else ''
            if blob_name:
                gcs_delete_file(blob_name)
        except Exception:
            logger.exception('GCS delete failed for %s', db_file.gcs_uri)

    if db_file.file:
        try:
            db_file.file.delete(save=False)
        except Exception:
            logger.exception('Local file delete failed')

    db_file.delete()
    return redirect('developer.files')


@login_required
@require_POST
def delete_corpus_only_file(request):
    if not allowed_visitor(request.user):
        return redirect('home.index')

    rag_name = (request.POST.get('rag_resource_name') or '').strip()
    if not rag_name:
        return redirect('developer.files')

    _delete_from_rag_corpus(rag_name)
    DatabaseFile.objects.filter(rag_resource_name=rag_name).update(rag_resource_name='')
    return redirect('developer.files')


@login_required
@require_POST
def clean_text_api(request):
    if not allowed_visitor(request.user):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    try:
        body = json.loads(request.body)
        raw_text = body.get('text', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid request body.'}, status=400)

    if not raw_text:
        return JsonResponse({'error': 'Text is required.'}, status=400)

    result = clean_text(raw_text)
    if result.get('error'):
        return JsonResponse({'error': result['error']}, status=502)

    return JsonResponse({'text': result['text']})


@login_required
@require_POST
def suggest_description_api(request):
    if not allowed_visitor(request.user):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    body_text = None

    uploaded = request.FILES.get('file')
    if uploaded:
        extracted, ext_err = extract_text_from_upload(uploaded)
        if ext_err:
            return JsonResponse({'error': ext_err}, status=400)
        body_text = extracted
    else:
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, AttributeError):
            return JsonResponse({'error': 'Invalid request body.'}, status=400)

        body_text = ''
        if isinstance(body, dict):
            t = (body.get('text') or '').strip()
            if t:
                body_text = t
            elif 'document' in body:
                doc = body.get('document')
                if doc is None:
                    return JsonResponse({'error': '"document" must not be null.'}, status=400)
                try:
                    body_text = json.dumps(doc, ensure_ascii=False, indent=2)
                except (TypeError, ValueError) as exc:
                    return JsonResponse(
                        {'error': f'Could not serialize document: {exc}'},
                        status=400,
                    )
        elif isinstance(body, list):
            try:
                body_text = json.dumps(body, ensure_ascii=False, indent=2)
            except (TypeError, ValueError) as exc:
                return JsonResponse(
                    {'error': f'Could not serialize JSON array: {exc}'},
                    status=400,
                )

    if not body_text:
        return JsonResponse(
            {
                'error': (
                    'Provide multipart "file", a JSON body with "text", '
                    'a JSON object with "document", or a top-level JSON array.'
                ),
            },
            status=400,
        )

    result = summarize_for_description(body_text)
    if result.get('error'):
        return JsonResponse({'error': result['error']}, status=502)

    return JsonResponse({'description': result['description']})


@login_required
def accuracy(request):
    if not allowed_developer_visitor(request.user):
        return redirect('home.index')

    error = None
    success = None
    form_values = {
        'name': '',
        'question': '',
        'expected_answer': '',
        'required_terms': '',
        'is_active': True,
    }

    if request.method == 'POST':
        subfield = request.POST.get('subfield', '')

        if subfield == 'create_case':
            form_values = {
                'name': request.POST.get('name', '').strip(),
                'question': request.POST.get('question', '').strip(),
                'expected_answer': request.POST.get('expected_answer', '').strip(),
                'required_terms': request.POST.get('required_terms', '').strip(),
                'is_active': request.POST.get('is_active') == 'on',
            }

            if not form_values['name']:
                error = 'Name is required.'
            elif not form_values['question']:
                error = 'Question is required.'
            elif not form_values['expected_answer']:
                error = 'Expected answer is required.'
            else:
                AccuracyTestCase.objects.create(
                    name=form_values['name'],
                    question=form_values['question'],
                    expected_answer=form_values['expected_answer'],
                    required_terms=form_values['required_terms'],
                    is_active=form_values['is_active'],
                )
                success = f'Created "{form_values["name"]}".'
                form_values = {
                    'name': '',
                    'question': '',
                    'expected_answer': '',
                    'required_terms': '',
                    'is_active': True,
                }

        elif subfield == 'run_case':
            case_id = request.POST.get('case_id')
            try:
                test_case = AccuracyTestCase.objects.get(pk=case_id)
            except AccuracyTestCase.DoesNotExist:
                error = 'That test case was not found.'
            else:
                _run_accuracy_case(test_case)
                success = f'Ran "{test_case.name}".'

        elif subfield == 'run_all':
            active_cases = list(AccuracyTestCase.objects.filter(is_active=True).order_by('name', 'id'))
            if not active_cases:
                error = 'There are no active test cases to run.'
            else:
                for test_case in active_cases:
                    _run_accuracy_case(test_case)
                success = f'Ran {len(active_cases)} active test case(s).'

    cases = list(AccuracyTestCase.objects.all().order_by('name', 'id'))
    recent_runs = list(
        AccuracyTestRun.objects.select_related('test_case').order_by('-created_at')
    )
    latest_runs = {}
    for run in recent_runs:
        if run.test_case_id not in latest_runs:
            latest_runs[run.test_case_id] = run

    for case in cases:
        case.latest_run = latest_runs.get(case.id)
        case.term_list = _split_required_terms(case.required_terms)

    template_data = {
        'title': 'Accuracy Testing',
        'cases': cases,
        'recent_runs': recent_runs[:10],
        'total_cases': len(cases),
        'active_cases': sum(1 for case in cases if case.is_active),
        'error': error,
        'success': success,
        'form_values': form_values,
    }
    return render(request, 'developer/accuracy.html', {'template_data': template_data})
def usage_logs(request):
    if not allowed_visitor(request.user):
        return redirect('home.index')

    logs = QueryLog.objects.all().order_by('-timestamp')
    template_data = {
        'title': 'Usage Logs',
        'logs': logs,
    }
    successes = 0
    total_response_time = 0
    for log in logs:
        successes += 1 if log.success else 0
        total_response_time += log.response_time_ms
    num_queries = len(logs)
    template_data['num_queries'] = num_queries
    template_data['success_rate'] = int(100 * successes / num_queries) if num_queries else 0
    template_data['avg_response_time'] = int(total_response_time / num_queries) if num_queries else 0

    return render(request, 'developer/logs.html', {'template_data': template_data})
