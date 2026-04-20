from django.db import models
from accounts.models import CPPUser
from django.utils import timezone


class DatabaseFile(models.Model):
    SOURCE_FILE = "file"
    SOURCE_TEXT = "text"
    SOURCE_CHOICES = [
        (SOURCE_FILE, "File Upload"),
        (SOURCE_TEXT, "Text Upload"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(max_length=1023, blank=True)
    file = models.FileField(upload_to='rag_dataset', blank=True)
    source_type = models.CharField(
        max_length=10, choices=SOURCE_CHOICES, default=SOURCE_FILE,
    )
    gcs_uri = models.CharField(max_length=1024, blank=True)
    rag_resource_name = models.CharField(max_length=1024, blank=True)
    date_added = models.DateTimeField("date added", default=timezone.now)
    uploader = models.ForeignKey(CPPUser, on_delete=models.SET(None), blank=True)

    def __str__(self):
        return self.name

# Create your models here.
