from django.contrib.auth import login as auth_login, authenticate, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from .forms import CustomUserCreationForm, CustomErrorList
from .models import CPPUser
from chefplusplus import settings
import re


def normalize_link(url: str) -> str:
    """Ensure URL has a scheme (https://) for safe use in href."""
    u = (url or '').strip()
    if not u:
        return u
    if 'https://' not in u:
        if 'http://' not in u:
            return f'https://{u}'
        else:
            return u.replace('http://', 'https://')
    return u


def validate_urls(urls: str) -> list[str]:
    """Validate a string of comma-separated URLs. Returns an empty list if the URL is invalid."""
    return_urls = re.findall(r'(?:http[s]?:\/\/.)?(?:www\.)?[-a-zA-Z0-9@%._\+~#=]{2,256}\.[a-z]{2,6}\b(?:[-a-zA-Z0-9@:%_\+.~#?&\/\/=]*)', urls)
    return [normalize_link(u) for u in return_urls]
    

@login_required
def logout(request):
    auth_logout(request)
    return redirect('home.index')

def login(request, just_registered=False):
    template_data = {}
    template_data['title'] = 'Login'
    if request.method == 'GET':
        return render(request, 'accounts/login.html', {'template_data': template_data})
    elif just_registered:
        user = authenticate(request, username = request.POST['email'],
                          password = request.POST['password1'])
        auth_login(request, user)
        return redirect('home.index')
    elif request.method == 'POST':
        user = authenticate(request, username = request.POST['email'],
                          password = request.POST['password'])
        if user is None:
            template_data['error'] = 'The username or password is incorrect.'
            return render(request, 'accounts/login.html', {'template_data': template_data})
        user.save()
        auth_login(request, user)
        return redirect('home.index')

def register(request):
    template_data = {}
    template_data['title'] = 'Register'
    if request.method == 'GET':
        template_data['form'] = CustomUserCreationForm()
        return render(request, 'accounts/register.html', {'template_data': template_data})
    elif request.method == 'POST':
        form = CustomUserCreationForm(request.POST, error_class=CustomErrorList)
        if form.is_valid():
            form.save()
            login(request, just_registered=True)
            return redirect('home.index')
        else:
            template_data['form'] = form
            return render(request, 'accounts/register.html', {'template_data': template_data})

'''
@login_required    
def onboard(request):
    if request.method == 'POST':
        if (request.POST['user_type'] == 'job_seeker'):
            job_seeker = JobSeeker()
            job_seeker.user = request.user
            request.user.is_seeker = True 
            if (request.POST['headline'] and request.POST['headline'].strip()):
                request.user.headline = request.POST['headline'].strip()
            if ('pfp' in request.FILES):
                request.user.pfp = request.FILES['pfp']
            if ('resume' in request.FILES):
                job_seeker.resume = request.FILES['resume']
            if (request.POST['links'] and request.POST['links'].strip()):
                job_seeker.links = ''.join(f"{link}," for link in validate_urls(request.POST['links'].strip()))
            request.user.save()
            job_seeker.save()
            home_notif.update_onboarded_user_notifications
        elif (request.POST['user_type'] == 'recruiter'):
            recruiter = Recruiter()
            recruiter.user = request.user
            request.user.is_recruiter = True 
            if (request.POST['headline'] and request.POST['headline'].strip()):
                request.user.headline = request.POST['headline'].strip()
            if ('pfp' in request.FILES):
                request.user.pfp = request.FILES['pfp']
            if (request.POST['company'] and request.POST['company'].strip()):
                recruiter.company = request.POST['company'].strip()
            if (request.POST['links'] and request.POST['links'].strip()):
                recruiter.links = ''.join(f"{link}," for link in validate_urls(request.POST['links'].strip()))
            request.user.save()
            recruiter.save()
            home_notif.update_onboarded_user_notifications
        return redirect('accounts.profiles', user_link=str(request.user))
    else:
        template_data = {}
        return render(request, 'accounts/onboard.html', {'template_data': template_data})
'''
        
#This should be just to show your own account to edit your settings
def profiles(request, user_link):
    id = CPPUser.get_id_by_name(user_link)
    user = CPPUser.objects.get(id=id) 
    template_data = {}
    template_data['title'] = 'My Account'
    template_data['profile_user'] = user
    template_data['id'] = id
    return render(request, 'accounts/profiles.html', {'template_data': template_data, 'google_api_key': settings.GOOGLE_API_KEY,})

'''
    id = TTUser.get_id_by_name(user_link)
    user = TTUser.objects.get(id=id) 
    template_data = {}
    template_data['title'] = 'Profiles'
    template_data['profile_user'] = user
    template_data['id'] = id
    template_data['is_seeker'] = user.is_seeker
    template_data['is_recruiter'] = user.is_recruiter
    if template_data['is_seeker']:
        seeker_user = JobSeeker.objects.get(user_id=id)
        template_data["seeker_user"] = seeker_user
        template_data['education'] = seeker_user.education.all()
        template_data['skills'] = seeker_user.skills.all()
        template_data['skills_options'] = Skill.objects.all().order_by('name')
        template_data['experience'] = seeker_user.experience.all()
        template_data['degree_choices'] = Education.DegreeType.choices
        t_links = [normalize_link(l.strip()) for l in seeker_user.links.split(",") if l.strip()]
        template_data['links'] = t_links
        #find some way to put resume 
    elif template_data['is_recruiter']:
        recruiter_user = Recruiter.objects.get(user_id=id)
        template_data['recruiter_user'] = recruiter_user
        t_links = [normalize_link(l.strip()) for l in recruiter_user.links.split(",") if l.strip()]
        template_data['links'] = t_links


    if request.method == 'POST':
        updated = request.POST['subfield']
        if updated == 'headline':
            user.headline = request.POST['headline']
            user.save()

        if updated == 'pfp':
            if ('pfp_upload' in request.FILES):
                user.pfp.delete()
                user.pfp = request.FILES['pfp_upload']
                user.save()

        if updated == 'location':
            user.street = request.POST.get('street', '').strip()
            user.city = request.POST.get('city', '').strip().title()
            user.state = request.POST.get('state', '').strip().upper()
            user.postal_code = request.POST.get('postal_code', '').strip()
            user.country = request.POST.get('country', '').strip().title()
            user.latitude = request.POST.get('latitude')
            user.longitude = request.POST.get('longitude')
            user.latitude = float(user.latitude) if user.latitude else None
            user.longitude = float(user.longitude) if user.longitude else None
            if not user.country:
                user.location = 'No location specified'
            elif not user.state:
                user.location = user.country.title()
            elif user.state and not user.city:
                user.location = f"{user.state.title()}, {user.country.title()}"
            elif user.city:
                user.location = f"{user.city.title()}, {user.state.title()}"
            user.save()
            
        elif user.is_seeker:
            if updated == 'hidden':
                hidden_links = request.POST.getlist('hidden')
                if 'profile' in hidden_links:
                    seeker_user.account_is_hidden = True
                else:
                    seeker_user.account_is_hidden = False
                if 'experience' in hidden_links:
                    seeker_user.experience_is_hidden = True
                else:
                    seeker_user.experience_is_hidden = False
                if 'education' in hidden_links:
                    seeker_user.education_is_hidden = True
                else:
                    seeker_user.education_is_hidden = False
                if 'links' in hidden_links:
                    seeker_user.links_is_hidden = True
                else:
                    seeker_user.links_is_hidden = False
                seeker_user.save()

            if request.POST['subfield'] == 'education_add':
                try:
                    grad_year = request.POST['grad_year']
                except:
                    return redirect('home.index') #MAKE THIS A JS alert()
                new_education = Education()
                new_education.grad_year = grad_year
                new_education.degree = request.POST['degree']
                new_education.degree_name = request.POST['degree_name']
                new_education.school_name = request.POST['school_name']
                new_education.save()
                seeker_user.education.add(new_education)
                return redirect('accounts.profiles', user_link=str(request.user))

            if request.POST['subfield'] == 'education_edit':
                try:
                    grad_year = request.POST['grad_year']
                except:
                    return redirect('home.index') #MAKE THIS A JS alert()
                try:
                    edit_education = get_object_or_404(Education, id=request.POST['id'])
                except:
                    return redirect('home.index') #MAKE THIS A JS alert()
                edit_education.grad_year = grad_year
                edit_education.degree = request.POST['degree']
                edit_education.degree_name = request.POST['degree_name']
                edit_education.school_name = request.POST['school_name']
                edit_education.save()
                return redirect('accounts.profiles', user_link=str(request.user))


            if request.POST['subfield'] == 'education_remove':
                try:
                    deleted_education = get_object_or_404(Education, id=request.POST['education_id'])
                except:
                    return redirect('home.index') #MAKE THIS A JS alert()
                deleted_education.delete()
                return redirect('accounts.profiles', user_link=str(request.user))
            
            elif request.POST['subfield'] == 'experience_add':
                new_experience = Experience()
                new_experience.company_name = request.POST['company_name']
                new_experience.position_title = request.POST['position_title']
                new_experience.job_description = request.POST['job_description']
                try: new_experience.current_employee = bool(request.POST['current_employee'])
                except: new_experience.current_employee = False
                new_experience.start_date = request.POST['start_date']
                if not new_experience.current_employee:
                    new_experience.end_date = request.POST['end_date']
                new_experience.save()
                seeker_user.experience.add(new_experience)
                return redirect('accounts.profiles', user_link=str(request.user))
            
            elif request.POST['subfield'] == 'experience_edit':
                try:
                    edit_experience = get_object_or_404(Experience, id=request.POST['id'])
                except:
                    return redirect('home.index') #MAKE THIS A JS alert()

                edit_experience.company_name = request.POST['company_name']
                edit_experience.position_title = request.POST['position_title']
                edit_experience.job_description = request.POST['job_description']
                edit_experience.current_employee = bool(request.POST.get('current_employee', False))
                edit_experience.start_date = request.POST['start_date']
                if not edit_experience.current_employee:
                    edit_experience.end_date = request.POST['end_date']
                edit_experience.save()
                return redirect('accounts.profiles', user_link=str(request.user))


            if request.POST['subfield'] == 'experience_remove':
                try:
                    deleted_experience = get_object_or_404(Experience, id=request.POST['experience_id'])
                except:
                    return redirect('home.index') #MAKE THIS A JS alert()
                deleted_experience.delete()
                return redirect('accounts.profiles', user_link=str(request.user))

            if request.POST['subfield'] == 'link_add':
                links = validate_urls(request.POST['link'])
                seeker_user.links += ''.join(f"{link}," for link in links)
                seeker_user.save()
                template_data['links'].extend(links)

            if request.POST['subfield'] == 'link_delete':
                to_remove = request.POST['link'].strip()
                seeker_user.links = seeker_user.links.replace(f"{to_remove},", '')
                seeker_user.save()
                template_data['links'][:] = [item for item in template_data['links'] if item != to_remove]

            if request.POST['subfield'] == 'skill_add':
                for skill in request.POST.getlist('skills'):
                    seeker_user.skills.add(get_object_or_404(Skill, id=skill))
                seeker_user.save()
                home_notif.update_seeker_notifications(user)
                
            if request.POST['subfield'] == 'skill_delete':
                skill = Skill.objects.get(id=request.POST['id'])
                seeker_user.skills.remove(skill)
                seeker_user.save()

            if request.POST['subfield'] == 'resume_change':
                if ('resume_upload' in request.FILES):
                    seeker_user.resume.delete()
                    seeker_user.resume = request.FILES['resume_upload']
                    seeker_user.save()

            if request.POST['subfield'] == 'resume_delete':
                seeker_user.resume.delete()
                seeker_user.save()
                
            home_notif.update_seeker_notifications(user)

        elif user.is_recruiter:
            if request.POST['subfield'] == 'link_add':
                links = validate_urls(request.POST['link'])
                recruiter_user.links += ''.join(f"{link}," for link in links)
                recruiter_user.save()
                template_data['links'].extend(links)

            if request.POST['subfield'] == 'link_delete':
                to_remove = request.POST['link'].strip()
                recruiter_user.links = recruiter_user.links.replace(f"{to_remove},", '')
                recruiter_user.save()
                template_data['links'][:] = [item for item in template_data['links'] if item != to_remove]


    return render(request, 'accounts/profiles.html', {'template_data': template_data, 'google_api_key': settings.GOOGLE_API_KEY,})
'''