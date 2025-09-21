"""
URL configuration for calendar-builder project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse

def health_check(request):
    return JsonResponse({'status': 'ok'})

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('calendars/', include('apps.calendars.urls')),
    path('health/', health_check, name='health'),
    path('', include('apps.core.urls')),  # Beautiful landing page
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Add debug toolbar URLs in development
if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass

    # Add error page testing URLs in development
    from django.views.generic import TemplateView
    from django.http import Http404
    from django.core.exceptions import PermissionDenied

    def test_404(request):
        raise Http404("This is a test 404 error")

    def test_500(request):
        raise Exception("This is a test 500 error")

    def test_403(request):
        raise PermissionDenied("This is a test 403 error")

    urlpatterns += [
        path('test-404/', test_404, name='test_404'),
        path('test-500/', test_500, name='test_500'),
        path('test-403/', test_403, name='test_403'),
    ]