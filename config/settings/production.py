"""
Production settings for calendar-builder
"""

from .base import *
from urllib.parse import urlparse

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Add request logging middleware for production debugging
MIDDLEWARE.insert(1, 'apps.core.middleware.RequestLoggingMiddleware')

# Security settings for production
SECURE_SSL_REDIRECT = False  # Cloudflare handles SSL termination
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True  # Trust X-Forwarded-Host header from proxy
USE_X_FORWARDED_PORT = True  # Trust X-Forwarded-Port header from proxy
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = 'DENY'

# Session settings
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 3600  # 1 hour
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# CSRF settings
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True

# ============================================================================
# DATABASE - Remote PostgreSQL (if DATABASE_URL is set)
# ============================================================================

db_url = config('DATABASE_URL', default=None)
if db_url:
    parsed = urlparse(db_url)

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': parsed.path[1:],
            'USER': parsed.username,
            'PASSWORD': parsed.password,
            'HOST': parsed.hostname,
            'PORT': parsed.port or 5432,
            'CONN_MAX_AGE': 60,
            'OPTIONS': {
                'connect_timeout': 10,
            }
        }
    }
else:
    # Fallback to local database from .env
    DATABASES['default'].update({
        'CONN_MAX_AGE': 60,
        'OPTIONS': {
            'connect_timeout': 10,
        }
    })

# ============================================================================
# STATIC AND MEDIA FILES - Cloudflare R2 CDN (if R2 is configured)
# ============================================================================

# Check if R2 is configured
USE_R2_STORAGE = all([
    config('R2_ACCESS_KEY_ID', default=None),
    config('R2_SECRET_ACCESS_KEY', default=None),
    config('R2_BUCKET_NAME', default=None),
    config('R2_ENDPOINT_URL', default=None),
    config('R2_PUBLIC_DOMAIN', default=None),
])

if USE_R2_STORAGE:
    # Use R2 for both static and media files
    STORAGES = {
        "default": {
            "BACKEND": "config.storage.MediaStorage",
        },
        "staticfiles": {
            "BACKEND": "config.storage.StaticStorage",
        },
    }

    # R2 Configuration (S3-compatible)
    AWS_ACCESS_KEY_ID = config('R2_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = config('R2_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = config('R2_BUCKET_NAME')
    AWS_S3_ENDPOINT_URL = config('R2_ENDPOINT_URL')
    AWS_S3_CUSTOM_DOMAIN = config('R2_PUBLIC_DOMAIN')

    # R2 Settings
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = False
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=31536000',
    }

    # URLs
    STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'
    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'

    # No local static/media roots when using R2
    STATIC_ROOT = None
    MEDIA_ROOT = None
else:
    # Fallback to local file storage
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
    MEDIA_ROOT = BASE_DIR / 'persistent_media'

# Cache settings for production
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://redis:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
} if config('REDIS_URL', default=None) else {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'cache_table',
    }
}

# Email settings for production
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@calendar.flyhomemnlab.com')

# Sentry error tracking (if configured)
SENTRY_DSN = config('SENTRY_DSN', default=None)
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    
    sentry_logging = LoggingIntegration(
        level=logging.INFO,
        event_level=logging.ERROR
    )
    
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), sentry_logging],
        traces_sample_rate=0.1,
        send_default_pii=True,
        environment=config('ENVIRONMENT', default='production'),
    )

# Database optimizations handled above in DATABASE configuration

# Production logging - more verbose for debugging
LOGGING['handlers']['console']['level'] = 'INFO'
LOGGING['root']['level'] = 'INFO'

# Configure specific loggers for production debugging
LOGGING['loggers'] = {
    'django': {
        'handlers': ['console'],
        'level': 'INFO',
        'propagate': False,
    },
    'django.request': {
        'handlers': ['console'],
        'level': 'INFO',
        'propagate': False,
    },
    'django.server': {
        'handlers': ['console'],
        'level': 'INFO',
        'propagate': False,
    },
    'apps': {
        'handlers': ['console'],
        'level': 'INFO',
        'propagate': False,
    },
    'apps.calendars': {
        'handlers': ['console'],
        'level': 'INFO',
        'propagate': False,
    },
    # Security logging
    'django.security': {
        'handlers': ['console'],
        'level': 'WARNING',
        'propagate': False,
    },
}

# Silence boto3 logging if using R2 storage
if USE_R2_STORAGE:
    LOGGING['loggers']['boto3'] = {'level': 'WARNING', 'handlers': ['console'], 'propagate': False}
    LOGGING['loggers']['botocore'] = {'level': 'WARNING', 'handlers': ['console'], 'propagate': False}
    LOGGING['loggers']['s3transfer'] = {'level': 'WARNING', 'handlers': ['console'], 'propagate': False}
    LOGGING['loggers']['urllib3'] = {'level': 'WARNING', 'handlers': ['console'], 'propagate': False}

# Additional production apps
if config('USE_CELERY', default=False, cast=bool):
    INSTALLED_APPS += [
        'django_celery_beat',
        'django_celery_results',
    ]
    
    # Celery Configuration
    CELERY_BROKER_URL = config('REDIS_URL', default='redis://redis:6379/0')
    CELERY_RESULT_BACKEND = config('REDIS_URL', default='redis://redis:6379/0')
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_TIMEZONE = TIME_ZONE
    CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# API settings (if using DRF)
if 'rest_framework' in INSTALLED_APPS:
    REST_FRAMEWORK = {
        'DEFAULT_RENDERER_CLASSES': [
            'rest_framework.renderers.JSONRenderer',
        ],
        'DEFAULT_PERMISSION_CLASSES': [
            'rest_framework.permissions.IsAuthenticated',
        ],
        'DEFAULT_AUTHENTICATION_CLASSES': [
            'rest_framework.authentication.SessionAuthentication',
            'rest_framework.authentication.TokenAuthentication',
        ],
        'DEFAULT_THROTTLE_CLASSES': [
            'rest_framework.throttling.AnonRateThrottle',
            'rest_framework.throttling.UserRateThrottle'
        ],
        'DEFAULT_THROTTLE_RATES': {
            'anon': '100/hour',
            'user': '1000/hour'
        },
        'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
        'PAGE_SIZE': 20,
    }