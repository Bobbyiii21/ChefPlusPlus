from django.db import models
from django.conf import settings
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
    
class QueryLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    timestamp = models.DateTimeField(auto_now_add=True)
    response_time_ms = models.IntegerField()
    success = models.BooleanField()



class AccuracyTestCase(models.Model):
    name = models.CharField(max_length=255)
    question = models.TextField(max_length=1023)
    expected_answer = models.TextField(max_length=4095)
    required_terms = models.TextField(max_length=1023, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class AccuracyTestRun(models.Model):
    class Status(models.TextChoices):
        PASS = "pass", "Pass"
        FAIL = "fail", "Fail"
        REVIEW = "review", "Needs Review"
        ERROR = "error", "Error"

    test_case = models.ForeignKey(
        AccuracyTestCase,
        on_delete=models.CASCADE,
        related_name='runs',
    )
    actual_answer = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    missing_terms = models.TextField(max_length=1023, blank=True)
    response_time_ms = models.IntegerField(default=0)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.REVIEW,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.test_case.name} - {self.get_status_display()}"


class Intent(models.Model):
    name = models.CharField(max_length=50, unique=True)
    prompt = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Pattern(models.Model):
    intent = models.ForeignKey(Intent, on_delete=models.CASCADE, related_name='patterns')
    regex = models.CharField(max_length=2047)

    def __str__(self):
        return f"{self.intent.name}: {self.regex}"
