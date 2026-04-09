import logging

from django.contrib.auth import login as auth_login, authenticate, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from accounts.models import CPPUser
from .models import DatabaseFile
from tools.gcs_storage import upload_file as gcs_upload_file
from tools.rag_files import import_files as rag_import_files

logger = logging.getLogger(__name__)


def allowed_visitor(user: CPPUser):
    return user.is_superuser

@login_required
def index(request):
    if not allowed_visitor(request.user):
        return redirect('home.index')
    template_data = {}
    template_data['title'] = 'Database'
    return render(request, 'developer/index.html', {'template_data': template_data})

@login_required
def database_files(request):
    if not allowed_visitor(request.user):
        return redirect('home.index')

    if request.method == 'POST':
        if request.POST['subfield'] == 'file_add':
            new_file = DatabaseFile()
            new_file.name = request.POST['name']
            if request.POST['description']:
                new_file.description = request.POST['description']
            new_file.file = request.FILES['file_upload']
            new_file.uploader = request.user
            new_file.save()

            # Upload the saved file to GCS, then import into the RAG corpus
            gs_uri = gcs_upload_file(new_file.file.path)
            try:
                rag_import_files([gs_uri])
            except Exception:
                logger.exception("RAG import failed for %s", gs_uri)

    template_data = {}
    template_data['title'] = 'Database'
    template_data['files'] = DatabaseFile.objects.all()
    return render(request, 'developer/files.html', {'template_data': template_data})



