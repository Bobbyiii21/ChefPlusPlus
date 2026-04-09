from django.contrib.auth import login as auth_login, authenticate, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from accounts.models import CPPUser
from .models import DatabaseFile


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

    template_data = {}
    template_data['title'] = 'Database'
    template_data['files'] = DatabaseFile.objects.all()
    return render(request, 'developer/files.html', {'template_data': template_data})



