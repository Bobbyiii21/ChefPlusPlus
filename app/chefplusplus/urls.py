import re

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path('accounts/', include('accounts.urls')),
    path('admin/', admin.site.urls),
    path('', include('home.urls')),
    #path('chat/', include('chat.urls')),
    path('developer/', include('developer.urls')),
    path('recipes/', include('recipes.urls')),
]

# User uploads (RAG corpus files). ``static()`` only registers these when DEBUG
# is true; keep the same URLs working in production so chat reference links work.
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
else:
    media_prefix = settings.MEDIA_URL.lstrip("/")
    if media_prefix:
        urlpatterns += [
            re_path(
                rf"^{re.escape(media_prefix)}(?P<path>.*)$",
                serve,
                {"document_root": settings.MEDIA_ROOT},
            ),
        ]
