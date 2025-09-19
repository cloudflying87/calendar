from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, TemplateView
from django.views import View
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from .models import Calendar, CalendarEvent, CalendarHeader, GeneratedCalendar, Holiday, HolidayCalculator
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

        return context

    def get_events_by_month(self):
        events_by_month = {}
        for month in range(1, 13):
            events_by_month[month] = self.object.events.filter(month=month).order_by('day')
        return events_by_month


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
        return context

    def get_events_by_month(self):
        events_by_month = {}
        for month in range(1, 13):
            events_by_month[month] = self.object.events.filter(month=month).order_by('day')
        return events_by_month


@method_decorator(login_required, name='dispatch')
class ImageUploadView(View):
    def get(self, request, year):
        calendar = get_object_or_404(Calendar, year=year, user=request.user)
        form = ImageUploadForm()
        return render(request, 'calendars/image_upload.html', {
            'calendar': calendar,
            'form': form
        })

    def post(self, request, year):
        calendar = get_object_or_404(Calendar, year=year, user=request.user)
        form = ImageUploadForm(request.POST, request.FILES)

        if form.is_valid():
            uploaded_files = request.FILES.getlist('images')
            created_events = []
            errors = []

            # Get user preferences for master events
            from .models import UserEventPreferences, EventMaster
            preferences, created = UserEventPreferences.objects.get_or_create(user=request.user)

            # Process all files as bulk upload (no cropping)
            for uploaded_file in uploaded_files:
                try:
                    # Parse filename to extract date and event name
                    parsed_data = CalendarEvent.parse_filename(uploaded_file.name)

                    if parsed_data:
                        month, day, event_name = parsed_data

                        # Check if matching master event exists
                        master_event = EventMaster.objects.filter(
                            user=request.user,
                            name__iexact=event_name,
                            month=month,
                            day=day
                        ).first()

                        # Get display name if master event exists
                        display_name = event_name
                        if master_event:
                            display_name = master_event.get_display_name(for_year=calendar.year)

                        # Create or update calendar event
                        event, created = CalendarEvent.objects.update_or_create(
                            calendar=calendar,
                            month=month,
                            day=day,
                            defaults={
                                'event_name': display_name,
                                'master_event': master_event,
                                'image': uploaded_file,
                                'original_filename': uploaded_file.name
                            }
                        )
                        created_events.append(event)

                        # Handle adding to master list based on preferences
                        if not master_event and preferences.add_to_master_list == 'always':
                            # Auto-create master event
                            EventMaster.objects.create(
                                user=request.user,
                                name=event_name,
                                month=month,
                                day=day,
                                groups=preferences.default_groups
                            )
                    else:
                        errors.append(f"Could not parse filename: {uploaded_file.name}. Use format: MMDD eventname.jpg")

                except Exception as e:
                    errors.append(f"Error processing {uploaded_file.name}: {str(e)}")

            if created_events:
                messages.success(request, f"Successfully uploaded {len(created_events)} images.")

            if errors:
                for error in errors:
                    messages.error(request, error)

            return redirect('calendars:calendar_detail', year=year)

        return render(request, 'calendars/image_upload.html', {
            'calendar': calendar,
            'form': form
        })


@method_decorator(login_required, name='dispatch')
class HeaderUploadView(View):
    def get(self, request, year):
        calendar = get_object_or_404(Calendar, year=year, user=request.user)
        form = HeaderUploadForm()
        return render(request, 'calendars/header_upload.html', {
            'calendar': calendar,
            'form': form
        })

    def post(self, request, year):
        calendar = get_object_or_404(Calendar, year=year, user=request.user)
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
        calendar = get_object_or_404(Calendar, year=year, user=request.user)
        generation_type = request.POST.get('generation_type', 'calendar_only')

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

            # Save generated calendar record
            generated_calendar = GeneratedCalendar.objects.create(
                calendar=calendar,
                pdf_file=pdf_file,
                generation_type=generation_type
            )

            messages.success(request, f"Calendar generated successfully! Type: {generated_calendar.get_generation_type_display()}")

        except Exception as e:
            messages.error(request, f"Error generating calendar: {str(e)}")

        return redirect('calendars:calendar_detail', year=year)


@method_decorator(login_required, name='dispatch')
class DownloadCalendarView(View):
    def get(self, request, year, generation_type):
        calendar = get_object_or_404(Calendar, user=request.user, year=year)

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
    def get(self, request, year):
        calendar = get_object_or_404(Calendar, year=year, user=request.user)
        form = HolidayManagementForm(calendar=calendar)

        # Calculate actual dates for each holiday
        holiday_dates = {}
        for holiday_code, holiday_name in Holiday.HOLIDAY_CHOICES:
            calculated_date = HolidayCalculator.get_holiday_date(holiday_code, year)
            if calculated_date:
                holiday_dates[holiday_code] = calculated_date.strftime('%B %d, %Y')
            else:
                holiday_dates[holiday_code] = 'Date calculation error'

        return render(request, 'calendars/holiday_management.html', {
            'calendar': calendar,
            'form': form,
            'holiday_dates': holiday_dates
        })

    def post(self, request, year):
        calendar = get_object_or_404(Calendar, year=year, user=request.user)
        form = HolidayManagementForm(request.POST, request.FILES, calendar=calendar)

        if form.is_valid():
            form.save(calendar)
            messages.success(request, "Holiday selections updated successfully.")
            return redirect('calendars:calendar_detail', year=year)

        # Calculate actual dates for template on form errors
        holiday_dates = {}
        for holiday_code, holiday_name in Holiday.HOLIDAY_CHOICES:
            calculated_date = HolidayCalculator.get_holiday_date(holiday_code, year)
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
        calendar = get_object_or_404(Calendar, year=year, user=request.user)

        # Check if we're editing an existing event
        edit_event_data = request.session.get('edit_event_data')
        context = {
            'calendar': calendar,
            'edit_event_data': edit_event_data,
        }

        return render(request, 'calendars/photo_editor_upload.html', context)

    def post(self, request, year):
        calendar = get_object_or_404(Calendar, year=year, user=request.user)

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
        calendar = get_object_or_404(Calendar, year=year, user=request.user)

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

        if edit_event_data:
            # Editing existing event - use event data
            event_date = f"{edit_event_data['month']:02d}/{edit_event_data['day']:02d}/{year}"
            event_name = edit_event_data['event_name']
            month = edit_event_data['month']
            day = edit_event_data['day']
        elif 'month' in crop_data and 'day' in crop_data:
            # Old workflow - has date/event data in crop_data
            event_date = f"{crop_data['month']:02d}/{crop_data['day']:02d}/{year}"
            event_name = crop_data['event_name']
            month = crop_data['month']
            day = crop_data['day']
        else:
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
        })


@method_decorator(login_required, name='dispatch')
class ProcessCropView(View):
    def post(self, request, year):
        calendar = get_object_or_404(Calendar, year=year, user=request.user)

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

            # Create Django file from temporary file
            with open(temp_cropped.name, 'rb') as f:
                from django.core.files.base import ContentFile
                django_file = ContentFile(f.read(), name=original_filename)

            # Create or update calendar event
            event, created = CalendarEvent.objects.update_or_create(
                calendar=calendar,
                month=month,
                day=day,
                defaults={
                    'event_name': event_name,
                    'image': django_file,
                    'original_filename': original_filename
                }
            )

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
    def get(self, request, year):
        calendar = get_object_or_404(Calendar, year=year, user=request.user)
        return render(request, 'calendars/delete_calendar.html', {
            'calendar': calendar
        })

    def post(self, request, year):
        calendar = get_object_or_404(Calendar, year=year, user=request.user)
        calendar_year = calendar.year

        # Delete all associated files and the calendar
        calendar.delete()

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
class DownloadAllPhotosView(View):
    def get(self, request, year):
        calendar = get_object_or_404(Calendar, year=year, user=request.user)

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
class EditEventPhotoView(View):
    """Edit photo for an existing event using the photo editor"""
    def get(self, request, event_id):
        event = get_object_or_404(CalendarEvent, id=event_id, calendar__user=request.user)

        # Store event info in session for the photo editor
        request.session['edit_event_data'] = {
            'event_id': event.id,
            'month': event.month,
            'day': event.day,
            'event_name': event.event_name,
            'return_to_edit': True,
        }

        # Redirect to photo editor upload
        return redirect('calendars:photo_editor_upload', year=event.calendar.year)


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
        calendar = get_object_or_404(Calendar, year=year, user=request.user)

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
        calendar = get_object_or_404(Calendar, year=year, user=request.user)

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
        temp_path = temp_tokens.get(token)

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
        calendar = get_object_or_404(Calendar, year=year, user=request.user)

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
        calendar = get_object_or_404(Calendar, year=year, user=request.user)

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
