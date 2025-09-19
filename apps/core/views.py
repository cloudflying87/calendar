from django.shortcuts import render, redirect
from django.views.generic import TemplateView

class LandingPageView(TemplateView):
    """Beautiful landing page for Calendar Builder"""
    template_name = 'core/landing.html'

    def get(self, request, *args, **kwargs):
        # If user is already authenticated, redirect to their calendars
        if request.user.is_authenticated:
            return redirect('calendars:calendar_list')

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add some stats for the landing page
        from apps.calendars.models import Calendar, CalendarEvent
        from django.contrib.auth.models import User

        context.update({
            'total_calendars': Calendar.objects.count(),
            'total_events': CalendarEvent.objects.count(),
            'total_users': User.objects.filter(is_active=True).count(),
        })

        return context