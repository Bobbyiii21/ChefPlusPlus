import json
import logging
import os
import tempfile
import uuid

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.models import CPPUser
from .models import DatabaseFile
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

@login_required
def index(request):
    if not allowed_visitor(request.user):
        return redirect('home.index')
    template_data = {}
    template_data['title'] = 'Database'
    return render(request, 'developer/index.html', {'template_data': template_data})


def _validate_file_extension(uploaded_file):
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, ext
    return True, ext


def _import_to_rag(gcs_uri, db_file):
    """Import a GCS URI into the RAG corpus and store the resource name."""
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
        logger.exception("RAG import failed for %s", gcs_uri)


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

                        gcs_uri = gcs_upload_file(tmp_path, destination_name=f"rag_dataset/{uuid.uuid4().hex}{ext}")
                        db_file.gcs_uri = gcs_uri
                        db_file.save(update_fields=['gcs_uri'])

                        _import_to_rag(gcs_uri, db_file)
                        success = f'File "{name}" uploaded successfully.'
                    except Exception as exc:
                        logger.exception("File upload failed")
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
                    dest_name = f"rag_dataset/{uuid.uuid4().hex}.txt"
                    gcs_uri = gcs_upload_from_string(
                        raw_text.encode('utf-8'),
                        dest_name,
                        content_type='text/plain',
                    )
                    db_file.gcs_uri = gcs_uri
                    db_file.save(update_fields=['gcs_uri'])

                    _import_to_rag(gcs_uri, db_file)
                    success = f'Text source "{name}" uploaded successfully.'
                except Exception as exc:
                    logger.exception("Text upload failed")
                    db_file.delete()
                    error = f'Upload failed: {exc}'

    template_data = {
        'title': 'Database',
        'files': DatabaseFile.objects.all().order_by('-date_added'),
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
        try:
            rag_delete_file(db_file.rag_resource_name)
        except Exception:
            logger.exception("RAG delete failed for %s", db_file.rag_resource_name)

    if db_file.gcs_uri:
        try:
            blob_name = db_file.gcs_uri.split('/', 3)[-1] if '/' in db_file.gcs_uri else ''
            if blob_name:
                gcs_delete_file(blob_name)
        except Exception:
            logger.exception("GCS delete failed for %s", db_file.gcs_uri)

    if db_file.file:
        try:
            db_file.file.delete(save=False)
        except Exception:
            logger.exception("Local file delete failed")

    db_file.delete()
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

        body_text = ""
        if isinstance(body, dict):
            t = (body.get("text") or "").strip()
            if t:
                body_text = t
            elif "document" in body:
                doc = body.get("document")
                if doc is None:
                    return JsonResponse({'error': '"document" must not be null.'}, status=400)
                try:
                    body_text = json.dumps(doc, ensure_ascii=False, indent=2)
                except (TypeError, ValueError) as exc:
                    return JsonResponse(
                        {'error': f"Could not serialize document: {exc}"},
                        status=400,
                    )
        elif isinstance(body, list):
            try:
                body_text = json.dumps(body, ensure_ascii=False, indent=2)
            except (TypeError, ValueError) as exc:
                return JsonResponse(
                    {'error': f"Could not serialize JSON array: {exc}"},
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
