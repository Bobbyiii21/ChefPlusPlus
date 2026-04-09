from django.contrib.auth.forms import UserCreationForm
from django.forms.utils import ErrorList
from django.utils.safestring import mark_safe
from django import forms
from .models import CPPUser
class CustomErrorList(ErrorList):
    def __str__(self):
        if not self:
            return ''
        return mark_safe(''.join([f'<div class="alert alert-danger" role="alert">{e}</div>' for e in self]))
class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField()

    field_order = ['email', 'username', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super(CustomUserCreationForm, self).__init__(*args, **kwargs)
        self.fields['email'].label = 'Email'
        self.fields['email'].widget.attrs.update({'class': 'form-control'})
        self.fields['username'].label = 'Name'
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['password1'].label = 'Password'
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].label = 'Password Confirmation'
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})
        #self.fields['nutrition_goals'].label = 'Nutrition Goals'
        #self.fields['nutrition_goals'].widget.attrs.update({'class': 'form-control'})
        #self.fields['nutrition_goals'].help_text = "What do you want ChefPlusPlus"

        for field in ['email', 'username', 'password1', 'password2']:
            self.fields[field].help_text = None
        

    class Meta:
        model = CPPUser
        fields = ('username', 'email', 'password1', 'password2')