from django.db import models
from django.contrib.auth.models import PermissionsMixin, AbstractUser, BaseUserManager
from django.utils import timezone
from django.utils.text import slugify
#import datetime
from django.utils.safestring import mark_safe
import os

#NOTE: some of these models may need to be moved into different apps in order to be integrated properly, dont forget import statments if necessary after moving
#NOTE: make sure to verify that we are using the same method of implementation for things such as locations, fix conflicts immediately

#File Upload naming schemes
def get_pfp_path(user, filename):
    filetype = filename.split('.')[-1]
    new_name = user.slugify_name() + '.' + filetype
    return os.path.join('pfps', new_name)

#might just create 2 separate user classes? depends on whether its easier to implement a parent class or have 2 independent user classes.
#parent class defines a User with an ID, username, email
class CustomUserManager(BaseUserManager):
    def create_user(self, email, name, password):
        user = self.model(email=email, username=name, password=password)
        user.set_password(password)
        user.is_staff = False
        user.is_superuser = False
        user.save(using=self.db)
        return user
    
    def create_superuser(self, email, name, password):
        user = self.model(email=email, username=name)
        user.set_password(password)
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self.db)
        return user

    def get_by_natural_key(self, email_):
        print(email_)
        return self.get(email=email_)

class CPPUser(AbstractUser, PermissionsMixin):
    id = models.AutoField(primary_key=True)
    #username is used as the name that the chat calls you
    email = models.EmailField("email address", max_length=127, unique=True)
    pfp = models.ImageField(upload_to=get_pfp_path, height_field=None, width_field=None, blank=True)
    date_joined = models.DateTimeField("date joined", default=timezone.now)
    logins = models.IntegerField(default=0)
    #nutrition_goal = models.TextField(max_length=511, blank=True)
    #allergies = models.TextField(max_length=511, blank=True)
    #diet = models.TextField(max_length=127, blank=True)
    # Check that the above image loads and figure out where to store user-uploaded images
    is_staff = models.BooleanField(
        "staff status",
        default=False,
        help_text="Designates whether the user can log into this admin site.",
    )
    is_active = models.BooleanField(
        "active",
        default=True,
        help_text=
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts.",
    )


    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    objects = CustomUserManager()

    class Meta:
        db_table = 'auth_user'
        verbose_name = "User"
        verbose_name_plural = "Users"

    def slugify_name(self):
        return f"{str(self.id)}-{slugify(self.email.split('@')[0])}"

    def get_id_by_name(user_name):
        return int(user_name.split('-')[0])

    def natural_key(self):
        return self.email
    
    def __str__(self):
        return self.slugify_name()

