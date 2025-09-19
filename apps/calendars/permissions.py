"""
Permission utilities for calendar sharing functionality
"""
from django.shortcuts import get_object_or_404
from django.http import Http404
from functools import wraps
from .models import Calendar


def get_calendar_or_404(user, calendar_id, permission_required='view'):
    """
    Get a calendar object that the user has permission to access

    Args:
        user: The requesting user
        calendar_id: ID of the calendar
        permission_required: 'view', 'edit', or 'share'

    Returns:
        Calendar object if user has permission

    Raises:
        Http404 if calendar doesn't exist or user lacks permission
    """
    try:
        calendar = Calendar.objects.get(id=calendar_id)
    except Calendar.DoesNotExist:
        raise Http404("Calendar not found")

    # Check permissions
    if permission_required == 'view' and not calendar.can_view(user):
        raise Http404("Calendar not found")
    elif permission_required == 'edit' and not calendar.can_edit(user):
        raise Http404("Calendar not found")
    elif permission_required == 'share' and not calendar.can_share(user):
        raise Http404("Calendar not found")

    return calendar


def require_calendar_permission(permission_required='view'):
    """
    Decorator to check calendar permissions

    Usage:
        @require_calendar_permission('edit')
        def my_view(request, calendar_id):
            # calendar is available as request.calendar
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, calendar_id, *args, **kwargs):
            calendar = get_calendar_or_404(
                request.user,
                calendar_id,
                permission_required
            )
            request.calendar = calendar
            return view_func(request, calendar_id, *args, **kwargs)
        return wrapper
    return decorator


class CalendarPermissionMixin:
    """
    Mixin for class-based views that need calendar permission checking
    """
    permission_required = 'view'

    def get_calendar(self):
        """Get the calendar object with permission checking"""
        calendar_id = self.kwargs.get('calendar_id') or self.kwargs.get('pk')
        return get_calendar_or_404(
            self.request.user,
            calendar_id,
            self.permission_required
        )

    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to check permissions"""
        self.calendar = self.get_calendar()
        return super().dispatch(request, *args, **kwargs)


def get_user_calendars(user, include_shared=True):
    """
    Get all calendars accessible to a user

    Args:
        user: The user
        include_shared: Whether to include shared calendars

    Returns:
        QuerySet of Calendar objects with permission annotations
    """
    # Get owned calendars
    owned_calendars = Calendar.objects.filter(user=user)

    if not include_shared:
        return owned_calendars

    # Get shared calendars
    shared_calendar_ids = user.shared_calendars.values_list('calendar_id', flat=True)
    shared_calendars = Calendar.objects.filter(id__in=shared_calendar_ids)

    # Combine and return
    return owned_calendars.union(shared_calendars).order_by('-year')