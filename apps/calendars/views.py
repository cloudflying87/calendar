from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, TemplateView
from django.views import View
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.utils import timezone
from .models import Calendar, CalendarEvent, CalendarHeader, GeneratedCalendar, Holiday, HolidayCalculator, CalendarHeaderImage
from .forms import CalendarForm, ImageUploadForm, HeaderUploadForm, EventEditForm, HolidayManagementForm
from .utils import CalendarPDFGenerator
import os
import tempfile
import base64
from PIL import Image
import io
import zipfile
import shutil
from django.utils.text import slugify
from datetime import datetime
import calendar as cal


def get_calendar_or_404(year, user):
    """Helper function to get calendar by year and user, handling multiple objects"""
    try:
        return Calendar.objects.filter(year=year, user=user).latest('created_at')
    except Calendar.DoesNotExist:
        raise Http404("Calendar not found")


class CalendarListView(LoginRequiredMixin, ListView):
    model = Calendar
    template_name = 'calendars/calendar_list.html'
    context_object_name = 'calendars'
    paginate_by = 10

    def get_queryset(self):
        from .permissions import get_user_calendars
        return get_user_calendars(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add permission info for each calendar
        calendars_with_permissions = []
        for calendar in context['calendars']:
            permission = calendar.get_user_permission(self.request.user)
            calendars_with_permissions.append({
                'calendar': calendar,
                'permission': permission,
                'is_owner': permission == 'owner'
            })
        context['calendars_with_permissions'] = calendars_with_permissions
        return context


class CalendarCreateView(LoginRequiredMixin, CreateView):
    model = Calendar
    form_class = CalendarForm
    template_name = 'calendars/calendar_create.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        from .models import CalendarYear

        form.instance.user = self.request.user

        # Create or get CalendarYear
        calendar_name = form.cleaned_data.get('calendar_name') or 'Default'
        calendar_year, created = CalendarYear.objects.get_or_create(
            user=self.request.user,
            year=form.instance.year,
            name=calendar_name
        )

        # Link the calendar to the CalendarYear
        form.instance.calendar_year = calendar_year

        response = super().form_valid(form)

        # Handle copying from another calendar if selected
        copy_from_calendar = form.cleaned_data.get('copy_from_calendar')
        if copy_from_calendar:
            self.copy_calendar_events(copy_from_calendar, self.object)

        return response

    def copy_calendar_events(self, source_calendar, target_calendar):
        """Copy all events and their photos from source to target calendar"""
        from django.core.files.base import ContentFile
        import os

        copied_count = 0

        for event in source_calendar.events.all():
            # Create new event
            new_event = CalendarEvent(
                calendar=target_calendar,
                month=event.month,
                day=event.day,
                event_name=event.event_name,
                original_filename=event.original_filename
            )

            # Copy image if it exists
            if event.image and os.path.exists(event.image.path):
                with open(event.image.path, 'rb') as f:
                    image_content = f.read()

                # Create new file with updated path
                new_filename = f"copy_{event.original_filename}" if event.original_filename else f"copy_{event.image.name}"
                new_event.image.save(
                    new_filename,
                    ContentFile(image_content),
                    save=False
                )

            new_event.save()
            copied_count += 1

        if copied_count > 0:
            messages.success(
                self.request,
                f"Successfully copied {copied_count} events from {source_calendar.year} calendar."
            )

    def get_success_url(self):
        return reverse('calendars:calendar_detail', kwargs={'year': self.object.year})


class CalendarDetailView(LoginRequiredMixin, DetailView):
    model = Calendar
    template_name = 'calendars/calendar_detail.html'
    context_object_name = 'calendar'
    slug_field = 'year'
    slug_url_kwarg = 'year'

    def get_queryset(self):
        from .permissions import get_user_calendars
        return get_user_calendars(self.request.user)

    def get(self, request, *args, **kwargs):
        """Override to handle multiple calendars per year"""
        year = self.kwargs.get('year')
        calendar_name = self.kwargs.get('calendar_name')

        if not calendar_name:
            # Check if there are multiple calendars for this year
            queryset = self.get_queryset()
            calendars = queryset.filter(year=year)

            if calendars.count() > 1:
                # Multiple calendars, show selection page
                from django.shortcuts import render
                return render(request, 'calendars/calendar_select.html', {
                    'calendars': calendars,
                    'year': year
                })

        return super().get(request, *args, **kwargs)

    def get_object(self, queryset=None):
        """Override to handle multiple calendars per year"""
        if queryset is None:
            queryset = self.get_queryset()

        year = self.kwargs.get('year')
        calendar_name = self.kwargs.get('calendar_name')

        if calendar_name:
            # If calendar_name is provided, get specific calendar
            try:
                return queryset.get(year=year, calendar_year__name=calendar_name)
            except Calendar.DoesNotExist:
                from django.http import Http404
                raise Http404("Calendar not found")
        else:
            # If no calendar_name, get the single calendar for this year
            try:
                return queryset.get(year=year)
            except Calendar.MultipleObjectsReturned:
                # This should be handled by the get() method above
                from django.http import Http404
                raise Http404("Multiple calendars found")
            except Calendar.DoesNotExist:
                from django.http import Http404
                raise Http404("Calendar not found")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['events_by_month'] = self.get_events_by_month()
        context['has_header'] = hasattr(self.object, 'header')
        context['generated_calendars'] = self.object.generated_pdfs.all()

        # Add sharing context
        context['user_can_share'] = self.object.can_share(self.request.user)
        context['user_can_edit'] = self.object.can_edit(self.request.user)
        context['user_permission'] = self.object.get_user_permission(self.request.user)

        # Add public sharing URL
        if self.object.is_publicly_shared:
            context['public_share_url'] = self.object.get_public_share_url(self.request)

        return context

    def get_events_by_month(self):
        events_by_month = {}
        for month in range(1, 13):
            events_by_month[month] = self.object.events.filter(month=month).order_by('day')
        return events_by_month


class CalendarSimpleView(LoginRequiredMixin, DetailView):
    """Simplified dashboard view focused on PDF calendar creation workflow"""
    model = Calendar
    template_name = 'calendars/calendar_simple.html'
    context_object_name = 'calendar'
    slug_field = 'year'
    slug_url_kwarg = 'year'

    def get_queryset(self):
        from .permissions import get_user_calendars
        return get_user_calendars(self.request.user)

    def get(self, request, *args, **kwargs):
        """Override to handle multiple calendars per year"""
        year = self.kwargs.get('year')
        calendar_name = self.kwargs.get('calendar_name')

        if not calendar_name:
            # Check if there are multiple calendars for this year
            queryset = self.get_queryset()
            calendars = queryset.filter(year=year)

            if calendars.count() > 1:
                # Multiple calendars, show selection page for simple view
                from django.shortcuts import render
                return render(request, 'calendars/calendar_simple_select.html', {
                    'calendars': calendars,
                    'year': year
                })

        return super().get(request, *args, **kwargs)

    def get_object(self, queryset=None):
        """Override to handle multiple calendars per year"""
        if queryset is None:
            queryset = self.get_queryset()

        year = self.kwargs.get('year')
        calendar_name = self.kwargs.get('calendar_name')

        if calendar_name:
            # If calendar_name is provided, get specific calendar
            try:
                return queryset.get(year=year, calendar_year__name=calendar_name)
            except Calendar.DoesNotExist:
                from django.http import Http404
                raise Http404("Calendar not found")
        else:
            # If no calendar_name, get the single calendar for this year
            try:
                return queryset.get(year=year)
            except Calendar.MultipleObjectsReturned:
                # This should be handled by the get() method above
                from django.http import Http404
                raise Http404("Multiple calendars found")
            except Calendar.DoesNotExist:
                from django.http import Http404
                raise Http404("Calendar not found")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['has_header'] = hasattr(self.object, 'header')
        context['generated_calendars'] = self.object.generated_pdfs.all()

        # Add sharing context
        context['user_can_share'] = self.object.can_share(self.request.user)
        context['user_can_edit'] = self.object.can_edit(self.request.user)
        context['user_permission'] = self.object.get_user_permission(self.request.user)

        return context


class CalendarSimpleByIdView(LoginRequiredMixin, DetailView):
    """Simple view for accessing calendars directly by their ID"""
    model = Calendar
    template_name = 'calendars/calendar_simple.html'
    context_object_name = 'calendar'
    pk_url_kwarg = 'calendar_id'

    def get_queryset(self):
        from .permissions import get_user_calendars
        return get_user_calendars(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['has_header'] = hasattr(self.object, 'header')
        context['generated_calendars'] = self.object.generated_pdfs.all()
        context['user_can_share'] = self.object.can_share(self.request.user)
        context['user_can_edit'] = self.object.can_edit(self.request.user)
        context['user_permission'] = self.object.get_user_permission(self.request.user)
        return context


class CalendarDetailByIdView(LoginRequiredMixin, DetailView):
    """View for accessing calendars directly by their ID"""
    model = Calendar
    template_name = 'calendars/calendar_detail.html'
    context_object_name = 'calendar'
    pk_url_kwarg = 'calendar_id'

    def get_queryset(self):
        from .permissions import get_user_calendars
        return get_user_calendars(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Reuse the same methods from CalendarDetailView
        context['events_by_month'] = self.get_events_by_month()
        context['has_header'] = hasattr(self.object, 'header')
        context['generated_calendars'] = self.object.generated_pdfs.all()
        context['user_can_share'] = self.object.can_share(self.request.user)
        context['shared_with'] = self.object.shares.all() if self.object.can_share(self.request.user) else None

        # Add public sharing URL
        if self.object.is_publicly_shared:
            context['public_share_url'] = self.object.get_public_share_url(self.request)

        return context

    def get_events_by_month(self):
        events_by_month = {}
        for month in range(1, 13):
            events_by_month[month] = self.object.events.filter(month=month).order_by('day')
        return events_by_month


@method_decorator(login_required, name='dispatch')
class BulkCropView(View):
    """View for bulk cropping existing calendar photos"""
    def get(self, request, year):
        calendar = get_calendar_or_404(year, request.user)

        # Get all events with images
        events_with_images = calendar.events.filter(image__isnull=False).order_by('month', 'day')

        if not events_with_images.exists():
            messages.error(request, "No photos found to crop.")
            return redirect('calendars:calendar_detail', year=year)

        # Get current event index from session or start with 0
        current_index = request.session.get('bulk_crop_index', 0)

        # Check if we're done with all photos
        if current_index >= events_with_images.count():
            # Reset and redirect
            request.session.pop('bulk_crop_index', None)
            messages.success(request, "Bulk cropping completed!")
            return redirect('calendars:calendar_detail', year=year)

        current_event = events_with_images[current_index]

        # Store event info for processing
        request.session['bulk_crop_event_id'] = current_event.id
        request.session['bulk_crop_total'] = events_with_images.count()

        return render(request, 'calendars/bulk_crop.html', {
            'calendar': calendar,
            'current_event': current_event,
            'current_index': current_index + 1,  # 1-based for display
            'total_events': events_with_images.count(),
            'progress_percentage': ((current_index) / events_with_images.count()) * 100,
            'year': year,
        })

    def post(self, request, year):
        calendar = get_calendar_or_404(year, request.user)

        action = request.POST.get('action')

        if action == 'skip':
            # Skip current photo and move to next
            current_index = request.session.get('bulk_crop_index', 0)
            request.session['bulk_crop_index'] = current_index + 1
            return redirect('calendars:bulk_crop', year=year)

        elif action == 'finish':
            # User wants to finish bulk cropping
            request.session.pop('bulk_crop_index', None)
            request.session.pop('bulk_crop_event_id', None)
            request.session.pop('bulk_crop_total', None)
            messages.success(request, "Bulk cropping session ended.")
            return redirect('calendars:calendar_detail', year=year)

        elif action == 'crop':
            # Process the crop data
            event_id = request.session.get('bulk_crop_event_id')
            crop_data = request.POST.get('crop_data')

            if not event_id or not crop_data:
                messages.error(request, "Error processing crop data.")
                return redirect('calendars:bulk_crop', year=year)

            try:
                event = CalendarEvent.objects.get(id=event_id, calendar=calendar)

                # Decode base64 image data
                image_data = crop_data.split(',')[1]  # Remove data:image/jpeg;base64, prefix
                image_binary = base64.b64decode(image_data)

                # Create PIL image from binary data
                image = Image.open(io.BytesIO(image_binary))

                # Ensure it's RGB
                if image.mode in ('RGBA', 'LA', 'P'):
                    image = image.convert('RGB')

                # Save cropped image to a temporary file with higher quality
                temp_cropped = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                image.save(temp_cropped.name, 'JPEG', quality=95, optimize=True)
                temp_cropped.close()

                # Create Django file from cropped image
                with open(temp_cropped.name, 'rb') as f:
                    from django.core.files.base import ContentFile
                    cropped_django_file = ContentFile(f.read(), name=f"cropped_{event.original_filename or 'image.jpg'}")

                # Update event with new cropped image
                event.image = cropped_django_file
                event.save()

                # Clean up temporary file
                try:
                    if os.path.exists(temp_cropped.name):
                        os.unlink(temp_cropped.name)
                except OSError:
                    pass

                # Move to next photo
                current_index = request.session.get('bulk_crop_index', 0)
                request.session['bulk_crop_index'] = current_index + 1

                messages.success(request, f"Photo cropped for '{event.event_name}'.")
                return redirect('calendars:bulk_crop', year=year)

            except Exception as e:
                messages.error(request, f"Error processing cropped image: {str(e)}")
                return redirect('calendars:bulk_crop', year=year)

        else:
            messages.error(request, "Invalid action.")
            return redirect('calendars:bulk_crop', year=year)


@method_decorator(login_required, name='dispatch')
class ImageUploadView(View):
    def detect_event_type(self, event_name):
        """Detect event type based on keywords in the event name"""
        event_name_lower = event_name.lower()

        # Birthday keywords
        birthday_keywords = ['birthday', 'bday', 'birth day', "b'day", 'born']
        has_birthday = any(keyword in event_name_lower for keyword in birthday_keywords)

        # Anniversary keywords
        anniversary_keywords = ['anniversary', 'wedding', 'married', 'engagement']
        has_anniversary = any(keyword in event_name_lower for keyword in anniversary_keywords)

        # If both birthday and anniversary keywords are present, it's ambiguous - keep as custom
        if has_birthday and has_anniversary:
            return 'custom'

        # Single type detection
        if has_birthday:
            return 'birthday'

        if has_anniversary:
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

    def clean_event_name(self, event_name):
        """Clean event name by removing suffixes after apostrophes (e.g., 's Birthday, 's Anniversary)"""
        # Find the first apostrophe and remove everything after it
        if "'" in event_name:
            event_name = event_name.split("'")[0].strip()

        return event_name

    def get(self, request, year):
        calendar = get_calendar_or_404(year, request.user)
        form = ImageUploadForm()
        return render(request, 'calendars/image_upload.html', {
            'calendar': calendar,
            'form': form
        })

    def post(self, request, year):
        calendar = get_calendar_or_404(year, request.user)
        form = ImageUploadForm(request.POST, request.FILES)

        if form.is_valid():
            uploaded_files = request.FILES.getlist('images')

            # Debug: Check if we actually got files
            if not uploaded_files:
                messages.error(request, "No files were uploaded. Please select files before submitting.")
                return redirect('calendars:image_upload', year=year)

            messages.info(request, f"Processing {len(uploaded_files)} files...")
            created_events = []
            errors = []
            duplicate_dates = []

            # Get user preferences for master events
            from .models import UserEventPreferences, EventMaster
            preferences, created = UserEventPreferences.objects.get_or_create(user=request.user)

            # Process all files as bulk upload (no cropping)
            for uploaded_file in uploaded_files:
                try:
                    # Debug: Log the filename being processed
                    print(f"Processing file: {uploaded_file.name}")

                    # Copy the uploaded file to ensure it's available during processing
                    from django.core.files.base import ContentFile
                    import tempfile

                    # Read the file content immediately while it's available
                    uploaded_file.seek(0)  # Ensure we're at the beginning
                    file_content = uploaded_file.read()
                    uploaded_file.seek(0)  # Reset for potential later use

                    # Create a new ContentFile with the data
                    safe_file = ContentFile(file_content, name=uploaded_file.name)

                    # Parse filename to extract date and event name
                    parsed_data = CalendarEvent.parse_filename(uploaded_file.name)

                    if parsed_data:
                        month, day, event_name = parsed_data
                        image_added_to_master = False
                        auto_created_master = False
                        event_type_updated = False

                        # Clean the event name by removing text after apostrophes
                        cleaned_event_name = self.clean_event_name(event_name)

                        # Auto-detect event type based on the original event name (before cleaning)
                        detected_event_type = self.detect_event_type(event_name)

                        # Check if matching master event exists (using both original and cleaned names)
                        master_event = EventMaster.objects.filter(
                            user=request.user,
                            name__iexact=event_name,
                            month=month,
                            day=day
                        ).first()

                        # If not found, try with cleaned name
                        if not master_event:
                            master_event = EventMaster.objects.filter(
                                user=request.user,
                                name__iexact=cleaned_event_name,
                                month=month,
                                day=day
                            ).first()

                        # Get display name if master event exists
                        display_name = event_name
                        if master_event:
                            display_name = master_event.get_display_name(for_year=calendar.year, user=request.user)

                            # Update master event with new information
                            updates = {}

                            # If master event exists but has no image, add the image
                            if not master_event.image:
                                updates['image'] = safe_file
                                image_added_to_master = True

                            # Update event type if it's currently 'custom' and we detected a specific type
                            if master_event.event_type == 'custom' and detected_event_type != 'custom':
                                updates['event_type'] = detected_event_type
                                event_type_updated = True

                            # Update the name to the cleaned version if it's different
                            if master_event.name != cleaned_event_name and detected_event_type != 'custom':
                                updates['name'] = cleaned_event_name

                            # Save updates if any
                            if updates:
                                for field, value in updates.items():
                                    setattr(master_event, field, value)
                                master_event.save(update_fields=list(updates.keys()))

                        # Check if events already exist for this date
                        existing_events = CalendarEvent.get_events_for_date(calendar, month, day)

                        if existing_events.exists():
                            # Create a new event (allow multiple events on same day)
                            event = CalendarEvent(
                                calendar=calendar,
                                month=month,
                                day=day,
                                event_name=display_name,
                                master_event=master_event,
                                image=safe_file,
                                full_image=safe_file,  # For bulk uploads, the same image is used for both
                                original_filename=uploaded_file.name
                            )
                            event.save(skip_resize=True)  # Skip auto-resize for bulk uploads
                            created = True
                            duplicate_dates.append(f"{calendar.year}-{month:02d}-{day:02d}")
                        else:
                            # Create new event
                            event = CalendarEvent(
                                calendar=calendar,
                                month=month,
                                day=day,
                                event_name=display_name,
                                master_event=master_event,
                                image=safe_file,
                                full_image=safe_file,  # For bulk uploads, the same image is used for both
                                original_filename=uploaded_file.name
                            )
                            event.save(skip_resize=True)  # Skip auto-resize for bulk uploads
                            created = True
                        created_events.append(event)

                        # Handle adding to master list based on preferences
                        if not master_event and preferences.add_to_master_list == 'always':
                            # Auto-create master event with detected type and cleaned name
                            new_master_event = EventMaster.objects.create(
                                user=request.user,
                                name=cleaned_event_name,  # Use cleaned name for master event
                                month=month,
                                day=day,
                                event_type=detected_event_type,
                                groups=preferences.default_groups,
                                image=safe_file  # Save the image to the master event
                            )

                            # Update the calendar event to link to the new master event
                            event.master_event = new_master_event
                            event.save(update_fields=['master_event'], skip_resize=True)
                            auto_created_master = True

                        # Add tracking flags to the event for notifications
                        event._auto_created_master = auto_created_master
                        event._image_added_to_master = image_added_to_master
                        event._event_type_updated = event_type_updated
                    else:
                        errors.append(f"Could not parse filename: {uploaded_file.name}. Use format: MMDD eventname.jpg")

                except Exception as e:
                    errors.append(f"Error processing {uploaded_file.name}: {str(e)}")

            # Resize images for successfully created events after they've been saved
            if created_events:
                resize_errors = []
                auto_created_count = 0
                auto_typed_count = 0
                image_added_count = 0

                for event in created_events:
                    try:
                        event.resize_image()
                    except Exception as e:
                        resize_errors.append(f"Error resizing {event.original_filename}: {str(e)}")

                # Count intelligent features used
                event_type_updated_count = 0
                for event in created_events:
                    if hasattr(event, '_auto_created_master') and event._auto_created_master:
                        auto_created_count += 1
                        if event.master_event and event.master_event.event_type != 'custom':
                            auto_typed_count += 1
                    elif event.master_event and hasattr(event, '_image_added_to_master') and event._image_added_to_master:
                        image_added_count += 1

                    # Count event type updates
                    if hasattr(event, '_event_type_updated') and event._event_type_updated:
                        event_type_updated_count += 1

                messages.success(request, f"Successfully uploaded {len(created_events)} images.")

                # Add intelligent feature notifications
                if auto_created_count > 0:
                    messages.info(request, f"✨ {auto_created_count} master event(s) automatically created with smart type detection.")

                if image_added_count > 0:
                    messages.info(request, f"🖼️ {image_added_count} existing master event(s) updated with new images.")

                if event_type_updated_count > 0:
                    messages.info(request, f"🏷️ {event_type_updated_count} existing master event(s) updated with detected event types.")

                if resize_errors:
                    for error in resize_errors:
                        messages.warning(request, error)

            if duplicate_dates:
                messages.warning(request, f"Multiple events added to these dates: {', '.join(set(duplicate_dates))}")

            if errors:
                for error in errors:
                    messages.error(request, error)

            return redirect('calendars:calendar_detail', year=year)
        else:
            # Form is not valid - show errors
            messages.error(request, f"Form validation failed: {form.errors}")

        return render(request, 'calendars/image_upload.html', {
            'calendar': calendar,
            'form': form
        })


@method_decorator(login_required, name='dispatch')
class HeaderUploadView(View):
    def get(self, request, year):
        calendar = get_calendar_or_404(year, request.user)
        form = HeaderUploadForm()
        return render(request, 'calendars/header_upload.html', {
            'calendar': calendar,
            'form': form
        })

    def post(self, request, year):
        calendar = get_calendar_or_404(year, request.user)
        form = HeaderUploadForm(request.POST, request.FILES)

        if form.is_valid():
            header, created = CalendarHeader.objects.update_or_create(
                calendar=calendar,
                defaults={
                    'document': form.cleaned_data['document'],
                    'january_page': form.cleaned_data['january_page']
                }
            )

            action = "uploaded" if created else "updated"
            messages.success(request, f"Header document {action} successfully.")
            return redirect('calendars:calendar_detail', year=year)

        return render(request, 'calendars/header_upload.html', {
            'calendar': calendar,
            'form': form
        })


@method_decorator(login_required, name='dispatch')
class GenerateCalendarView(View):
    def post(self, request, year):
        calendar = get_calendar_or_404(year, request.user)
        generation_type = request.POST.get('generation_type', 'calendar_only')
        action = request.POST.get('action', 'generate')

        # Check if a calendar of this type already exists
        existing_calendar = GeneratedCalendar.objects.filter(
            calendar=calendar,
            generation_type=generation_type
        ).first()

        # If existing calendar found and no action specified, ask user what to do
        if existing_calendar and action == 'generate':
            return render(request, 'calendars/pdf_generation_conflict.html', {
                'calendar': calendar,
                'generation_type': generation_type,
                'generation_type_display': dict(GeneratedCalendar._meta.get_field('generation_type').choices)[generation_type],
                'existing_calendar': existing_calendar,
                'year': year
            })

        try:
            generator = CalendarPDFGenerator(calendar)

            if generation_type == 'calendar_only':
                pdf_file = generator.generate_calendar_only()
            elif generation_type == 'with_headers':
                pdf_file = generator.generate_combined_spread()
            elif generation_type == 'combined':
                pdf_file = generator.generate_with_headers()
            else:
                messages.error(request, "Invalid generation type.")
                return redirect('calendars:calendar_detail', year=year)

            # Handle the action based on user choice
            if action == 'overwrite' and existing_calendar:
                # Delete the old PDF file if it exists
                if existing_calendar.pdf_file and os.path.exists(existing_calendar.pdf_file.path):
                    try:
                        os.unlink(existing_calendar.pdf_file.path)
                    except OSError:
                        pass  # File might already be deleted

                # Update existing record
                existing_calendar.pdf_file = pdf_file
                existing_calendar.created_at = timezone.now()
                existing_calendar.save()
                generated_calendar = existing_calendar
                action_message = "overwritten"

            elif action == 'create_new':
                # Remove unique constraint temporarily by deleting existing
                if existing_calendar:
                    if existing_calendar.pdf_file and os.path.exists(existing_calendar.pdf_file.path):
                        try:
                            os.unlink(existing_calendar.pdf_file.path)
                        except OSError:
                            pass
                    existing_calendar.delete()

                # Create new record
                generated_calendar = GeneratedCalendar.objects.create(
                    calendar=calendar,
                    pdf_file=pdf_file,
                    generation_type=generation_type
                )
                action_message = "created"

            else:
                # First time generation
                generated_calendar = GeneratedCalendar.objects.create(
                    calendar=calendar,
                    pdf_file=pdf_file,
                    generation_type=generation_type
                )
                action_message = "generated"

            messages.success(request, f"Calendar {action_message} successfully! Type: {generated_calendar.get_generation_type_display()}")

        except Exception as e:
            messages.error(request, f"Error generating calendar: {str(e)}")

        return redirect('calendars:calendar_detail', year=year)


@method_decorator(login_required, name='dispatch')
class DownloadCalendarView(View):
    def get(self, request, year, generation_type):
        calendar = get_calendar_or_404(year, request.user)

        try:
            generated_calendar = calendar.generated_pdfs.filter(
                generation_type=generation_type
            ).latest('created_at')

            if os.path.exists(generated_calendar.pdf_file.path):
                return FileResponse(
                    open(generated_calendar.pdf_file.path, 'rb'),
                    as_attachment=True,
                    filename=f"calendar_{year}_{generation_type}.pdf"
                )
            else:
                messages.error(request, "PDF file not found.")

        except GeneratedCalendar.DoesNotExist:
            messages.error(request, "No generated calendar found. Please generate one first.")

        return redirect('calendars:calendar_detail', year=year)


@method_decorator(login_required, name='dispatch')
class EditEventView(View):
    def get(self, request, event_id):
        event = get_object_or_404(CalendarEvent, id=event_id, calendar__user=request.user)
        form = EventEditForm(instance=event)

        # Get calendars that use this master event (if it has one)
        calendars_using_event = None
        if event.master_event:
            calendars_using_event = Calendar.objects.filter(
                events__master_event=event.master_event,
                user=request.user
            ).distinct()

        return render(request, 'calendars/edit_event.html', {
            'event': event,
            'calendar': event.calendar,
            'form': form,
            'calendars_using_event': calendars_using_event
        })

    def post(self, request, event_id):
        event = get_object_or_404(CalendarEvent, id=event_id, calendar__user=request.user)
        form = EventEditForm(request.POST, instance=event)

        if form.is_valid():
            form.save()
            messages.success(request, f"Event '{event.event_name}' updated successfully.")
            return redirect('calendars:calendar_detail', year=event.calendar.year)

        # Get calendars that use this master event (if it has one)
        calendars_using_event = None
        if event.master_event:
            calendars_using_event = Calendar.objects.filter(
                events__master_event=event.master_event,
                user=request.user
            ).distinct()

        return render(request, 'calendars/edit_event.html', {
            'event': event,
            'calendar': event.calendar,
            'form': form,
            'calendars_using_event': calendars_using_event
        })


@method_decorator(login_required, name='dispatch')
class DeleteEventView(View):
    def post(self, request, event_id):
        event = get_object_or_404(CalendarEvent, id=event_id, calendar__user=request.user)
        calendar_year = event.calendar.year
        event_name = event.event_name

        # Delete the event and its associated image
        event.delete()

        messages.success(request, f"Event '{event_name}' deleted successfully.")
        return redirect('calendars:calendar_detail', year=calendar_year)


@method_decorator(login_required, name='dispatch')
class HolidayManagementView(View):
    def get(self, request, calendar_id):
        from .permissions import get_user_calendars
        calendar = get_object_or_404(get_user_calendars(request.user), id=calendar_id)
        form = HolidayManagementForm(calendar=calendar)

        # Calculate actual dates for each holiday
        holiday_dates = {}
        for holiday_code, holiday_name in Holiday.HOLIDAY_CHOICES:
            calculated_date = HolidayCalculator.get_holiday_date(holiday_code, calendar.year)
            if calculated_date:
                holiday_dates[holiday_code] = calculated_date.strftime('%B %d, %Y')
            else:
                holiday_dates[holiday_code] = 'Date calculation error'

        return render(request, 'calendars/holiday_management.html', {
            'calendar': calendar,
            'form': form,
            'holiday_dates': holiday_dates
        })

    def post(self, request, calendar_id):
        from .permissions import get_user_calendars
        calendar = get_object_or_404(get_user_calendars(request.user), id=calendar_id)
        form = HolidayManagementForm(request.POST, request.FILES, calendar=calendar)

        if form.is_valid():
            form.save(calendar)
            messages.success(request, "Holiday selections updated successfully.")
            return redirect('calendars:calendar_detail_by_id', calendar_id=calendar.id)

        # Calculate actual dates for template on form errors
        holiday_dates = {}
        for holiday_code, holiday_name in Holiday.HOLIDAY_CHOICES:
            calculated_date = HolidayCalculator.get_holiday_date(holiday_code, calendar.year)
            if calculated_date:
                holiday_dates[holiday_code] = calculated_date.strftime('%B %d, %Y')
            else:
                holiday_dates[holiday_code] = 'Date calculation error'

        return render(request, 'calendars/holiday_management.html', {
            'calendar': calendar,
            'form': form,
            'holiday_dates': holiday_dates
        })


@method_decorator(login_required, name='dispatch')
class PhotoEditorUploadView(View):
    """New upload view specifically for the photo editor - accepts any filename"""
    def get(self, request, year):
        calendar = get_calendar_or_404(year, request.user)

        # Check if we're editing an existing event
        edit_event_data = request.session.get('edit_event_data')

        # Check if we're editing a master event
        master_event_id = request.GET.get('master_event_id')
        master_event = None
        if master_event_id:
            from .models import EventMaster
            try:
                master_event = EventMaster.objects.get(pk=master_event_id, user=request.user)
                # Store in session for later processing
                request.session['edit_master_event_id'] = master_event_id
            except EventMaster.DoesNotExist:
                pass

        context = {
            'calendar': calendar,
            'edit_event_data': edit_event_data,
            'master_event': master_event,
        }

        return render(request, 'calendars/photo_editor_upload.html', context)

    def post(self, request, year):
        calendar = get_calendar_or_404(year, request.user)

        # Get form data
        photo_mode = request.POST.get('photo_mode', 'single')

        if photo_mode == 'single':
            # Handle single photo upload
            uploaded_file = request.FILES.get('photo')

            if not uploaded_file:
                messages.error(request, "Please select a photo to upload.")
                return redirect('calendars:photo_editor_upload', year=year)

            # Save temporary file for cropping
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            for chunk in uploaded_file.chunks():
                temp_file.write(chunk)
            temp_file.close()

            # Store data in session for the crop view (no date/event data yet)
            request.session['crop_data'] = {
                'temp_path': temp_file.name,
                'original_filename': uploaded_file.name,
                'photo_mode': 'single'
            }

            return redirect('calendars:photo_crop', year=year)

        elif photo_mode == 'multi':
            # Handle multiple photo upload
            uploaded_files = request.FILES.getlist('photos')
            layout = request.POST.get('layout')

            if not uploaded_files:
                messages.error(request, "Please select photos to upload.")
                return redirect('calendars:photo_editor_upload', year=year)

            if not layout:
                messages.error(request, "Please select a layout template.")
                return redirect('calendars:photo_editor_upload', year=year)

            # Validate file count based on layout
            max_files = 2 if layout in ['two-horizontal', 'two-vertical'] else 3
            min_files = 2

            if len(uploaded_files) < min_files or len(uploaded_files) > max_files:
                messages.error(request, f"Please select {min_files}-{max_files} photos for the {layout.replace('-', ' ')} layout.")
                return redirect('calendars:photo_editor_upload', year=year)

            # Save temporary files
            temp_paths = []
            original_filenames = []

            for i, uploaded_file in enumerate(uploaded_files):
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'_photo{i+1}.jpg')
                for chunk in uploaded_file.chunks():
                    temp_file.write(chunk)
                temp_file.close()
                temp_paths.append(temp_file.name)
                original_filenames.append(uploaded_file.name)

            # Store data in session for the multi-crop view
            request.session['multi_crop_data'] = {
                'temp_paths': temp_paths,
                'original_filenames': original_filenames,
                'layout': layout,
                'photo_mode': 'multi',
                'current_photo_index': 0  # Start with first photo
            }

            return redirect('calendars:multi_photo_crop', year=year)

        else:
            messages.error(request, "Invalid photo mode selected.")
            return redirect('calendars:photo_editor_upload', year=year)


@method_decorator(login_required, name='dispatch')
class PhotoCropView(View):
    def get(self, request, year):
        calendar = get_calendar_or_404(year, request.user)

        # Get crop data from session
        crop_data = request.session.get('crop_data')
        if not crop_data:
            messages.error(request, "No image to crop. Please upload an image first.")
            return redirect('calendars:image_upload', year=year)

        # Check if temp file exists
        if not os.path.exists(crop_data['temp_path']):
            messages.error(request, "Temporary image file not found. Please upload again.")
            return redirect('calendars:image_upload', year=year)

        # Create a secure URL for the temporary image
        import uuid
        temp_token = str(uuid.uuid4())

        # Store the temp file path in session with a secure token
        if 'temp_tokens' not in request.session:
            request.session['temp_tokens'] = {}
        request.session['temp_tokens'][temp_token] = crop_data['temp_path']
        request.session.modified = True

        # Create URL that will be served by our secure view
        temp_image_url = f"/calendars/temp-image/{temp_token}/"

        # Check if we have edit event data or crop data
        edit_event_data = request.session.get('edit_event_data')
        master_event_id = request.session.get('edit_master_event_id')
        master_event = None

        if master_event_id:
            # Editing master event
            from .models import EventMaster
            try:
                master_event = EventMaster.objects.get(pk=master_event_id, user=request.user)
                event_date = f"{master_event.month:02d}/{master_event.day:02d}"
                event_name = master_event.name
                month = master_event.month
                day = master_event.day
            except EventMaster.DoesNotExist:
                # Clear invalid session data
                del request.session['edit_master_event_id']
                master_event_id = None
                master_event = None

        if edit_event_data and not master_event_id:
            # Editing existing event - use event data
            event_date = f"{edit_event_data['month']:02d}/{edit_event_data['day']:02d}/{year}"
            event_name = edit_event_data['event_name']
            month = edit_event_data['month']
            day = edit_event_data['day']
        elif 'month' in crop_data and 'day' in crop_data and not master_event_id:
            # Old workflow - has date/event data in crop_data
            event_date = f"{crop_data['month']:02d}/{crop_data['day']:02d}/{year}"
            event_name = crop_data['event_name']
            month = crop_data['month']
            day = crop_data['day']
        elif not master_event_id:
            # New workflow - no date/event data yet
            event_date = "Choose Date"
            event_name = "Enter Event Name"
            month = ''
            day = ''

        return render(request, 'calendars/photo_crop.html', {
            'calendar': calendar,
            'temp_image_url': temp_image_url,
            'temp_image_path': crop_data['temp_path'],
            'original_filename': crop_data['original_filename'],
            'event_name': event_name,
            'month': month,
            'day': day,
            'event_date': event_date,
            'year': year,
            'edit_event_data': edit_event_data,
            'master_event': master_event,
            'is_master_event': bool(master_event),
        })


@method_decorator(login_required, name='dispatch')
class ProcessCropView(View):
    def post(self, request, year):
        calendar = get_calendar_or_404(year, request.user)

        # Check if we're updating a master event
        master_event_id = request.session.get('edit_master_event_id')
        is_master_event = bool(master_event_id)

        # Get form data
        temp_image_path = request.POST.get('temp_image_path')
        original_filename = request.POST.get('original_filename')
        event_name = request.POST.get('event_name')
        month = int(request.POST.get('month'))
        day = int(request.POST.get('day'))
        crop_data = request.POST.get('crop_data')

        if not crop_data:
            messages.error(request, "No crop data received. Please try again.")
            return redirect('calendars:photo_crop', year=year)

        try:
            # Decode base64 image data
            image_data = crop_data.split(',')[1]  # Remove data:image/jpeg;base64, prefix
            image_binary = base64.b64decode(image_data)

            # Create PIL image from binary data
            image = Image.open(io.BytesIO(image_binary))

            # Ensure it's RGB
            if image.mode in ('RGBA', 'LA', 'P'):
                image = image.convert('RGB')

            # Save cropped image to a temporary file with higher quality
            temp_cropped = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            image.save(temp_cropped.name, 'JPEG', quality=95, optimize=True)
            temp_cropped.close()

            # Create Django file from cropped image
            with open(temp_cropped.name, 'rb') as f:
                from django.core.files.base import ContentFile
                cropped_django_file = ContentFile(f.read(), name=f"cropped_{original_filename}")

            # Create Django file from full original image
            full_django_file = None
            if temp_image_path and os.path.exists(temp_image_path):
                with open(temp_image_path, 'rb') as f:
                    full_django_file = ContentFile(f.read(), name=f"full_{original_filename}")
                print(f"DEBUG: Created full_django_file from {temp_image_path}, size: {len(full_django_file.read())} bytes")
                full_django_file.seek(0)  # Reset file pointer after reading for debug
            else:
                print(f"DEBUG: Could not create full_django_file. temp_image_path={temp_image_path}, exists={os.path.exists(temp_image_path) if temp_image_path else False}")

            # Handle master event update if applicable
            if is_master_event:
                from .models import EventMaster
                try:
                    master_event = EventMaster.objects.get(pk=master_event_id, user=request.user)
                    master_event.image = cropped_django_file
                    if full_django_file:
                        master_event.full_image = full_django_file
                    master_event.save()

                    # Clear session data
                    if 'crop_data' in request.session:
                        del request.session['crop_data']
                    if 'edit_master_event_id' in request.session:
                        del request.session['edit_master_event_id']
                    if 'temp_tokens' in request.session:
                        del request.session['temp_tokens']

                    # Clean up temporary files
                    try:
                        if os.path.exists(temp_image_path):
                            os.unlink(temp_image_path)
                        if os.path.exists(temp_cropped.name):
                            os.unlink(temp_cropped.name)
                    except OSError:
                        pass

                    messages.success(request, f"Photo updated successfully for master event '{master_event.name}'!")
                    return redirect('calendars:master_events')

                except EventMaster.DoesNotExist:
                    messages.error(request, "Master event not found.")
                    return redirect('calendars:master_events')

            # Check if events already exist for this date (calendar event logic)
            existing_events = CalendarEvent.get_events_for_date(calendar, month, day)

            if existing_events.exists():
                # Check if we're updating an existing event (coming from edit mode)
                edit_event_data = request.session.get('edit_event_data')
                if edit_event_data and edit_event_data.get('event_id'):
                    # Update the specific event
                    event = CalendarEvent.objects.get(id=edit_event_data['event_id'])
                    event.event_name = event_name
                    event.image = cropped_django_file
                    event.full_image = full_django_file
                    event.original_filename = original_filename
                    event.save()
                    created = False
                else:
                    # Create a new event (allow multiple events on same day)
                    event = CalendarEvent.objects.create(
                        calendar=calendar,
                        month=month,
                        day=day,
                        event_name=event_name,
                        image=cropped_django_file,
                        full_image=full_django_file,
                        original_filename=original_filename
                    )
                    created = True

                    # Notify user about multiple events
                    messages.warning(request, f"Added '{event_name}' to {calendar.year}-{month:02d}-{day:02d}. This date now has {existing_events.count() + 1} events.")
            else:
                # Create new event
                event = CalendarEvent.objects.create(
                    calendar=calendar,
                    month=month,
                    day=day,
                    event_name=event_name,
                    image=cropped_django_file,
                    full_image=full_django_file,
                    original_filename=original_filename
                )
                created = True

            # Clean up temporary files
            try:
                if os.path.exists(temp_image_path):
                    os.unlink(temp_image_path)
                if os.path.exists(temp_cropped.name):
                    os.unlink(temp_cropped.name)
            except OSError:
                pass

            # Clear session data and check for return destination
            edit_event_data = request.session.get('edit_event_data')
            if 'crop_data' in request.session:
                del request.session['crop_data']
            if 'edit_event_data' in request.session:
                del request.session['edit_event_data']
            if 'edit_master_event_id' in request.session:
                del request.session['edit_master_event_id']
            if 'temp_tokens' in request.session:
                del request.session['temp_tokens']

            action = "created" if created else "updated"
            messages.success(request, f"Event '{event_name}' {action} successfully with cropped photo.")

            # Return to event edit page if we were editing an event
            if edit_event_data and edit_event_data.get('return_to_edit'):
                return redirect('calendars:edit_event', event_id=event.id)
            else:
                return redirect('calendars:calendar_detail', year=year)

        except Exception as e:
            messages.error(request, f"Error processing cropped image: {str(e)}")
            return redirect('calendars:photo_crop', year=year)


@method_decorator(login_required, name='dispatch')
class DeleteCalendarView(View):
    def get(self, request, calendar_id):
        from .permissions import get_user_calendars
        calendar = get_object_or_404(get_user_calendars(request.user), id=calendar_id)
        return render(request, 'calendars/delete_calendar.html', {
            'calendar': calendar
        })

    def post(self, request, calendar_id):
        from .permissions import get_user_calendars
        calendar = get_object_or_404(get_user_calendars(request.user), id=calendar_id)
        calendar_year_obj = calendar.calendar_year
        calendar_year = calendar.year

        # Delete all associated files and the calendar
        calendar.delete()

        # Clean up orphaned CalendarYear if no other calendars use it
        if calendar_year_obj:
            # Check if any other calendars reference this CalendarYear
            other_calendars = Calendar.objects.filter(calendar_year=calendar_year_obj)
            if not other_calendars.exists():
                calendar_year_obj.delete()

        messages.success(request, f"Calendar {calendar_year} and all associated files deleted successfully.")
        return redirect('calendars:calendar_list')


@method_decorator(login_required, name='dispatch')
class DeleteGeneratedPDFView(View):
    def post(self, request, pdf_id):
        generated_pdf = get_object_or_404(GeneratedCalendar, id=pdf_id, calendar__user=request.user)
        calendar_year = generated_pdf.calendar.year
        generation_type = generated_pdf.get_generation_type_display()

        # Delete the PDF file and record
        if generated_pdf.pdf_file and os.path.exists(generated_pdf.pdf_file.path):
            try:
                os.remove(generated_pdf.pdf_file.path)
            except OSError:
                pass  # File might already be deleted

        generated_pdf.delete()

        messages.success(request, f"Generated PDF '{generation_type}' deleted successfully.")
        return redirect('calendars:calendar_detail', year=calendar_year)


@method_decorator(login_required, name='dispatch')
class BulkDeleteEventsView(View):
    def post(self, request, calendar_id):
        from .permissions import get_user_calendars
        calendar = get_object_or_404(get_user_calendars(request.user), id=calendar_id)

        selected_event_ids = request.POST.getlist('selected_events')

        if not selected_event_ids:
            messages.warning(request, "No events were selected for deletion.")
            return redirect('calendars:calendar_detail_by_id', calendar_id=calendar.id)

        deleted_count = 0
        for event_id in selected_event_ids:
            try:
                event = calendar.events.get(id=event_id)
                event.delete()
                deleted_count += 1
            except CalendarEvent.DoesNotExist:
                continue

        if deleted_count > 0:
            messages.success(request, f"Successfully deleted {deleted_count} event(s).")
        else:
            messages.warning(request, "No events were deleted.")

        return redirect('calendars:calendar_detail_by_id', calendar_id=calendar.id)


class PublicCalendarView(DetailView):
    """Public view for calendars shared via token - no login required"""
    model = Calendar
    template_name = 'calendars/public_calendar_detail.html'
    context_object_name = 'calendar'
    slug_field = 'public_share_token'
    slug_url_kwarg = 'token'

    def get_queryset(self):
        # Only show publicly shared calendars
        return Calendar.objects.filter(is_publicly_shared=True, public_share_token__isnull=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        calendar = self.object

        # Get events organized by month (similar to private view but simplified)
        events_by_month = {}
        for month in range(1, 13):
            events_by_month[month] = calendar.events.filter(month=month).order_by('day')

        context['events_by_month'] = events_by_month
        context['is_public_view'] = True
        context['calendar_owner'] = calendar.user
        return context


@method_decorator(login_required, name='dispatch')
class EnablePublicShareView(View):
    def post(self, request, calendar_id):
        from .permissions import get_user_calendars
        calendar = get_object_or_404(get_user_calendars(request.user), id=calendar_id)

        if not calendar.can_share(request.user):
            messages.error(request, "You don't have permission to share this calendar.")
            return redirect('calendars:calendar_detail_by_id', calendar_id=calendar.id)

        calendar.generate_public_share_token()
        messages.success(request, "Public sharing enabled! Anyone with the link can now view your calendar.")
        return redirect('calendars:calendar_detail_by_id', calendar_id=calendar.id)


@method_decorator(login_required, name='dispatch')
class DisablePublicShareView(View):
    def post(self, request, calendar_id):
        from .permissions import get_user_calendars
        calendar = get_object_or_404(get_user_calendars(request.user), id=calendar_id)

        if not calendar.can_share(request.user):
            messages.error(request, "You don't have permission to manage sharing for this calendar.")
            return redirect('calendars:calendar_detail_by_id', calendar_id=calendar.id)

        calendar.disable_public_sharing()
        messages.success(request, "Public sharing disabled. The previous link will no longer work.")
        return redirect('calendars:calendar_detail_by_id', calendar_id=calendar.id)


@method_decorator(login_required, name='dispatch')
class DownloadAllPhotosView(View):
    def get(self, request, year):
        calendar = get_calendar_or_404(year, request.user)

        # Get all events with images
        events_with_images = calendar.events.filter(image__isnull=False).order_by('month', 'day')

        if not events_with_images.exists():
            messages.error(request, "No photos found in this calendar.")
            return redirect('calendars:calendar_detail', year=year)

        # Create temporary zip file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_zip:
            with zipfile.ZipFile(tmp_zip, 'w', zipfile.ZIP_DEFLATED) as zip_file:

                # Create events manifest
                events_info = []

                # Group events by month for organization
                current_month = None

                for event in events_with_images:
                    if event.image and os.path.exists(event.image.path):
                        # Create safe filename (flattened - no folders)
                        event_name_safe = slugify(event.event_name)
                        original_ext = os.path.splitext(event.original_filename)[1] if event.original_filename else '.jpg'
                        filename = f"{event.month:02d}{event.day:02d}_{event_name_safe}{original_ext}"

                        # Add photo directly to zip root (no folders)
                        zip_file.write(event.image.path, filename)

                        # Track for CSV data
                        master_event_name = event.master_event.name if event.master_event else ""
                        event_type = event.master_event.get_event_type_display() if event.master_event else ""
                        year_occurred = event.master_event.year_occurred if event.master_event else ""
                        groups = event.master_event.groups if event.master_event else ""

                        events_info.append({
                            'date': f"{event.month:02d}/{event.day:02d}/{year}",
                            'event_name': event.event_name,
                            'filename': filename,
                            'master_event': master_event_name,
                            'event_type': event_type,
                            'year_occurred': year_occurred or "",
                            'groups': groups
                        })

                # Create CSV file for events
                import csv
                import io

                csv_data = []
                csv_data.append(['Date', 'Event Name', 'Filename', 'Master Event', 'Event Type', 'Year Occurred', 'Groups'])

                for event_info in events_info:
                    csv_data.append([
                        event_info['date'],
                        event_info['event_name'],
                        event_info['filename'],
                        event_info['master_event'],
                        event_info['event_type'],
                        event_info['year_occurred'],
                        event_info['groups']
                    ])

                # Create CSV file in memory
                csv_buffer = io.StringIO()
                csv_writer = csv.writer(csv_buffer)
                csv_writer.writerows(csv_data)

                # Add CSV to zip
                zip_file.writestr(f"Calendar-{year}-Events.csv", csv_buffer.getvalue())

                # Create text manifest for backward compatibility
                manifest_content = f"Calendar {year} Photos Export\n"
                manifest_content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                manifest_content += f"Total Photos: {len(events_with_images)}\n"
                manifest_content += "All photos are in the root directory with CSV event list\n\n"
                manifest_content += "File Format: MMDD_eventname.jpg\n"
                manifest_content += f"CSV Format: Calendar-{year}-Events.csv contains full event details\n"

                # Add manifest to zip
                zip_file.writestr("README.txt", manifest_content)

            # Read the zip file
            with open(tmp_zip.name, 'rb') as f:
                zip_content = f.read()

            # Clean up temp file
            os.unlink(tmp_zip.name)

            # Return as download
            response = HttpResponse(zip_content, content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="Calendar-{year}-Photos.zip"'
            return response


@method_decorator(login_required, name='dispatch')
class MasterEventPhotoCropView(View):
    """View for cropping master event photos"""

    def get(self, request, pk):
        from .models import EventMaster
        event = get_object_or_404(EventMaster, pk=pk, user=request.user)

        temp_image = request.GET.get('temp_image')
        if not temp_image:
            messages.error(request, "No temporary image found for cropping.")
            return redirect('calendars:master_events')

        # Generate a temporary token for secure image access
        import uuid
        temp_token = str(uuid.uuid4())

        # Store the crop data in session
        request.session['master_event_crop_data'] = {
            'event_id': event.id,
            'temp_image': temp_image,
            'temp_token': temp_token
        }

        # Store token mapping
        if 'master_event_temp_tokens' not in request.session:
            request.session['master_event_temp_tokens'] = {}
        request.session['master_event_temp_tokens'][temp_token] = temp_image
        request.session.modified = True

        context = {
            'event': event,
            'temp_token': temp_token
        }
        return render(request, 'calendars/master_event_crop_photo.html', context)


@method_decorator(login_required, name='dispatch')
class MasterEventProcessCropView(View):
    """Process the cropped master event photo"""

    def post(self, request, pk):
        from .models import EventMaster
        import base64
        import tempfile
        import os
        from PIL import Image
        import io

        event = get_object_or_404(EventMaster, pk=pk, user=request.user)

        # Get crop data from request
        crop_data = request.POST.get('crop_data')
        if not crop_data:
            messages.error(request, "No crop data provided")
            return redirect('calendars:master_events')

        try:
            # Get session data
            session_data = request.session.get('master_event_crop_data', {})
            temp_image = session_data.get('temp_image')

            if not temp_image:
                messages.error(request, "Session data not found")
                return redirect('calendars:master_events')

            # Decode the base64 image
            image_data = crop_data.split(',')[1]  # Remove data:image/jpeg;base64, prefix
            image_binary = base64.b64decode(image_data)

            # Create PIL image from binary data
            image = Image.open(io.BytesIO(image_binary))

            # Ensure it's RGB
            if image.mode in ('RGBA', 'LA', 'P'):
                image = image.convert('RGB')

            # Save cropped image to a temporary file with higher quality
            temp_cropped = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            image.save(temp_cropped.name, 'JPEG', quality=95, optimize=True)
            temp_cropped.close()

            # Create Django file from cropped image
            with open(temp_cropped.name, 'rb') as f:
                from django.core.files.base import ContentFile
                import os
                cropped_filename = f"cropped_master_event_{event.id}_{temp_image}"
                cropped_django_file = ContentFile(f.read(), name=cropped_filename)

            # Create Django file from full original image
            full_django_file = None
            from django.core.files.storage import default_storage
            temp_image_path = f"temp/{temp_image}"
            if default_storage.exists(temp_image_path):
                with default_storage.open(temp_image_path, 'rb') as f:
                    full_filename = f"full_master_event_{event.id}_{temp_image}"
                    full_django_file = ContentFile(f.read(), name=full_filename)

            # Save both images to the master event
            event.image = cropped_django_file
            if full_django_file:
                event.full_image = full_django_file
            event.save()

            # Clean up temporary files
            try:
                from django.core.files.storage import default_storage
                temp_image_path = f"temp/{temp_image}"
                if default_storage.exists(temp_image_path):
                    default_storage.delete(temp_image_path)
                if os.path.exists(temp_cropped.name):
                    os.unlink(temp_cropped.name)
            except (OSError, Exception):
                pass

            # Clear session data
            if 'master_event_crop_data' in request.session:
                del request.session['master_event_crop_data']
            if 'master_event_temp_tokens' in request.session:
                del request.session['master_event_temp_tokens']

            messages.success(request, f"Photo updated successfully for {event.name}!")

            # Preserve pagination by checking for page parameter in session
            page = request.session.get('master_events_page')
            if page:
                return redirect(f"{reverse('calendars:master_events')}?page={page}")
            return redirect('calendars:master_events')

        except Exception as e:
            messages.error(request, f"Error processing cropped image: {str(e)}")
            return redirect('calendars:master_events')


@method_decorator(login_required, name='dispatch')
class EditEventPhotoView(View):
    """Edit photo for an existing event using the unified photo editor"""
    def get(self, request, event_id):
        event = get_object_or_404(CalendarEvent, id=event_id, calendar__user=request.user)

        # Redirect to unified photo editor with calendar event context
        return redirect(f"{reverse('calendars:unified_photo_editor')}?calendar_event_id={event.id}")


@method_decorator(login_required, name='dispatch')
class RemoveEventPhotoView(View):
    """Remove photo from an event"""
    def post(self, request, event_id):
        event = get_object_or_404(CalendarEvent, id=event_id, calendar__user=request.user)

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

        messages.success(request, f"Photo removed from '{event.event_name}'.")
        return redirect('calendars:edit_event', event_id=event.id)


@method_decorator(login_required, name='dispatch')
class MultiPhotoCropView(View):
    """Crop multiple photos sequentially for combination"""
    def get(self, request, year):
        calendar = get_calendar_or_404(year, request.user)

        # Get multi-crop data from session
        multi_crop_data = request.session.get('multi_crop_data')
        if not multi_crop_data:
            messages.error(request, "No images to crop. Please upload images first.")
            return redirect('calendars:photo_editor_upload', year=year)

        current_index = multi_crop_data.get('current_photo_index', 0)
        temp_paths = multi_crop_data['temp_paths']

        # Check if we're done with all photos
        if current_index >= len(temp_paths):
            messages.error(request, "All photos have been processed.")
            return redirect('calendars:photo_editor_upload', year=year)

        # Check if current temp file exists
        current_temp_path = temp_paths[current_index]
        if not os.path.exists(current_temp_path):
            messages.error(request, "Temporary image file not found. Please upload again.")
            return redirect('calendars:photo_editor_upload', year=year)

        # Create a secure URL for the temporary image
        import uuid
        temp_token = str(uuid.uuid4())

        # Store the temp file path in session with a secure token
        if 'temp_tokens' not in request.session:
            request.session['temp_tokens'] = {}
        request.session['temp_tokens'][temp_token] = current_temp_path
        request.session.modified = True

        # Create URL that will be served by our secure view
        temp_image_url = f"/calendars/temp-image/{temp_token}/"

        return render(request, 'calendars/multi_photo_crop.html', {
            'calendar': calendar,
            'temp_image_url': temp_image_url,
            'current_index': current_index,
            'total_photos': len(temp_paths),
            'layout': multi_crop_data['layout'],
            'current_filename': multi_crop_data['original_filenames'][current_index],
            'year': year,
        })


@method_decorator(login_required, name='dispatch')
class ProcessMultiCropView(View):
    """Process cropped photos and combine them"""
    def post(self, request, year):
        calendar = get_calendar_or_404(year, request.user)

        # Get multi-crop data from session
        multi_crop_data = request.session.get('multi_crop_data')
        if not multi_crop_data:
            messages.error(request, "No crop data found.")
            return redirect('calendars:photo_editor_upload', year=year)

        current_index = multi_crop_data.get('current_photo_index', 0)
        crop_data_base64 = request.POST.get('crop_data')

        if not crop_data_base64:
            messages.error(request, "No crop data received.")
            return redirect('calendars:multi_photo_crop', year=year)

        # Decode and save the cropped image
        try:
            # Remove data URL prefix if present
            if crop_data_base64.startswith('data:image'):
                crop_data_base64 = crop_data_base64.split(',')[1]

            # Decode base64 to image
            image_data = base64.b64decode(crop_data_base64)
            image = Image.open(io.BytesIO(image_data))

            # Save cropped image temporarily with higher quality
            cropped_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'_cropped_{current_index}.jpg')
            image.save(cropped_temp_file.name, 'JPEG', quality=95, optimize=True)
            cropped_temp_file.close()

            # Store cropped image path
            if 'cropped_paths' not in multi_crop_data:
                multi_crop_data['cropped_paths'] = []

            # Ensure list is long enough
            while len(multi_crop_data['cropped_paths']) <= current_index:
                multi_crop_data['cropped_paths'].append(None)

            multi_crop_data['cropped_paths'][current_index] = cropped_temp_file.name

            # Move to next photo
            multi_crop_data['current_photo_index'] = current_index + 1

            # Update session
            request.session['multi_crop_data'] = multi_crop_data

            # Check if we have more photos to crop
            if current_index + 1 < len(multi_crop_data['temp_paths']):
                # More photos to crop
                return redirect('calendars:multi_photo_crop', year=year)
            else:
                # All photos cropped, now combine and save
                return self._combine_and_save_photos(request, year, calendar, multi_crop_data)

        except Exception as e:
            messages.error(request, f"Error processing crop: {str(e)}")
            return redirect('calendars:multi_photo_crop', year=year)

    def _combine_and_save_photos(self, request, year, calendar, multi_crop_data):
        """Combine cropped photos according to layout and save to calendar"""
        try:
            layout = multi_crop_data['layout']
            cropped_paths = multi_crop_data['cropped_paths']

            # Create combined image based on layout
            combined_image = self._create_combined_image(cropped_paths, layout)

            # Get event details from form
            month = int(request.POST.get('month', 1))
            day = int(request.POST.get('day', 1))
            event_name = request.POST.get('event_name', 'Multi-Photo Event')

            # Save the combined image with higher quality
            temp_combined_file = tempfile.NamedTemporaryFile(delete=False, suffix='_combined.jpg')
            combined_image.save(temp_combined_file.name, 'JPEG', quality=95, optimize=True)
            temp_combined_file.close()

            # Create or update calendar event
            event, created = CalendarEvent.objects.get_or_create(
                calendar=calendar,
                month=month,
                day=day,
                defaults={'event_name': event_name}
            )

            if not created:
                # Update existing event
                event.event_name = event_name
                # Delete old image if exists
                if event.image:
                    try:
                        if os.path.exists(event.image.path):
                            os.remove(event.image.path)
                    except OSError:
                        pass

            # Save new image to event
            from django.core.files import File
            with open(temp_combined_file.name, 'rb') as f:
                event.image.save(
                    f"{event_name.replace(' ', '_')}_{month:02d}_{day:02d}.jpg",
                    File(f),
                    save=True
                )

            # Clean up temporary files
            for temp_path in multi_crop_data.get('temp_paths', []):
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except OSError:
                    pass

            for cropped_path in cropped_paths:
                try:
                    if cropped_path and os.path.exists(cropped_path):
                        os.remove(cropped_path)
                except OSError:
                    pass

            try:
                if os.path.exists(temp_combined_file.name):
                    os.remove(temp_combined_file.name)
            except OSError:
                pass

            # Clear session data
            if 'multi_crop_data' in request.session:
                del request.session['multi_crop_data']

            messages.success(request, f"Multi-photo event '{event_name}' created successfully!")
            return redirect('calendars:calendar_detail', year=year)

        except Exception as e:
            messages.error(request, f"Error creating combined image: {str(e)}")
            return redirect('calendars:photo_editor_upload', year=year)

    def _create_combined_image(self, cropped_paths, layout):
        """Create combined image based on layout template"""
        # Target size is 320x200 (same as single photos)
        combined_width, combined_height = 320, 200

        # Create new image with white background
        combined = Image.new('RGB', (combined_width, combined_height), 'white')

        # Load cropped images
        images = []
        for path in cropped_paths:
            if path and os.path.exists(path):
                img = Image.open(path)
                images.append(img)

        if not images:
            raise ValueError("No valid cropped images found")

        if layout == 'two-horizontal':
            # Two photos side by side - images already cropped to 160x200
            if len(images) >= 2:
                # Images are already the correct size from cropping
                combined.paste(images[0], (0, 0))
                combined.paste(images[1], (160, 0))

        elif layout == 'two-vertical':
            # Two photos stacked - images already cropped to 320x100
            if len(images) >= 2:
                # Images are already the correct size from cropping
                combined.paste(images[0], (0, 0))
                combined.paste(images[1], (0, 100))

        elif layout == 'three-grid':
            # Three photos: large left, two small right
            if len(images) >= 3:
                # Images are already cropped to correct sizes:
                # img1: 160x200, img2: 160x100, img3: 160x100
                combined.paste(images[0], (0, 0))
                combined.paste(images[1], (160, 0))
                combined.paste(images[2], (160, 100))

        return combined


@method_decorator(login_required, name='dispatch')
class TempImageView(View):
    """Secure view to serve temporary images during photo cropping"""

    def get(self, request, token):
        # Validate token format (should be a UUID)
        import uuid
        try:
            uuid.UUID(token)
        except ValueError:
            raise Http404("Invalid token format")

        # Get the temp file path from session using the secure token
        temp_tokens = request.session.get('temp_tokens', {})
        master_event_tokens = request.session.get('master_event_temp_tokens', {})

        temp_path = temp_tokens.get(token)

        # If not found in regular tokens, check master event tokens
        if not temp_path:
            temp_filename = master_event_tokens.get(token)
            if temp_filename:
                from django.core.files.storage import default_storage
                temp_path = default_storage.path(f"temp/{temp_filename}")

        if not temp_path or not os.path.exists(temp_path):
            raise Http404("Temporary image not found")

        try:
            # Open and serve the image file
            with open(temp_path, 'rb') as f:
                image_data = f.read()

            # Determine content type based on file extension
            import mimetypes
            content_type, _ = mimetypes.guess_type(temp_path)
            if not content_type or not content_type.startswith('image/'):
                content_type = 'image/jpeg'  # Default fallback

            response = HttpResponse(image_data, content_type=content_type)
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Expires'] = '0'
            return response

        except Exception as e:
            raise Http404("Error serving temporary image")


# Calendar Sharing Views

class CalendarShareView(LoginRequiredMixin, View):
    """View for sharing a calendar with another user"""

    def post(self, request, year):
        from django.contrib.auth.models import User
        from .models import CalendarShare, CalendarInvitation
        from django.utils import timezone
        from datetime import timedelta

        # Get the calendar that belongs to the user (they can only share their own calendars)
        calendar = get_calendar_or_404(year, request.user)

        email = request.POST.get('email', '').strip()
        permission_level = request.POST.get('permission_level', 'viewer')

        if not email:
            messages.error(request, "Email address is required.")
            return redirect('calendars:calendar_detail', year=year)

        if permission_level not in ['viewer', 'editor']:
            permission_level = 'viewer'

        try:
            # Check if user exists
            try:
                target_user = User.objects.get(email=email)

                # Check if already shared
                existing_share = CalendarShare.objects.filter(
                    calendar=calendar,
                    shared_with=target_user
                ).first()

                if existing_share:
                    messages.info(request, f"Calendar is already shared with {email}")
                    return redirect('calendars:calendar_detail', year=year)

                # Create direct share
                CalendarShare.objects.create(
                    calendar=calendar,
                    shared_with=target_user,
                    shared_by=request.user,
                    permission_level=permission_level
                )

                messages.success(request, f"Calendar shared with {email} as {permission_level}")

            except User.DoesNotExist:
                # User doesn't exist, create invitation
                existing_invitation = CalendarInvitation.objects.filter(
                    calendar=calendar,
                    email=email
                ).first()

                if existing_invitation and not existing_invitation.is_expired():
                    messages.info(request, f"Invitation already sent to {email}")
                    return redirect('calendars:calendar_detail', year=year)

                # Delete old expired invitation
                if existing_invitation:
                    existing_invitation.delete()

                # Create new invitation
                CalendarInvitation.objects.create(
                    calendar=calendar,
                    email=email,
                    invited_by=request.user,
                    permission_level=permission_level,
                    expires_at=timezone.now() + timedelta(days=7)
                )

                messages.success(request, f"Invitation sent to {email}")

        except Exception as e:
            messages.error(request, f"Error sharing calendar: {str(e)}")

        return redirect('calendars:calendar_detail', year=year)


class CalendarUnshareView(LoginRequiredMixin, View):
    """View for unsharing a calendar"""

    def post(self, request, year):
        from .models import CalendarShare

        # Get the calendar that belongs to the user (they can only unshare their own calendars)
        calendar = get_calendar_or_404(year, request.user)

        share_id = request.POST.get('share_id')
        if not share_id:
            messages.error(request, "Invalid share ID")
            return redirect('calendars:calendar_detail', year=year)

        try:
            share = CalendarShare.objects.get(
                id=share_id,
                calendar=calendar,
                shared_by=request.user
            )

            username = share.shared_with.username
            share.delete()

            messages.success(request, f"Calendar unshared from {username}")

        except CalendarShare.DoesNotExist:
            messages.error(request, "Share not found")
        except Exception as e:
            messages.error(request, f"Error unsharing calendar: {str(e)}")

        return redirect('calendars:calendar_detail', year=year)


class AcceptInvitationView(LoginRequiredMixin, View):
    """View for accepting a calendar invitation"""

    def get(self, request, token):
        from .models import CalendarInvitation

        try:
            invitation = CalendarInvitation.objects.get(token=token)

            if invitation.is_expired():
                messages.error(request, "This invitation has expired")
                return redirect('calendars:calendar_list')

            if invitation.accepted:
                messages.info(request, "This invitation has already been accepted")
                return redirect('calendars:calendar_list')

            # Check if user's email matches invitation
            if invitation.email.lower() != request.user.email.lower():
                messages.error(request, "This invitation was not sent to your email address")
                return redirect('calendars:calendar_list')

            # Accept the invitation
            share = invitation.accept_invitation(request.user)

            messages.success(request,
                f"You now have {share.permission_level} access to {share.calendar}")

            return redirect('calendars:calendar_detail', year=share.calendar.year)

        except CalendarInvitation.DoesNotExist:
            messages.error(request, "Invalid invitation link")
            return redirect('calendars:calendar_list')
        except Exception as e:
            messages.error(request, f"Error accepting invitation: {str(e)}")
            return redirect('calendars:calendar_list')


class SharedCalendarsView(LoginRequiredMixin, ListView):
    """View for displaying calendars shared with the user"""

    template_name = 'calendars/shared_calendars.html'
    context_object_name = 'shared_calendars'
    paginate_by = 10

    def get_queryset(self):
        from .models import CalendarShare
        return CalendarShare.objects.filter(shared_with=self.request.user)


class CalendarSharingView(LoginRequiredMixin, TemplateView):
    """Dedicated page for calendar sharing management"""
    template_name = 'calendars/calendar_sharing.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        calendar_id = kwargs.get('calendar_id')
        calendar = get_object_or_404(Calendar, id=calendar_id, user=self.request.user)

        # Get public share URL if enabled
        public_share_url = None
        if calendar.is_publicly_shared and calendar.public_share_token:
            public_share_url = self.request.build_absolute_uri(
                reverse('calendars:public_calendar', kwargs={'token': calendar.public_share_token})
            )

        context.update({
            'calendar': calendar,
            'public_share_url': public_share_url,
            'user_can_share': True,  # Only owner can access this page
        })
        return context


class CalendarPDFViewerView(LoginRequiredMixin, TemplateView):
    """View to display generated PDF calendars in a web viewer"""
    template_name = 'calendars/pdf_viewer.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        calendar_id = kwargs.get('calendar_id')
        generation_type = kwargs.get('generation_type', 'calendar_only')

        calendar = get_object_or_404(Calendar, id=calendar_id, user=self.request.user)

        # Get the generated PDF
        from .models import GeneratedCalendar
        try:
            generated_pdf = GeneratedCalendar.objects.filter(
                calendar=calendar,
                generation_type=generation_type
            ).latest('created_at')
        except GeneratedCalendar.DoesNotExist:
            # If PDF doesn't exist, show error in context
            context.update({
                'calendar': calendar,
                'error_message': 'PDF not found. Generate a calendar first.',
                'generation_type': generation_type,
            })
            return context

        # Create the PDF URL for the viewer
        pdf_url = self.request.build_absolute_uri(
            reverse('calendars:download_calendar', kwargs={
                'year': calendar.year,
                'generation_type': generation_type
            })
        )

        # Ensure HTTPS in production
        if not self.request.is_secure() and 'localhost' not in pdf_url and '127.0.0.1' not in pdf_url:
            pdf_url = pdf_url.replace('http://', 'https://', 1)

        context.update({
            'calendar': calendar,
            'generated_pdf': generated_pdf,
            'pdf_url': pdf_url,
            'generation_type': generation_type,
        })
        return context


class CalendarHeaderImagesView(LoginRequiredMixin, TemplateView):
    """View to manage header images for each month"""
    template_name = 'calendars/header_images.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        calendar_id = kwargs.get('calendar_id')
        calendar = get_object_or_404(Calendar, id=calendar_id, user=self.request.user)

        # Get existing header images
        header_images = CalendarHeaderImage.objects.filter(calendar=calendar)
        headers_dict = {img.month: img for img in header_images}

        # Create list of all months (0=Cover, 1-12=Months, 13=Back Cover)
        months_data = []
        for month in range(0, 14):
            if month == 0:
                month_name = "Cover Page"
                month_display = "Cover"
            elif month == 13:
                month_name = "Back Cover"
                month_display = "Back Cover"
            else:
                import calendar as cal
                month_name = cal.month_name[month]
                month_display = month_name

            months_data.append({
                'month': month,
                'name': month_name,
                'display': month_display,
                'header_image': headers_dict.get(month),
                'has_image': month in headers_dict,
            })

        context.update({
            'calendar': calendar,
            'months_data': months_data,
            'total_headers': len(header_images),
            'max_headers': 14,  # Cover + 12 months + Back Cover
        })
        return context

    def post(self, request, calendar_id):
        """Handle header image uploads"""
        import logging
        logger = logging.getLogger(__name__)

        calendar = get_object_or_404(Calendar, id=calendar_id, user=request.user)
        action = request.POST.get('action')

        logger.info(f"Header images action - Calendar ID: {calendar_id}, Action: {action}, User: {request.user.username}")

        if action == 'upload_pdf':
            # PDF upload doesn't need month validation
            pass
        else:
            # Individual image upload needs month validation
            month = request.POST.get('month')
            if not month or not month.isdigit():
                messages.error(request, 'Invalid month specified.')
                return redirect('calendars:header_images', calendar_id=calendar.id)
            month = int(month)

        if action == 'upload':
            if 'image' not in request.FILES:
                messages.error(request, 'No image file provided.')
                return redirect('calendars:header_images', calendar_id=calendar.id)


            # Get or create header image for this month
            header_image, created = CalendarHeaderImage.objects.get_or_create(
                calendar=calendar,
                month=month,
                defaults={
                    'image': request.FILES['image'],
                    'title': request.POST.get('title', ''),
                }
            )

            if not created:
                # Update existing
                header_image.image = request.FILES['image']
                header_image.title = request.POST.get('title', '')
                header_image.save()

            import calendar as cal
            month_name = "Cover Page" if month == 0 else cal.month_name[month]
            messages.success(request, f'Header image uploaded for {month_name}!')

        elif action == 'upload_pdf':
            if 'pdf_file' not in request.FILES:
                logger.warning(f"PDF upload failed - No PDF file provided, Calendar ID: {calendar_id}")
                messages.error(request, 'No PDF file provided.')
                return redirect('calendars:header_images', calendar_id=calendar.id)

            pdf_file = request.FILES['pdf_file']
            logger.info(f"PDF upload started - File: {pdf_file.name}, Size: {pdf_file.size} bytes, Calendar ID: {calendar_id}")

            # Validate PDF file
            if not pdf_file.name.lower().endswith('.pdf'):
                logger.warning(f"PDF upload failed - Invalid file type: {pdf_file.name}, Calendar ID: {calendar_id}")
                messages.error(request, 'Please upload a PDF file.')
                return redirect('calendars:header_images', calendar_id=calendar.id)

            try:
                # Save the PDF to the header page as well
                from .models import CalendarHeader
                from django.core.files.base import ContentFile

                # Read the PDF content once
                pdf_content = pdf_file.read()

                # Create a copy for the header document
                pdf_copy = ContentFile(pdf_content, name=pdf_file.name)

                header, created = CalendarHeader.objects.update_or_create(
                    calendar=calendar,
                    defaults={
                        'document': pdf_copy,
                        'january_page': 2  # Default to page 2 for January since page 1 is cover
                    }
                )

                # Process PDF to individual header images using the raw content
                self._process_pdf_to_headers(pdf_content, calendar, request)

                if created:
                    logger.info(f"PDF upload successful - New header created, Calendar ID: {calendar_id}")
                    messages.success(request, 'PDF saved to header page and converted to individual header images successfully!')
                else:
                    logger.info(f"PDF upload successful - Header updated, Calendar ID: {calendar_id}")
                    messages.success(request, 'PDF updated on header page and converted to individual header images successfully!')
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f'Error processing PDF to headers: {str(e)}', exc_info=True)
                messages.error(request, f'Error processing PDF: {str(e)}')
                return redirect('calendars:header_images', calendar_id=calendar.id)

        elif action == 'delete':
            try:
                header_image = CalendarHeaderImage.objects.get(calendar=calendar, month=month)
                import calendar as cal
                month_name = "Cover Page" if month == 0 else cal.month_name[month]
                header_image.delete()
                messages.success(request, f'Header image removed for {month_name}.')
            except CalendarHeaderImage.DoesNotExist:
                messages.error(request, 'Header image not found.')

        elif action == 'rotate':
            try:
                header_image = CalendarHeaderImage.objects.get(calendar=calendar, month=month)
                degrees = int(request.POST.get('degrees', 0))

                # Transform the image
                self._transform_header_image(header_image, action='rotate', degrees=degrees)

                import calendar as cal
                month_name = "Cover Page" if month == 0 else "Back Cover" if month == 13 else cal.month_name[month]
                messages.success(request, f'Header image rotated {degrees}° for {month_name}.')
            except CalendarHeaderImage.DoesNotExist:
                messages.error(request, 'Header image not found.')
            except ValueError:
                messages.error(request, 'Invalid rotation value.')
            except Exception as e:
                messages.error(request, f'Error rotating image: {str(e)}')

        elif action == 'flip':
            try:
                header_image = CalendarHeaderImage.objects.get(calendar=calendar, month=month)
                direction = request.POST.get('direction', 'horizontal')

                # Transform the image
                self._transform_header_image(header_image, action='flip', direction=direction)

                import calendar as cal
                month_name = "Cover Page" if month == 0 else "Back Cover" if month == 13 else cal.month_name[month]
                flip_text = "horizontally" if direction == "horizontal" else "vertically"
                messages.success(request, f'Header image flipped {flip_text} for {month_name}.')
            except CalendarHeaderImage.DoesNotExist:
                messages.error(request, 'Header image not found.')
            except Exception as e:
                messages.error(request, f'Error flipping image: {str(e)}')

        return redirect('calendars:header_images', calendar_id=calendar.id)

    def _process_pdf_to_headers(self, pdf_content, calendar, request):
        """Convert PDF pages to header images"""
        import tempfile
        import os
        from django.core.files.base import ContentFile
        from .models import CalendarHeaderImage

        try:
            from pdf2image import convert_from_bytes
        except ImportError as e:
            raise Exception("PDF processing library not available. Please contact support.") from e

        try:
            # Convert PDF to images
            images = convert_from_bytes(pdf_content, dpi=300)

            created_count = 0
            for i, image in enumerate(images):
                # Limit to 14 pages max (cover + 12 months + back cover)
                if i >= 14:
                    break

                try:
                    # Convert PIL image to Django file
                    from io import BytesIO
                    img_io = BytesIO()
                    image.save(img_io, format='JPEG', quality=95)
                    img_io.seek(0)

                    # Create filename
                    if i == 0:
                        filename = f'cover_{calendar.year}_{calendar.id}.jpg'
                        month_num = 0
                    elif i == 13:
                        filename = f'back_cover_{calendar.year}_{calendar.id}.jpg'
                        month_num = 13
                    else:
                        import calendar as cal
                        month_name = cal.month_name[i].lower()
                        filename = f'{month_name}_{calendar.year}_{calendar.id}.jpg'
                        month_num = i

                    # Create or update header image
                    header_image, created = CalendarHeaderImage.objects.get_or_create(
                        calendar=calendar,
                        month=month_num,
                        defaults={
                            'title': f'Page {i + 1}',
                        }
                    )

                    # Save the image
                    header_image.image.save(
                        filename,
                        ContentFile(img_io.getvalue()),
                        save=True
                    )

                    created_count += 1

                except Exception as e:
                    # Log the error but continue processing other pages
                    print(f"Error processing page {i + 1}: {str(e)}")
                    continue

            messages.info(request, f'Created {created_count} header images from PDF.')

        except Exception as e:
            raise Exception(f'Failed to convert PDF to images: {str(e)}')

    def _transform_header_image(self, header_image, action, **kwargs):
        """Transform header image (rotate or flip)"""
        from PIL import Image
        from django.core.files.base import ContentFile
        from io import BytesIO
        import os

        try:
            # Open the current image
            image_path = header_image.image.path
            with Image.open(image_path) as img:
                # Convert to RGB if necessary (for JPEG compatibility)
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')

                # Apply transformation
                if action == 'rotate':
                    degrees = kwargs.get('degrees', 0)
                    if degrees in [90, 180, 270]:
                        img = img.rotate(-degrees, expand=True)  # Negative for clockwise rotation
                elif action == 'flip':
                    direction = kwargs.get('direction', 'horizontal')
                    if direction == 'horizontal':
                        img = img.transpose(Image.FLIP_LEFT_RIGHT)
                    elif direction == 'vertical':
                        img = img.transpose(Image.FLIP_TOP_BOTTOM)

                # Save transformed image
                img_io = BytesIO()
                img.save(img_io, format='JPEG', quality=95)
                img_io.seek(0)

                # Get original filename
                original_name = os.path.basename(header_image.image.name)

                # Save back to the same field
                header_image.image.save(
                    original_name,
                    ContentFile(img_io.getvalue()),
                    save=True
                )

        except Exception as e:
            raise Exception(f'Failed to transform image: {str(e)}')


class DigitalCalendarView(TemplateView):
    template_name = 'calendars/digital_calendar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        calendar_id = self.kwargs['calendar_id']
        calendar = get_object_or_404(Calendar, id=calendar_id)

        # Check permissions - allow public access if calendar is publicly shared
        if not calendar.can_view(self.request.user) and not calendar.is_publicly_shared:
            raise PermissionDenied("You don't have permission to view this calendar.")

        # Get all events for the calendar
        events = calendar.events.all().order_by('month', 'day')

        # Get header images for the calendar
        header_images = CalendarHeaderImage.objects.filter(calendar=calendar)
        header_images_dict = {img.month: img for img in header_images}

        # Create month data with events and headers
        months_data = []

        # Add cover page (month 0)
        calendar_name = calendar.calendar_year.name if calendar.calendar_year else "Calendar"
        cover_data = {
            'month': 0,
            'name': 'Cover',
            'display': f'{calendar.year} {calendar_name}',
            'header_image': header_images_dict.get(0),
            'events': [],
            'calendar_grid': None
        }
        months_data.append(cover_data)

        # Add each month (1-12)
        for month in range(1, 13):
            month_events = events.filter(month=month)

            # Create calendar grid
            calendar_obj = cal.Calendar(firstweekday=6)  # Sunday = 0
            month_calendar = calendar_obj.monthdayscalendar(calendar.year, month)

            # Create events dict by day
            events_by_day = {}
            for event in month_events:
                if event.day not in events_by_day:
                    events_by_day[event.day] = []
                events_by_day[event.day].append(event)

            # Add events to calendar grid
            calendar_grid = []
            for week in month_calendar:
                week_data = []
                for day in week:
                    if day == 0:
                        week_data.append({'day': 0, 'events': []})
                    else:
                        day_events = events_by_day.get(day, [])
                        week_data.append({'day': day, 'events': day_events})
                calendar_grid.append(week_data)

            month_data = {
                'month': month,
                'name': cal.month_name[month],
                'display': f'{cal.month_name[month]} {calendar.year}',
                'header_image': header_images_dict.get(month),
                'events': month_events,
                'calendar_grid': calendar_grid
            }
            months_data.append(month_data)

        # Add back cover (month 13)
        back_cover_data = {
            'month': 13,
            'name': 'Back Cover',
            'display': 'Back Cover',
            'header_image': header_images_dict.get(13),
            'events': [],
            'calendar_grid': None
        }
        months_data.append(back_cover_data)

        # Process calendar grid to handle multiple events
        for month_data in months_data:
            if month_data['calendar_grid']:
                for week in month_data['calendar_grid']:
                    for day_data in week:
                        if day_data['day'] > 0 and len(day_data['events']) > 1:
                            # Multiple events on this day - create combined display
                            day_data['is_multiple'] = True
                            day_data['combined_name'] = CalendarEvent.get_combined_display_name(
                                calendar, month_data['month'], day_data['day']
                            )

        context.update({
            'calendar': calendar,
            'months_data': months_data,
            'year': calendar.year,
            'calendar_name': calendar_name
        })

        return context


@method_decorator(login_required, name='dispatch')
class UnifiedPhotoEditorView(View):
    """Year-agnostic photo editor that handles both calendar events and master events"""

    def get(self, request):
        # Determine context from URL parameters
        master_event_id = request.GET.get('master_event_id')
        calendar_event_id = request.GET.get('calendar_event_id')
        year = request.GET.get('year')

        context = {}

        if master_event_id:
            # Master event context
            from .models import EventMaster
            try:
                master_event = EventMaster.objects.get(pk=master_event_id, user=request.user)
                request.session['edit_master_event_id'] = master_event_id
                context.update({
                    'master_event': master_event,
                    'page_title': 'Edit Master Event Photo',
                    'back_url': reverse('calendars:master_events'),
                    'back_text': 'Back to Master Events'
                })
            except EventMaster.DoesNotExist:
                messages.error(request, "Master event not found.")
                return redirect('calendars:master_events')

        elif calendar_event_id:
            # Existing calendar event context
            event = get_object_or_404(CalendarEvent, id=calendar_event_id, calendar__user=request.user)
            request.session['edit_event_data'] = {
                'event_id': event.id,
                'month': event.month,
                'day': event.day,
                'event_name': event.event_name,
                'return_to_edit': True,
            }
            context.update({
                'edit_event_data': request.session['edit_event_data'],
                'calendar': event.calendar,
                'page_title': 'Change Event Photo',
                'back_url': reverse('calendars:edit_event', kwargs={'event_id': event.id}),
                'back_text': 'Back to Event'
            })

        elif year:
            # New calendar event context
            calendar = get_calendar_or_404(int(year), request.user)
            context.update({
                'calendar': calendar,
                'page_title': 'Upload & Edit Photo',
                'back_url': reverse('calendars:calendar_detail', kwargs={'year': int(year)}),
                'back_text': 'Back to Calendar'
            })
        else:
            messages.error(request, "Invalid photo editing context.")
            return redirect('calendars:calendar_list')

        return render(request, 'calendars/unified_photo_editor.html', context)

    def post(self, request):
        # Handle photo upload for any context
        photo_mode = request.POST.get('photo_mode', 'single')

        if photo_mode == 'single':
            uploaded_file = request.FILES.get('photo')

            if not uploaded_file:
                messages.error(request, "Please select a photo to upload.")
                return self.get(request)

            # Save temporary file for cropping
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            for chunk in uploaded_file.chunks():
                temp_file.write(chunk)
            temp_file.close()

            # Store data in session for the crop view
            request.session['crop_data'] = {
                'temp_path': temp_file.name,
                'original_filename': uploaded_file.name,
                'photo_mode': 'single'
            }

            return redirect('calendars:unified_photo_crop')

        elif photo_mode == 'multi':
            uploaded_files = request.FILES.getlist('photos')
            layout = request.POST.get('layout', 'side_by_side')

            if not uploaded_files or len(uploaded_files) < 2:
                messages.error(request, "Please select at least 2 photos for multi-photo mode.")
                return self.get(request)

            if len(uploaded_files) > 4:
                messages.error(request, "Maximum 4 photos allowed for multi-photo mode.")
                return self.get(request)

            # Save temporary files
            temp_paths = []
            original_filenames = []

            for uploaded_file in uploaded_files:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                for chunk in uploaded_file.chunks():
                    temp_file.write(chunk)
                temp_file.close()
                temp_paths.append(temp_file.name)
                original_filenames.append(uploaded_file.name)

            # Store multi-crop data in session
            request.session['multi_crop_data'] = {
                'temp_paths': temp_paths,
                'original_filenames': original_filenames,
                'layout': layout,
                'current_photo_index': 0,
                'cropped_paths': [],
                'photo_mode': 'multi'
            }

            # TODO: Create unified multi-crop view or redirect to existing one
            # For now, combine into single image and redirect to single crop
            combined_temp_path, full_image_path = self._create_temp_combined_image(temp_paths, layout)
            if combined_temp_path:
                request.session['crop_data'] = {
                    'temp_path': combined_temp_path,
                    'full_image_path': full_image_path,  # Store path to full-size image
                    'original_filename': f"combined_{len(uploaded_files)}_photos.jpg",
                    'photo_mode': 'combined_multi'
                }
                return redirect('calendars:unified_photo_crop')
            else:
                messages.error(request, "Error combining photos. Please try again.")
                return self.get(request)

        messages.error(request, "Invalid photo mode selected.")
        return self.get(request)

    def _create_temp_combined_image(self, temp_paths, layout):
        """Create a temporary combined image from multiple photos"""
        try:
            from PIL import Image
            import tempfile
            import shutil

            target_width, target_height = 320, 200
            combined_img = Image.new('RGB', (target_width, target_height), (255, 255, 255))

            images = []
            for path in temp_paths:
                try:
                    img = Image.open(path)
                    if img.mode in ('RGBA', 'LA', 'P'):
                        img = img.convert('RGB')
                    images.append(img)
                except Exception:
                    continue

            if len(images) < 2:
                return None, None

            # Create a copy of the first image as the full-size image
            full_image_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            if temp_paths:
                shutil.copy2(temp_paths[0], full_image_temp.name)
            full_image_temp.close()

            # Combine images based on layout
            if layout == 'side_by_side' and len(images) >= 2:
                # Side by side
                half_width = target_width // 2
                for i in range(min(2, len(images))):
                    img_resized = images[i].resize((half_width, target_height), Image.Resampling.LANCZOS)
                    x_pos = i * half_width
                    combined_img.paste(img_resized, (x_pos, 0))

            elif layout == 'top_bottom' and len(images) >= 2:
                # Top/bottom
                half_height = target_height // 2
                for i in range(min(2, len(images))):
                    img_resized = images[i].resize((target_width, half_height), Image.Resampling.LANCZOS)
                    y_pos = i * half_height
                    combined_img.paste(img_resized, (0, y_pos))

            elif layout == 'grid':
                # 2x2 grid
                half_width = target_width // 2
                half_height = target_height // 2
                for i in range(min(4, len(images))):
                    img_resized = images[i].resize((half_width, half_height), Image.Resampling.LANCZOS)
                    x_pos = (i % 2) * half_width
                    y_pos = (i // 2) * half_height
                    combined_img.paste(img_resized, (x_pos, y_pos))

            # Save combined image to temporary file
            temp_combined = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            combined_img.save(temp_combined.name, 'JPEG', quality=95, optimize=True)
            temp_combined.close()

            # Clean up individual temp files (except the one we copied for full image)
            for path in temp_paths:
                try:
                    os.unlink(path)
                except OSError:
                    pass

            return temp_combined.name, full_image_temp.name

        except Exception as e:
            print(f"Error creating combined image: {str(e)}")
            return None, None


@method_decorator(login_required, name='dispatch')
class UnifiedPhotoCropView(View):
    """Year-agnostic photo cropping view"""

    def get(self, request):
        # Get crop data from session
        crop_data = request.session.get('crop_data')
        if not crop_data:
            messages.error(request, "No image to crop. Please upload an image first.")
            return redirect('calendars:unified_photo_editor')

        # Check if temp file exists
        if not os.path.exists(crop_data['temp_path']):
            messages.error(request, "Temporary image file not found. Please upload again.")
            return redirect('calendars:unified_photo_editor')

        # Create a secure URL for the temporary image
        import uuid
        temp_token = str(uuid.uuid4())

        # Store the temp file path in session with a secure token
        if 'temp_tokens' not in request.session:
            request.session['temp_tokens'] = {}
        request.session['temp_tokens'][temp_token] = crop_data['temp_path']
        request.session.modified = True

        # Create URL that will be served by our secure view
        temp_image_url = f"/calendars/temp-image/{temp_token}/"

        # Determine context and prepare data
        context = {
            'temp_image_url': temp_image_url,
            'temp_image_path': crop_data['temp_path'],
            'original_filename': crop_data['original_filename'],
        }

        # Check context
        master_event_id = request.session.get('edit_master_event_id')
        edit_event_data = request.session.get('edit_event_data')

        if master_event_id:
            # Master event context
            from .models import EventMaster
            from .forms import MasterEventForm
            try:
                master_event = EventMaster.objects.get(pk=master_event_id, user=request.user)
                master_event_form = MasterEventForm(instance=master_event)
                print(f"DEBUG: Loading master event {master_event.id}, year_occurred: {master_event.year_occurred}")

                # Get linked calendar events for this master event
                linked_events = CalendarEvent.objects.filter(master_event=master_event).select_related('calendar')
                linked_calendars = []
                if linked_events.exists():
                    # Group events by calendar year for display
                    calendar_years = {}
                    for event in linked_events:
                        year = event.calendar.year
                        if year not in calendar_years:
                            calendar_years[year] = []
                        calendar_years[year].append(event)

                    # Create list of affected calendars
                    for year in sorted(calendar_years.keys()):
                        linked_calendars.append({
                            'year': year,
                            'count': len(calendar_years[year])
                        })

                context.update({
                    'master_event': master_event,
                    'master_event_form': master_event_form,
                    'is_master_event': True,
                    'event_name': master_event.name,
                    'month': master_event.month,
                    'day': master_event.day,
                    'event_date': f"{master_event.month:02d}/{master_event.day:02d}",
                    'page_title': f'Crop Photo for {master_event.name}',
                    'linked_events_count': linked_events.count(),
                    'linked_calendars': linked_calendars
                })
            except EventMaster.DoesNotExist:
                del request.session['edit_master_event_id']
                messages.error(request, "Master event not found.")
                return redirect('calendars:master_events')

        elif edit_event_data:
            # Calendar event context
            context.update({
                'edit_event_data': edit_event_data,
                'is_master_event': False,
                'event_name': edit_event_data['event_name'],
                'month': edit_event_data['month'],
                'day': edit_event_data['day'],
                'event_date': f"{edit_event_data['month']:02d}/{edit_event_data['day']:02d}",
                'year': 2025,  # We'll need to get this from the event or session
                'page_title': f'Crop Photo for {edit_event_data["event_name"]}'
            })
        else:
            # New calendar event context
            context.update({
                'is_master_event': False,
                'event_name': 'Enter Event Name',
                'month': '',
                'day': '',
                'event_date': 'Choose Date',
                'year': 2025,  # Default year or get from session
                'page_title': 'Crop Photo for New Event'
            })

        return render(request, 'calendars/unified_photo_crop.html', context)


@method_decorator(login_required, name='dispatch')
class UnifiedProcessCropView(View):
    """Year-agnostic crop processing view"""

    def post(self, request):
        # Get form data
        temp_image_path = request.POST.get('temp_image_path')
        original_filename = request.POST.get('original_filename')
        crop_data = request.POST.get('crop_data')

        # Check if this is a combined multi-photo (no full image to preserve)
        crop_session_data = request.session.get('crop_data', {})
        is_combined_multi = crop_session_data.get('photo_mode') == 'combined_multi'

        if not crop_data:
            messages.error(request, "No crop data received. Please try again.")
            return redirect('calendars:unified_photo_crop')

        try:
            # Process the cropped image
            image_data = crop_data.split(',')[1]  # Remove data:image/jpeg;base64, prefix
            image_binary = base64.b64decode(image_data)

            # Create PIL image from binary data
            image = Image.open(io.BytesIO(image_binary))

            # Ensure it's RGB
            if image.mode in ('RGBA', 'LA', 'P'):
                image = image.convert('RGB')

            # Save cropped image to a temporary file with higher quality
            temp_cropped = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            image.save(temp_cropped.name, 'JPEG', quality=95, optimize=True)
            temp_cropped.close()

            # Create Django files
            with open(temp_cropped.name, 'rb') as f:
                from django.core.files.base import ContentFile
                cropped_django_file = ContentFile(f.read(), name=f"cropped_{original_filename}")

            # Try to get full image path - for multi-photo it's stored separately
            full_image_path = request.session.get('crop_data', {}).get('full_image_path', temp_image_path)

            full_django_file = None
            if full_image_path and os.path.exists(full_image_path):
                with open(full_image_path, 'rb') as f:
                    full_django_file = ContentFile(f.read(), name=f"full_{original_filename}")
                print(f"DEBUG: Created full_django_file from {full_image_path}")
            else:
                print(f"DEBUG: Could not create full_django_file. full_image_path={full_image_path}, exists={os.path.exists(full_image_path) if full_image_path else False}")

            # Determine context and save appropriately
            master_event_id = request.session.get('edit_master_event_id')
            edit_event_data = request.session.get('edit_event_data')

            if master_event_id:
                # Save to master event with form data
                from .models import EventMaster
                try:
                    master_event = EventMaster.objects.get(pk=master_event_id, user=request.user)

                    # Update master event fields from form
                    master_event.name = request.POST.get('master_event_name', master_event.name)
                    master_event.month = int(request.POST.get('master_month', master_event.month))
                    master_event.day = int(request.POST.get('master_day', master_event.day))
                    master_event.event_type = request.POST.get('master_event_type', master_event.event_type)

                    # Debug all POST data related to year
                    print(f"DEBUG: All POST keys: {list(request.POST.keys())}")
                    year_occurred = request.POST.get('master_year_occurred', '') or request.POST.get('year_occurred', '')
                    print(f"DEBUG: year_occurred from POST: '{year_occurred}' (type: {type(year_occurred)})")

                    # More robust year processing
                    if year_occurred and str(year_occurred).strip():
                        try:
                            year_value = int(str(year_occurred).strip())
                            master_event.year_occurred = year_value
                            print(f"DEBUG: Successfully converted year_occurred to: {year_value}")
                        except (ValueError, TypeError) as e:
                            print(f"DEBUG: Failed to convert year_occurred '{year_occurred}': {e}")
                            master_event.year_occurred = None
                    else:
                        print(f"DEBUG: year_occurred is empty or None, setting to None")
                        master_event.year_occurred = None

                    print(f"DEBUG: master_event.year_occurred set to: {master_event.year_occurred}")

                    master_event.groups = request.POST.get('master_groups', master_event.groups)
                    master_event.description = request.POST.get('master_description', master_event.description)

                    # Update photos
                    master_event.image = cropped_django_file
                    if full_django_file:
                        master_event.full_image = full_django_file
                        print(f"DEBUG: Setting master_event.full_image for event {master_event.id}")
                    else:
                        print(f"DEBUG: No full_django_file to save for master event {master_event.id}")

                    # Debug year before save
                    print(f"DEBUG: About to save master_event {master_event.id}")
                    print(f"DEBUG: master_event.year_occurred before save: {master_event.year_occurred}")
                    print(f"DEBUG: master_event.__dict__ before save: {master_event.__dict__}")

                    master_event.save()

                    # Debug year after save
                    master_event.refresh_from_db()
                    print(f"DEBUG: After save and refresh - master_event.year_occurred: {master_event.year_occurred}")
                    print(f"DEBUG: Saved master event {master_event.id}, full_image field: {bool(master_event.full_image)}")

                    # Check if user wants to update linked calendar events
                    update_calendar_events_value = request.POST.get('update_calendar_events')
                    update_calendar_events = update_calendar_events_value == 'yes'
                    linked_events = CalendarEvent.objects.filter(master_event=master_event)

                    print(f"DEBUG: update_calendar_events POST value: '{update_calendar_events_value}'")
                    print(f"DEBUG: update_calendar_events boolean: {update_calendar_events}")
                    print(f"DEBUG: Found {linked_events.count()} linked events")

                    if update_calendar_events and linked_events.exists():
                        updated_count = 0
                        print(f"DEBUG: Starting update of {linked_events.count()} linked events")
                        print(f"DEBUG: Master event image: {master_event.image}")
                        print(f"DEBUG: Master event full_image: {master_event.full_image}")

                        for event in linked_events:
                            print(f"DEBUG: Updating event {event.id} in calendar {event.calendar.year}")
                            print(f"DEBUG: Before - event image: {event.image}")
                            print(f"DEBUG: Before - event full_image: {event.full_image}")

                            # Update event name based on master event
                            event.event_name = master_event.get_display_name(
                                for_year=event.calendar.year,
                                user=event.calendar.user
                            )
                            # Reference images from master event (no copying needed)
                            if master_event.image:
                                event.image = master_event.image
                            if master_event.full_image:
                                event.full_image = master_event.full_image

                            event.save()

                            # Verify the update
                            event.refresh_from_db()
                            print(f"DEBUG: After save - event image: {event.image}")
                            print(f"DEBUG: After save - event full_image: {event.full_image}")
                            updated_count += 1

                        messages.success(request,
                            f"Master event '{master_event.name}' updated successfully! "
                            f"Also updated {updated_count} linked calendar event(s)."
                        )
                    else:
                        messages.success(request, f"Master event '{master_event.name}' updated successfully with new photo!")

                    redirect_url = 'calendars:master_events'

                except EventMaster.DoesNotExist:
                    messages.error(request, "Master event not found.")
                    redirect_url = 'calendars:master_events'
                except ValueError as e:
                    messages.error(request, f"Invalid form data: {str(e)}")
                    return redirect('calendars:unified_photo_crop')

            elif edit_event_data:
                # Update existing calendar event
                event = CalendarEvent.objects.get(id=edit_event_data['event_id'])
                event.image = cropped_django_file
                event.full_image = full_django_file
                event.original_filename = original_filename
                event.save()

                messages.success(request, f"Photo updated successfully for '{event.event_name}'!")
                redirect_url = reverse('calendars:edit_event', kwargs={'event_id': event.id})

            else:
                # Create new calendar event - need form data
                event_name = request.POST.get('event_name')
                month = int(request.POST.get('month'))
                day = int(request.POST.get('day'))
                year = int(request.POST.get('year', 2025))  # Default to 2025 or get from context

                calendar = get_calendar_or_404(year, request.user)

                # Check if events already exist for this date
                existing_events = CalendarEvent.get_events_for_date(calendar, month, day)

                if existing_events.exists():
                    # Create a new event (allow multiple events on same day)
                    event = CalendarEvent.objects.create(
                        calendar=calendar,
                        month=month,
                        day=day,
                        event_name=event_name,
                        image=cropped_django_file,
                        full_image=full_django_file,
                        original_filename=original_filename
                    )
                    messages.warning(request, f"Added '{event_name}' to {calendar.year}-{month:02d}-{day:02d}. This date now has {existing_events.count() + 1} events.")
                else:
                    # Create new event
                    event = CalendarEvent.objects.create(
                        calendar=calendar,
                        month=month,
                        day=day,
                        event_name=event_name,
                        image=cropped_django_file,
                        full_image=full_django_file,
                        original_filename=original_filename
                    )

                messages.success(request, f"Event '{event_name}' created successfully with cropped photo.")
                redirect_url = reverse('calendars:calendar_detail', kwargs={'year': year})

            # Clean up temporary files
            try:
                if temp_image_path and os.path.exists(temp_image_path):
                    os.unlink(temp_image_path)
                if full_image_path and full_image_path != temp_image_path and os.path.exists(full_image_path):
                    os.unlink(full_image_path)
                if os.path.exists(temp_cropped.name):
                    os.unlink(temp_cropped.name)
            except OSError:
                pass

            # Clear session data
            session_keys_to_clear = ['crop_data', 'edit_master_event_id', 'edit_event_data', 'temp_tokens']
            for key in session_keys_to_clear:
                if key in request.session:
                    del request.session[key]

            return redirect(redirect_url)

        except Exception as e:
            messages.error(request, f"Error processing cropped image: {str(e)}")
            return redirect('calendars:unified_photo_crop')
