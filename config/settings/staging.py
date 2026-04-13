"""
Staging settings for calendar-builder
Use this to test R2 and remote database before production deployment
"""

from .base import *
from urllib.parse import urlparse

# Debug mode for staging
DEBUG = config('DEBUG', default=True, cast=bool)

# Security settings
SECURE_SSL_REDIRECT = False
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# ============================================================================
# DATABASE - Remote PostgreSQL
# ============================================================================

db_url = config('DATABASE_URL')
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

# ============================================================================
# STATIC AND MEDIA FILES - Cloudflare R2 CDN
# ============================================================================

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

# ============================================================================
# LOGGING - Silence boto3/S3 noise
# ============================================================================

LOGGING['loggers']['boto3'] = {'level': 'WARNING'}
LOGGING['loggers']['botocore'] = {'level': 'WARNING'}
LOGGING['loggers']['s3transfer'] = {'level': 'WARNING'}
LOGGING['loggers']['urllib3'] = {'level': 'WARNING'}

# ============================================================================
# EMAIL - Optional for staging
# ============================================================================

if config('EMAIL_HOST_USER', default=None):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
    DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@calendar.flyhomemnlab.com')
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ============================================================================
# CACHE - Redis if available, otherwise database
# ============================================================================

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://localhost:6379/0'),
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
