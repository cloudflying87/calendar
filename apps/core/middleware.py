import logging
import time
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(MiddlewareMixin):
    """Simple request logging middleware for production debugging"""

    def process_request(self, request):
        # Start timing
        request._start_time = time.time()

        # Log significant requests (skip static files and health checks)
        if self._should_log_request(request):
            user_info = f"User: {request.user.username}" if hasattr(request, 'user') and request.user.is_authenticated else "Anonymous"
            logger.info(f"REQUEST: {request.method} {request.path} - {user_info} - IP: {self._get_client_ip(request)}")

    def process_response(self, request, response):
        # Calculate request duration
        if hasattr(request, '_start_time'):
            duration = time.time() - request._start_time

            # Log slow requests or errors
            if self._should_log_response(request, response, duration):
                user_info = f"User: {request.user.username}" if hasattr(request, 'user') and request.user.is_authenticated else "Anonymous"
                logger.info(f"RESPONSE: {request.method} {request.path} - Status: {response.status_code} - Duration: {duration:.3f}s - {user_info}")

        return response

    def _should_log_request(self, request):
        """Determine if we should log this request"""
        # Skip static files, admin static, and health checks
        skip_paths = ['/static/', '/media/', '/favicon.ico', '/health/', '/admin/jsi18n/']

        for skip_path in skip_paths:
            if request.path.startswith(skip_path):
                return False

        return True

    def _should_log_response(self, request, response, duration):
        """Determine if we should log this response"""
        # Log if:
        # - Request was slow (>2 seconds)
        # - Response was an error (4xx, 5xx)
        # - Request was significant (not static files)
        return (
            duration > 2.0 or
            response.status_code >= 400 or
            self._should_log_request(request)
        )

    def _get_client_ip(self, request):
        """Get the client's IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip