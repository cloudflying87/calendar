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
import os
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
    form_class = None  # Will be set dynamically
    success_url = reverse_lazy('calendars:master_events')

    def get_form_class(self):
        from .forms import MasterEventForm
        return MasterEventForm

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
    form_class = None  # Will be set dynamically

    def get_form_class(self):
        from .forms import MasterEventForm
        return MasterEventForm

    def get_queryset(self):
        return EventMaster.objects.filter(user=self.request.user)

    def get_success_url(self):
        # Preserve the page parameter from the request
        page = self.request.GET.get('page') or self.request.POST.get('page')
        if page:
            return f"{reverse('calendars:master_events')}?page={page}"
        return reverse('calendars:master_events')

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


class MasterEventImageUploadView(LoginRequiredMixin, View):
    """View to handle inline image upload for master events - redirects to crop workflow"""

    def post(self, request, pk):
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"Master event image upload started - Event ID: {pk}, User: {request.user.username}")

        event = get_object_or_404(EventMaster, pk=pk, user=request.user)

        # Store page parameter for later redirect
        page = request.POST.get('page')
        if page:
            request.session['master_events_page'] = page

        if 'image' not in request.FILES:
            logger.warning(f"Master event image upload failed - No image provided for Event ID: {pk}")
            return JsonResponse({'success': False, 'error': 'No image provided'})

        # Store the uploaded image temporarily
        from django.core.files.storage import default_storage
        import uuid
        import os

        uploaded_file = request.FILES['image']

        # Create a unique filename for temporary storage
        file_extension = os.path.splitext(uploaded_file.name)[1]
        temp_filename = f"temp_master_event_{uuid.uuid4()}{file_extension}"
        temp_path = default_storage.save(f"temp/{temp_filename}", uploaded_file)

        # Return the crop URL instead of saving directly
        crop_url = f"/calendars/master-events/{pk}/crop-photo/?temp_image={temp_filename}"

        logger.info(f"Master event image upload successful - Event ID: {pk}, Temp file: {temp_filename}")

        return JsonResponse({
            'success': True,
            'redirect_to_crop': True,
            'crop_url': crop_url
        })


class MasterEventRemoveImageView(LoginRequiredMixin, View):
    """Remove image from a master event"""
    def post(self, request, pk):
        event = get_object_or_404(EventMaster, pk=pk, user=request.user)

        # Delete the image file
        if event.image:
            try:
                if os.path.exists(event.image.path):
                    os.remove(event.image.path)
            except OSError:
                pass

        # Clear the image field
        event.image = None
        event.save()

        messages.success(request, 'Photo removed successfully!')
        return redirect('calendars:master_event_edit', pk=event.pk)


class DeleteAllMasterEventsView(LoginRequiredMixin, View):
    """View to delete all master events for a user"""

    def get(self, request):
        # Get count of master events for confirmation
        event_count = EventMaster.objects.filter(user=request.user).count()

        # Get count of linked calendar events that would be affected
        linked_events_count = CalendarEvent.objects.filter(
            master_event__user=request.user,
            master_event__isnull=False
        ).count()

        context = {
            'event_count': event_count,
            'linked_events_count': linked_events_count
        }
        return render(request, 'calendars/delete_all_master_events.html', context)

    def post(self, request):
        confirmation = request.POST.get('confirmation')

        if confirmation != 'DELETE ALL MASTER EVENTS':
            messages.error(request, 'You must type "DELETE ALL MASTER EVENTS" exactly to confirm.')
            return redirect('calendars:delete_all_master_events')

        # Get counts before deletion
        event_count = EventMaster.objects.filter(user=request.user).count()

        # First, unlink all calendar events from master events
        CalendarEvent.objects.filter(
            master_event__user=request.user,
            master_event__isnull=False
        ).update(master_event=None)

        # Then delete all master events
        EventMaster.objects.filter(user=request.user).delete()

        messages.success(
            request,
            f'Successfully deleted {event_count} master events. Calendar events have been unlinked but preserved.'
        )
        return redirect('calendars:master_events')


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
        show_age_numbers = request.POST.get('show_age_numbers') == 'true'
        image_combination_layout = request.POST.get('image_combination_layout', 'auto')

        preferences.add_to_master_list = add_to_master
        preferences.default_groups = default_groups
        preferences.show_age_numbers = show_age_numbers
        preferences.image_combination_layout = image_combination_layout
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
        import calendar as cal
        calendar = get_object_or_404(Calendar, id=calendar_id, user=request.user)
        selected_groups = request.POST.getlist('groups')
        combine_events = request.POST.get('combine_events', False) == 'true'
        overwrite_events = request.POST.get('overwrite_events', False) == 'true'

        applied_count = 0
        combined_count = 0
        skipped_count = 0
        overwritten_count = 0
        skipped_events = []  # Track which events were skipped
        combined_events = []  # Track which events were combined
        overwritten_events = []  # Track which events were overwritten

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
                    calendar_event = CalendarEvent.objects.create(
                        calendar=calendar,
                        master_event=event,
                        month=event.month,
                        day=event.day,
                        event_name=event.get_display_name(for_year=calendar.year, user=request.user)
                    )

                    # Copy image from master event if it has one
                    if event.image:
                        from django.core.files.base import ContentFile
                        import os

                        # Read the original image
                        with event.image.open('rb') as f:
                            image_content = f.read()

                        # Create a new file with a unique name
                        original_name = os.path.basename(event.image.name)
                        name, ext = os.path.splitext(original_name)
                        new_name = f"{name}_{calendar.year}_{calendar_event.id}{ext}"

                        # Save the image to the calendar event
                        calendar_event.image.save(
                            new_name,
                            ContentFile(image_content),
                            save=True
                        )

                    applied_count += 1
                elif overwrite_events:
                    # Overwrite existing event
                    month_name = cal.month_name[event.month]
                    overwritten_events.append(f"{month_name} {event.day}: {existing.event_name} → {event.name}")

                    # Delete old image if exists
                    if existing.image:
                        try:
                            existing.image.delete()
                        except:
                            pass

                    # Update existing event
                    existing.master_event = event
                    existing.event_name = event.get_display_name(for_year=calendar.year, user=request.user)

                    # Copy image from master event if it has one
                    if event.image:
                        from django.core.files.base import ContentFile
                        import os

                        # Read the original image
                        with event.image.open('rb') as f:
                            image_content = f.read()

                        # Create a new file with a unique name
                        original_name = os.path.basename(event.image.name)
                        name, ext = os.path.splitext(original_name)
                        new_name = f"{name}_{calendar.year}_{existing.id}{ext}"

                        # Save the image to the calendar event
                        existing.image.save(
                            new_name,
                            ContentFile(image_content),
                            save=True
                        )

                    existing.save()
                    overwritten_count += 1
                elif combine_events:
                    # Add to existing event by combining names
                    month_name = cal.month_name[event.month]
                    combined_events.append(f"{month_name} {event.day}: {existing.event_name} + {event.name}")

                    if hasattr(existing, 'add_additional_event'):
                        existing.add_additional_event(event)
                    else:
                        # Manual combine if method doesn't exist
                        if existing.combined_events:
                            existing.combined_events += f" & {event.name}"
                        else:
                            existing.combined_events = f"{existing.event_name} & {event.name}"
                        existing.save()
                    combined_count += 1
                else:
                    # Skip this event
                    month_name = cal.month_name[event.month]
                    skipped_events.append(f"{month_name} {event.day}: {event.name} (existing: {existing.event_name})")
                    skipped_count += 1

        # Build detailed success message
        message_parts = []
        if applied_count > 0:
            message_parts.append(f"✅ Applied {applied_count} new events")
        if overwritten_count > 0:
            message_parts.append(f"🔄 Overwritten {overwritten_count} existing events")
        if combined_count > 0:
            message_parts.append(f"🔗 Combined {combined_count} events with existing dates")
        if skipped_count > 0:
            message_parts.append(f"⏭️ Skipped {skipped_count} dates with existing events")

        if message_parts:
            messages.success(request, '. '.join(message_parts) + '.')

        # Show detailed information about what was skipped/combined/overwritten
        if skipped_events:
            skipped_list = '<br>'.join(skipped_events[:10])  # Show first 10
            if len(skipped_events) > 10:
                skipped_list += f'<br>... and {len(skipped_events) - 10} more'
            messages.info(request, f"📋 Skipped events:<br>{skipped_list}")

        if combined_events:
            combined_list = '<br>'.join(combined_events[:5])  # Show first 5
            if len(combined_events) > 5:
                combined_list += f'<br>... and {len(combined_events) - 5} more'
            messages.info(request, f"🔗 Combined events:<br>{combined_list}")

        if overwritten_events:
            overwritten_list = '<br>'.join(overwritten_events[:5])  # Show first 5
            if len(overwritten_events) > 5:
                overwritten_list += f'<br>... and {len(overwritten_events) - 5} more'
            messages.warning(request, f"🔄 Overwritten events:<br>{overwritten_list}")

        return redirect('calendars:calendar_detail_by_id', calendar_id=calendar.id)


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
            'display_name': event.get_display_name(for_year=calendar_year, user=request.user) if calendar_year else event.name,
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
    """Import master events from CSV or JSON file with smart matching"""

    def detect_event_type(self, event_name):
        """Detect event type based on keywords in the event name (same logic as photo upload)"""
        event_name_lower = event_name.lower()

        # Birthday keywords
        birthday_keywords = ['birthday', 'bday', 'birth day', "b'day", 'born']
        if any(keyword in event_name_lower for keyword in birthday_keywords):
            return 'birthday'

        # Anniversary keywords
        anniversary_keywords = ['anniversary', 'wedding', 'married', 'engagement']
        if any(keyword in event_name_lower for keyword in anniversary_keywords):
            return 'anniversary'

        # Holiday keywords
        holiday_keywords = [
            'christmas', 'thanksgiving', 'easter', 'halloween', 'new year',
            'independence day', 'july 4th', 'memorial day', 'labor day',
            'valentine', 'mother\'s day', 'father\'s day', 'mothers day',
            'fathers day', 'hanukkah', 'kwanzaa', 'diwali', 'passover'
        ]
        if any(keyword in event_name_lower for keyword in holiday_keywords):
            return 'holiday'

        # Appointment keywords
        appointment_keywords = [
            'appointment', 'meeting', 'doctor', 'dentist', 'checkup',
            'visit', 'interview', 'consultation'
        ]
        if any(keyword in event_name_lower for keyword in appointment_keywords):
            return 'appointment'

        # Reminder keywords
        reminder_keywords = ['reminder', 'due', 'deadline', 'payment', 'bill', 'renew']
        if any(keyword in event_name_lower for keyword in reminder_keywords):
            return 'reminder'

        # Default to custom if no keywords match
        return 'custom'

    def get(self, request):
        return render(request, 'calendars/import_master_events.html')

    def post(self, request):
        file = request.FILES.get('import_file')
        if not file:
            messages.error(request, 'Please select a file to import')
            return redirect('calendars:import_master_events')

        file_name = file.name.lower()
        imported_count = 0
        updated_count = 0
        skipped_count = 0
        error_count = 0

        try:
            if file_name.endswith('.json'):
                # Import JSON
                content = file.read().decode('utf-8')
                data = json.loads(content)

                for item in data:
                    try:
                        # Smart matching - check for existing event by name and date
                        existing = EventMaster.objects.filter(
                            user=request.user,
                            name__iexact=item['name'],  # Case-insensitive
                            month=item['month'],
                            day=item['day']
                        ).first()

                        # Auto-detect event type if not provided
                        event_type = item.get('event_type', self.detect_event_type(item['name']))

                        if not existing:
                            # Create new master event
                            EventMaster.objects.create(
                                user=request.user,
                                name=item['name'],
                                event_type=event_type,
                                month=item['month'],
                                day=item['day'],
                                year_occurred=item.get('year_occurred'),
                                groups=item.get('groups', ''),
                                description=item.get('description', '')
                            )
                            imported_count += 1
                        else:
                            # Update existing event with missing information
                            updated = False

                            # Update event type if it's currently 'custom' and we have a better detection
                            if existing.event_type == 'custom' and event_type != 'custom':
                                existing.event_type = event_type
                                updated = True

                            # Update year_occurred if missing
                            if not existing.year_occurred and item.get('year_occurred'):
                                existing.year_occurred = item.get('year_occurred')
                                updated = True

                            # Update description if missing
                            if not existing.description and item.get('description'):
                                existing.description = item.get('description', '')
                                updated = True

                            # Update groups if missing
                            if not existing.groups and item.get('groups'):
                                existing.groups = item.get('groups', '')
                                updated = True

                            if updated:
                                existing.save()
                                updated_count += 1
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
                        # Smart matching - check for existing event by name and date
                        existing = EventMaster.objects.filter(
                            user=request.user,
                            name__iexact=row['Name'],  # Case-insensitive
                            month=int(row['Month']),
                            day=int(row['Day'])
                        ).first()

                        # Auto-detect event type if not provided or if provided type is 'custom'
                        provided_type = row.get('Event Type', '').strip()
                        if not provided_type or provided_type.lower() == 'custom':
                            event_type = self.detect_event_type(row['Name'])
                        else:
                            event_type = provided_type

                        if not existing:
                            # Create new master event
                            year_occurred = None
                            if row.get('Year Occurred') and row['Year Occurred'].strip():
                                year_occurred = int(row['Year Occurred'])

                            EventMaster.objects.create(
                                user=request.user,
                                name=row['Name'],
                                event_type=event_type,
                                month=int(row['Month']),
                                day=int(row['Day']),
                                year_occurred=year_occurred,
                                groups=row.get('Groups', ''),
                                description=row.get('Description', '')
                            )
                            imported_count += 1
                        else:
                            # Update existing event with missing information
                            updated = False

                            # Update event type if it's currently 'custom' and we have a better detection
                            if existing.event_type == 'custom' and event_type != 'custom':
                                existing.event_type = event_type
                                updated = True

                            # Update year_occurred if missing
                            if not existing.year_occurred and row.get('Year Occurred') and row['Year Occurred'].strip():
                                existing.year_occurred = int(row['Year Occurred'])
                                updated = True

                            # Update description if missing
                            if not existing.description and row.get('Description'):
                                existing.description = row.get('Description', '')
                                updated = True

                            # Update groups if missing
                            if not existing.groups and row.get('Groups'):
                                existing.groups = row.get('Groups', '')
                                updated = True

                            if updated:
                                existing.save()
                                updated_count += 1
                            else:
                                skipped_count += 1

                    except Exception as e:
                        error_count += 1
            else:
                messages.error(request, 'Please upload a CSV or JSON file')
                return redirect('calendars:import_master_events')

            # Build intelligent success message
            message_parts = []
            if imported_count > 0:
                message_parts.append(f"✨ {imported_count} new event(s) imported")
            if updated_count > 0:
                message_parts.append(f"🔄 {updated_count} existing event(s) updated with missing information")
            if skipped_count > 0:
                message_parts.append(f"⏭️ {skipped_count} event(s) skipped (no updates needed)")

            if message_parts:
                messages.success(request, '. '.join(message_parts) + '.')

            # Add smart feature notifications
            if imported_count > 0:
                messages.info(request, f"🎯 Smart event type detection applied to new imports.")
            if updated_count > 0:
                messages.info(request, f"🧠 Intelligent matching updated existing events with missing details.")

            if error_count > 0:
                messages.warning(request, f"⚠️ {error_count} event(s) failed to import due to formatting errors.")

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

    def _guess_event_type(self, event_name):
        """Guess event type based on event name"""
        event_name_lower = event_name.lower()

        # Birthday keywords
        if any(keyword in event_name_lower for keyword in ['birthday', 'bday', 'born', 'birth']):
            return 'birthday'

        # Anniversary keywords
        if any(keyword in event_name_lower for keyword in ['anniversary', 'wedding', 'married']):
            return 'anniversary'

        # Holiday keywords
        if any(keyword in event_name_lower for keyword in ['christmas', 'thanksgiving', 'easter', 'halloween', 'new year', 'holiday', 'valentine']):
            return 'holiday'

        # Appointment keywords
        if any(keyword in event_name_lower for keyword in ['appointment', 'meeting', 'doctor', 'dentist', 'visit']):
            return 'appointment'

        # Reminder keywords
        if any(keyword in event_name_lower for keyword in ['reminder', 'remember', 'deadline', 'due']):
            return 'reminder'

        return 'custom'

    def post(self, request, calendar_id):
        from .models import Calendar, EventMaster
        from django.core.files.base import ContentFile
        import os

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
                    # Guess event type if default is custom
                    event_type = default_event_type
                    if default_event_type == 'custom':
                        event_type = self._guess_event_type(event.event_name)

                    # Create new master event
                    master_event = EventMaster.objects.create(
                        user=request.user,
                        name=event.event_name,
                        event_type=event_type,
                        month=event.month,
                        day=event.day,
                        groups=default_groups
                    )

                    # Copy image from calendar event to master event if it exists
                    if event.image:
                        try:
                            # Copy the image file
                            image_content = event.image.read()
                            image_name = os.path.basename(event.image.name)
                            master_event.image.save(
                                image_name,
                                ContentFile(image_content),
                                save=True
                            )
                        except Exception as img_error:
                            # Continue even if image copy fails
                            pass

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
        return redirect('calendars:calendar_detail_by_id', calendar_id=calendar.id)


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

                # Copy image from calendar event to master event if it has one
                if event.image:
                    from django.core.files.base import ContentFile
                    import os

                    # Read the original image
                    with event.image.open('rb') as f:
                        image_content = f.read()

                    # Create a new file with a unique name
                    original_name = os.path.basename(event.image.name)
                    name, ext = os.path.splitext(original_name)
                    new_name = f"master_{name}_{master_event.id}{ext}"

                    # Save the image to the master event
                    master_event.image.save(
                        new_name,
                        ContentFile(image_content),
                        save=True
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


class ManageDuplicateEventsView(LoginRequiredMixin, TemplateView):
    """View to manage duplicate events on the same dates"""
    template_name = 'calendars/manage_duplicate_events.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all calendars for the user
        calendars = Calendar.objects.filter(user=self.request.user)

        # Find duplicate events (events with combined_events or multiple events on same date)
        duplicate_groups = []

        for calendar in calendars:
            # Get events with combined_events
            combined_events = CalendarEvent.objects.filter(
                calendar=calendar,
                combined_events__isnull=False
            ).exclude(combined_events='')

            # Also check for multiple events on same date that aren't combined yet
            from django.db.models import Count
            date_counts = CalendarEvent.objects.filter(
                calendar=calendar
            ).values('month', 'day').annotate(
                count=Count('id')
            ).filter(count__gt=1)

            for combined in combined_events:
                events_list = [e.strip() for e in combined.combined_events.split(' & ')]
                duplicate_groups.append({
                    'calendar': calendar,
                    'date': f"{calendar.year}-{combined.month:02d}-{combined.day:02d}",
                    'month': combined.month,
                    'day': combined.day,
                    'events': events_list,
                    'primary_event': combined,
                    'is_combined': True,
                    'image': combined.image
                })

            # Add uncombined duplicates
            for date_info in date_counts:
                events_on_date = CalendarEvent.objects.filter(
                    calendar=calendar,
                    month=date_info['month'],
                    day=date_info['day'],
                    combined_events__isnull=True
                ) | CalendarEvent.objects.filter(
                    calendar=calendar,
                    month=date_info['month'],
                    day=date_info['day'],
                    combined_events=''
                )

                if events_on_date.count() > 1:
                    events_list = [event.get_display_name() for event in events_on_date]
                    duplicate_groups.append({
                        'calendar': calendar,
                        'date': f"{calendar.year}-{date_info['month']:02d}-{date_info['day']:02d}",
                        'month': date_info['month'],
                        'day': date_info['day'],
                        'events': events_list,
                        'primary_event': events_on_date.first(),
                        'all_events': list(events_on_date),
                        'is_combined': False,
                        'image': events_on_date.first().image if events_on_date.first().image else None
                    })

        context['duplicate_groups'] = duplicate_groups
        context['calendars'] = calendars
        return context

    def post(self, request):
        """Handle duplicate event management actions"""
        action = request.POST.get('action')
        calendar_id = request.POST.get('calendar_id')
        month = request.POST.get('month')
        day = request.POST.get('day')

        calendar = get_object_or_404(Calendar, id=calendar_id, user=request.user)

        if action == 'combine':
            # Combine events on this date
            events = CalendarEvent.objects.filter(
                calendar=calendar,
                month=month,
                day=day
            )

            if events.count() > 1:
                primary_event = events.first()
                event_names = [event.get_display_name() for event in events]

                # Keep the first event and delete the others
                for event in events[1:]:
                    event.delete()

                # Set combined events on the primary event
                primary_event.combined_events = ' & '.join(event_names)
                primary_event.save()

                messages.success(request, f'Combined {len(event_names)} events on {calendar.year}-{month}-{day}')

        elif action == 'separate':
            # Separate combined events back to individual events
            event = CalendarEvent.objects.filter(
                calendar=calendar,
                month=month,
                day=day
            ).first()

            if event and event.combined_events:
                event_names = [e.strip() for e in event.combined_events.split(' & ')]

                # Keep the first event name and clear combined_events
                event.event_name = event_names[0]
                event.combined_events = ''
                event.save()

                # Create new events for the other names
                for name in event_names[1:]:
                    CalendarEvent.objects.create(
                        calendar=calendar,
                        month=month,
                        day=day,
                        event_name=name
                    )

                messages.success(request, f'Separated events on {calendar.year}-{month}-{day}')

        elif action == 'delete_duplicate':
            # Delete a specific duplicate event
            event_id = request.POST.get('event_id')
            event = get_object_or_404(CalendarEvent, id=event_id, calendar__user=request.user)
            event.delete()
            messages.success(request, f'Deleted duplicate event: {event.event_name}')

        return redirect('calendars:manage_duplicates')
