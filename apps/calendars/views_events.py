from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView
from django.http import JsonResponse, HttpResponse
from django.urls import reverse_lazy
from django.db.models import Q
from .models import EventMaster, EventGroup, UserEventPreferences, CalendarEvent, Calendar
from django.contrib import messages
from django.views import View
import calendar as cal
import csv
import json
from datetime import datetime


class MasterEventListView(LoginRequiredMixin, ListView):
    model = EventMaster
    template_name = 'calendars/master_event_list.html'
    context_object_name = 'events'
    paginate_by = 20

    def get_queryset(self):
        queryset = EventMaster.objects.filter(user=self.request.user)

        # Search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(groups__icontains=search)
            )

        # Filter by group
        group_filter = self.request.GET.get('group')
        if group_filter:
            queryset = queryset.filter(groups__icontains=group_filter)

        # Filter by month
        month_filter = self.request.GET.get('month')
        if month_filter:
            queryset = queryset.filter(month=int(month_filter))

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['groups'] = EventGroup.objects.filter(user=self.request.user)
        context['months'] = [
            (i, cal.month_name[i]) for i in range(1, 13)
        ]
        return context


class MasterEventCreateView(LoginRequiredMixin, CreateView):
    model = EventMaster
    template_name = 'calendars/master_event_form.html'
    fields = ['name', 'event_type', 'month', 'day', 'year_occurred', 'groups', 'description']
    success_url = reverse_lazy('calendars:master_events')

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, 'Master event created successfully!')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['groups'] = EventGroup.objects.filter(user=self.request.user)
        context['title'] = 'Create Master Event'
        return context


class MasterEventUpdateView(LoginRequiredMixin, UpdateView):
    model = EventMaster
    template_name = 'calendars/master_event_form.html'
    fields = ['name', 'event_type', 'month', 'day', 'year_occurred', 'groups', 'description']
    success_url = reverse_lazy('calendars:master_events')

    def get_queryset(self):
        return EventMaster.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, 'Master event updated successfully!')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['groups'] = EventGroup.objects.filter(user=self.request.user)
        context['title'] = 'Edit Master Event'
        return context


class MasterEventDeleteView(LoginRequiredMixin, DeleteView):
    model = EventMaster
    template_name = 'calendars/master_event_confirm_delete.html'
    success_url = reverse_lazy('calendars:master_events')

    def get_queryset(self):
        return EventMaster.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Master event deleted successfully!')
        return super().delete(request, *args, **kwargs)


class EventGroupListView(LoginRequiredMixin, ListView):
    model = EventGroup
    template_name = 'calendars/event_group_list.html'
    context_object_name = 'groups'

    def get_queryset(self):
        return EventGroup.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add event count for each group
        for group in context['groups']:
            group.event_count = EventMaster.objects.filter(
                user=self.request.user,
                groups__icontains=group.name
            ).count()
        return context


class EventGroupCreateView(LoginRequiredMixin, CreateView):
    model = EventGroup
    template_name = 'calendars/event_group_form.html'
    fields = ['name', 'description']
    success_url = reverse_lazy('calendars:event_groups')

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, 'Event group created successfully!')
        return super().form_valid(form)


class EventGroupUpdateView(LoginRequiredMixin, UpdateView):
    model = EventGroup
    template_name = 'calendars/event_group_form.html'
    fields = ['name', 'description']
    success_url = reverse_lazy('calendars:event_groups')

    def get_queryset(self):
        return EventGroup.objects.filter(user=self.request.user)

    def form_valid(self, form):
        old_name = self.get_object().name
        new_name = form.cleaned_data['name']

        # Update all master events that reference this group
        if old_name != new_name:
            events = EventMaster.objects.filter(
                user=self.request.user,
                groups__icontains=old_name
            )
            for event in events:
                groups = event.get_groups_list()
                if old_name in groups:
                    groups[groups.index(old_name)] = new_name
                    event.set_groups_list(groups)
                    event.save()

        messages.success(self.request, 'Event group updated successfully!')
        return super().form_valid(form)


class EventGroupDeleteView(LoginRequiredMixin, DeleteView):
    model = EventGroup
    template_name = 'calendars/event_group_confirm_delete.html'
    success_url = reverse_lazy('calendars:event_groups')

    def get_queryset(self):
        return EventGroup.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        group = self.get_object()

        # Remove group from all master events
        events = EventMaster.objects.filter(
            user=request.user,
            groups__icontains=group.name
        )
        for event in events:
            event.remove_from_group(group.name)

        messages.success(request, 'Event group deleted successfully!')
        return super().delete(request, *args, **kwargs)


@login_required
def user_preferences_view(request):
    """View for managing user event preferences"""
    preferences, created = UserEventPreferences.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        add_to_master = request.POST.get('add_to_master_list')
        default_groups = request.POST.get('default_groups', '')

        preferences.add_to_master_list = add_to_master
        preferences.default_groups = default_groups
        preferences.save()

        messages.success(request, 'Preferences updated successfully!')
        return redirect('calendars:user_preferences')

    context = {
        'preferences': preferences,
        'groups': EventGroup.objects.filter(user=request.user)
    }
    return render(request, 'calendars/user_preferences.html', context)


class ApplyMasterEventsView(LoginRequiredMixin, View):
    """View to apply master events from groups to a calendar"""

    def get(self, request, calendar_id):
        from .models import Calendar
        calendar = get_object_or_404(Calendar, id=calendar_id, user=request.user)
        groups = EventGroup.objects.filter(user=request.user)

        context = {
            'calendar': calendar,
            'groups': groups
        }
        return render(request, 'calendars/apply_master_events.html', context)

    def post(self, request, calendar_id):
        from .models import Calendar
        calendar = get_object_or_404(Calendar, id=calendar_id, user=request.user)
        selected_groups = request.POST.getlist('groups')
        combine_events = request.POST.get('combine_events', False) == 'true'

        applied_count = 0
        combined_count = 0
        skipped_count = 0

        # Get all master events from selected groups
        events = EventMaster.objects.filter(user=request.user)
        for event in events:
            event_groups = event.get_groups_list()
            if any(group in selected_groups for group in event_groups):
                # Check if event already exists for this date
                existing = CalendarEvent.objects.filter(
                    calendar=calendar,
                    month=event.month,
                    day=event.day
                ).first()

                if not existing:
                    # Create calendar event linked to master event
                    CalendarEvent.objects.create(
                        calendar=calendar,
                        master_event=event,
                        month=event.month,
                        day=event.day,
                        event_name=event.get_display_name(for_year=calendar.year)
                    )
                    applied_count += 1
                elif combine_events and not existing.image:
                    # Add to existing event if combining is enabled and no image yet
                    existing.add_additional_event(event)
                    combined_count += 1
                else:
                    skipped_count += 1

        message = f'Applied {applied_count} new events to the calendar.'
        if combined_count > 0:
            message += f' Combined {combined_count} events with existing dates.'
        if skipped_count > 0:
            message += f' Skipped {skipped_count} dates with existing events.'

        messages.success(request, message)
        return redirect('calendars:calendar_detail', pk=calendar.id)


@login_required
def get_master_events_json(request):
    """API endpoint to get master events for the event modal"""
    events = EventMaster.objects.filter(user=request.user)

    # Filter by search query if provided
    search = request.GET.get('search')
    if search:
        events = events.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search)
        )

    # Filter by month/day if provided
    month = request.GET.get('month')
    day = request.GET.get('day')
    if month and day:
        events = events.filter(month=int(month), day=int(day))

    # Get calendar year if provided (for year calculations)
    calendar_year = request.GET.get('year')
    if calendar_year:
        calendar_year = int(calendar_year)

    events_data = []
    for event in events[:20]:  # Limit to 20 results
        events_data.append({
            'id': event.id,
            'name': event.name,
            'display_name': event.get_display_name(for_year=calendar_year) if calendar_year else event.name,
            'month': event.month,
            'day': event.day,
            'year_occurred': event.year_occurred,
            'groups': event.groups,
            'description': event.description
        })

    return JsonResponse({'events': events_data})


class ExportMasterEventsView(LoginRequiredMixin, View):
    """Export master events to CSV or JSON format"""

    def get(self, request):
        format = request.GET.get('format', 'csv')
        events = EventMaster.objects.filter(user=request.user)

        if format == 'json':
            # Export as JSON
            data = []
            for event in events:
                data.append({
                    'name': event.name,
                    'event_type': event.event_type,
                    'month': event.month,
                    'day': event.day,
                    'year_occurred': event.year_occurred,
                    'groups': event.groups,
                    'description': event.description
                })

            response = HttpResponse(
                json.dumps(data, indent=2),
                content_type='application/json'
            )
            response['Content-Disposition'] = 'attachment; filename="master_events.json"'
        else:
            # Export as CSV
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="master_events.csv"'

            writer = csv.writer(response)
            writer.writerow(['Name', 'Event Type', 'Month', 'Day', 'Year Occurred', 'Groups', 'Description'])

            for event in events:
                writer.writerow([
                    event.name,
                    event.event_type,
                    event.month,
                    event.day,
                    event.year_occurred or '',
                    event.groups,
                    event.description
                ])

        return response


class ImportMasterEventsView(LoginRequiredMixin, View):
    """Import master events from CSV or JSON file"""

    def get(self, request):
        return render(request, 'calendars/import_master_events.html')

    def post(self, request):
        file = request.FILES.get('import_file')
        if not file:
            messages.error(request, 'Please select a file to import')
            return redirect('calendars:import_master_events')

        file_name = file.name.lower()
        imported_count = 0
        skipped_count = 0
        error_count = 0

        try:
            if file_name.endswith('.json'):
                # Import JSON
                content = file.read().decode('utf-8')
                data = json.loads(content)

                for item in data:
                    try:
                        # Check if event already exists
                        existing = EventMaster.objects.filter(
                            user=request.user,
                            name=item['name'],
                            month=item['month'],
                            day=item['day']
                        ).first()

                        if not existing:
                            EventMaster.objects.create(
                                user=request.user,
                                name=item['name'],
                                event_type=item.get('event_type', 'custom'),
                                month=item['month'],
                                day=item['day'],
                                year_occurred=item.get('year_occurred'),
                                groups=item.get('groups', ''),
                                description=item.get('description', '')
                            )
                            imported_count += 1
                        else:
                            skipped_count += 1
                    except Exception as e:
                        error_count += 1

            elif file_name.endswith('.csv'):
                # Import CSV
                content = file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(content)

                for row in reader:
                    try:
                        # Check if event already exists
                        existing = EventMaster.objects.filter(
                            user=request.user,
                            name=row['Name'],
                            month=int(row['Month']),
                            day=int(row['Day'])
                        ).first()

                        if not existing:
                            year_occurred = None
                            if row.get('Year Occurred') and row['Year Occurred'].strip():
                                year_occurred = int(row['Year Occurred'])

                            EventMaster.objects.create(
                                user=request.user,
                                name=row['Name'],
                                event_type=row.get('Event Type', 'custom'),
                                month=int(row['Month']),
                                day=int(row['Day']),
                                year_occurred=year_occurred,
                                groups=row.get('Groups', ''),
                                description=row.get('Description', '')
                            )
                            imported_count += 1
                        else:
                            skipped_count += 1
                    except Exception as e:
                        error_count += 1
            else:
                messages.error(request, 'Please upload a CSV or JSON file')
                return redirect('calendars:import_master_events')

            message = f'Successfully imported {imported_count} events.'
            if skipped_count > 0:
                message += f' Skipped {skipped_count} duplicate events.'
            if error_count > 0:
                message += f' Failed to import {error_count} events due to errors.'

            messages.success(request, message)

        except Exception as e:
            messages.error(request, f'Error importing file: {str(e)}')

        return redirect('calendars:master_events')


class BulkAddToMasterListView(LoginRequiredMixin, View):
    """Bulk add calendar events to master event list"""

    def get(self, request, calendar_id):
        from .models import Calendar
        calendar = get_object_or_404(Calendar, id=calendar_id, user=request.user)

        # Get events not linked to master events
        unlinked_events = calendar.events.filter(master_event__isnull=True)

        context = {
            'calendar': calendar,
            'unlinked_events': unlinked_events
        }
        return render(request, 'calendars/bulk_add_to_master_list.html', context)

    def post(self, request, calendar_id):
        from .models import Calendar, EventMaster
        calendar = get_object_or_404(Calendar, id=calendar_id, user=request.user)

        selected_event_ids = request.POST.getlist('selected_events')
        default_event_type = request.POST.get('default_event_type', 'custom')
        default_groups = request.POST.get('default_groups', '')

        added_count = 0
        skipped_count = 0

        for event_id in selected_event_ids:
            try:
                event = calendar.events.get(id=event_id, master_event__isnull=True)

                # Check if master event already exists with same name/date
                existing_master = EventMaster.objects.filter(
                    user=request.user,
                    name__iexact=event.event_name,
                    month=event.month,
                    day=event.day
                ).first()

                if not existing_master:
                    # Create new master event
                    master_event = EventMaster.objects.create(
                        user=request.user,
                        name=event.event_name,
                        event_type=default_event_type,
                        month=event.month,
                        day=event.day,
                        groups=default_groups
                    )

                    # Link calendar event to master event
                    event.master_event = master_event
                    event.save()

                    added_count += 1
                else:
                    # Link to existing master event
                    event.master_event = existing_master
                    event.save()
                    added_count += 1

            except Exception as e:
                skipped_count += 1

        message = f'Added {added_count} events to master list.'
        if skipped_count > 0:
            message += f' Skipped {skipped_count} events due to errors.'

        messages.success(request, message)
        return redirect('calendars:calendar_detail', pk=calendar.id)


class AddEventToMasterListView(LoginRequiredMixin, View):
    """Add a single calendar event to the master event list"""

    def get(self, request, event_id):
        from .models import Calendar, CalendarEvent
        from .forms import AddEventToMasterListForm

        event = get_object_or_404(CalendarEvent, id=event_id, calendar__user=request.user)

        # Check if event is already linked to a master event
        if event.master_event:
            messages.info(request, f"This event is already linked to master event '{event.master_event.event_name}'.")
            return redirect('calendars:edit_event', event_id=event.id)

        form = AddEventToMasterListForm(user=request.user, event=event)

        context = {
            'event': event,
            'form': form
        }
        return render(request, 'calendars/add_event_to_master_list.html', context)

    def post(self, request, event_id):
        from .models import Calendar, CalendarEvent, EventMaster
        from .forms import AddEventToMasterListForm

        event = get_object_or_404(CalendarEvent, id=event_id, calendar__user=request.user)

        # Check if event is already linked to a master event
        if event.master_event:
            messages.info(request, f"This event is already linked to master event '{event.master_event.event_name}'.")
            return redirect('calendars:edit_event', event_id=event.id)

        form = AddEventToMasterListForm(request.POST, user=request.user, event=event)

        if form.is_valid():
            master_event_name = form.cleaned_data['master_event_name']
            event_type = form.cleaned_data['event_type']
            birth_year = form.cleaned_data.get('birth_year')
            anniversary_year = form.cleaned_data.get('anniversary_year')
            event_group = form.cleaned_data.get('event_group')

            # Determine the year_occurred based on event type
            final_year_occurred = None
            if event_type == 'birthday' and birth_year:
                final_year_occurred = birth_year
            elif event_type == 'anniversary' and anniversary_year:
                final_year_occurred = anniversary_year

            # Convert event group to string for groups field
            groups_str = ""
            if event_group:
                groups_str = event_group.name

            # Check if master event already exists with this name and date
            existing_master = EventMaster.objects.filter(
                user=request.user,
                name__iexact=master_event_name,
                month=event.month,
                day=event.day
            ).first()

            if existing_master:
                # Link to existing master event
                event.master_event = existing_master
                event.save()
                messages.success(request, f'Event linked to existing master event: {existing_master.name}')
            else:
                # Create new master event
                master_event = EventMaster.objects.create(
                    user=request.user,
                    name=master_event_name,
                    event_type=event_type,
                    month=event.month,
                    day=event.day,
                    year_occurred=final_year_occurred,
                    groups=groups_str
                )

                # Link calendar event to new master event
                event.master_event = master_event
                event.save()

                messages.success(request, f'Event "{master_event_name}" added to master list and linked!')

            return redirect('calendars:edit_event', event_id=event.id)

        # Form is not valid, render with errors
        context = {
            'event': event,
            'form': form
        }
        return render(request, 'calendars/add_event_to_master_list.html', context)


class SettingsView(LoginRequiredMixin, TemplateView):
    """Central settings page with links to all user configuration options"""
    template_name = 'calendars/settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get counts for each section
        context.update({
            'event_groups_count': EventGroup.objects.filter(user=self.request.user).count(),
            'master_events_count': EventMaster.objects.filter(user=self.request.user).count(),
            'shared_calendars_count': Calendar.objects.filter(
                shares__shared_with=self.request.user
            ).count(),
        })

        return context
