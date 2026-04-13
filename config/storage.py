"""
Custom storage backends for Cloudflare R2 CDN
"""
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class StaticStorage(S3Boto3Storage):
    """
    Storage backend for static files (CSS, JS, images) on Cloudflare R2
    """
    location = 'static'
    default_acl = None
    file_overwrite = True  # Static files can be overwritten

    @property
    def custom_domain(self):
        """Use the configured custom domain for CDN URLs"""
        return settings.AWS_S3_CUSTOM_DOMAIN


class MediaStorage(S3Boto3Storage):
    """
    Storage backend for media files (user uploads, generated files) on Cloudflare R2
    """
    location = 'media'
    default_acl = None
    file_overwrite = False  # Don't overwrite user uploads

    @property
    def custom_domain(self):
        """Use the configured custom domain for CDN URLs"""
        return settings.AWS_S3_CUSTOM_DOMAIN
