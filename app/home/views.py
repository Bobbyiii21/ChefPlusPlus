from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.middleware.csrf import get_token


def index(request):
    # Ensure the CSRF cookie exists for the JS /api/chat POST call.
    get_token(request)
    template_data = {}
    template_data['title'] = 'Chef++'
    return render(request, 'home/index.html', {'template_data': template_data})

def about(request):
    return render(request, 'home/about.html')