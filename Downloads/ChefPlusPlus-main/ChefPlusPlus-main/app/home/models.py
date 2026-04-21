from django.db import models
from django.conf import settings


class QueryLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    timestamp = models.DateTimeField(auto_now_add=True)
    response_time_ms = models.IntegerField()
    success = models.BooleanField()
