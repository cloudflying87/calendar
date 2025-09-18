from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, TemplateView
from django.views import View
from django.http import JsonResponse, HttpResponse, FileResponse
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


class CalendarListView(LoginRequiredMixin, ListView):
    model = Calendar
    template_name = 'calendars/calendar_list.html'
    context_object_name = 'calendars'
    paginate_by = 10

    def get_queryset(self):
        return Calendar.objects.filter(user=self.request.user)


class CalendarCreateView(LoginRequiredMixin, CreateView):
    model = Calendar
    form_class = CalendarForm
    template_name = 'calendars/calendar_create.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('calendars:calendar_detail', kwargs={'year': self.object.year})


class CalendarDetailView(LoginRequiredMixin, DetailView):
    model = Calendar
    template_name = 'calendars/calendar_detail.html'
    context_object_name = 'calendar'
    slug_field = 'year'
    slug_url_kwarg = 'year'

    def get_queryset(self):
        return Calendar.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['events_by_month'] = self.get_events_by_month()
        context['has_header'] = hasattr(self.object, 'header')
        context['generated_calendars'] = self.object.generated_pdfs.all()
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

            # Process all files as bulk upload (no cropping)
            for uploaded_file in uploaded_files:
                try:
                    # Parse filename to extract date and event name
                    parsed_data = CalendarEvent.parse_filename(uploaded_file.name)

                    if parsed_data:
                        month, day, event_name = parsed_data

                        # Create or update calendar event
                        event, created = CalendarEvent.objects.update_or_create(
                            calendar=calendar,
                            month=month,
                            day=day,
                            defaults={
                                'event_name': event_name,
                                'image': uploaded_file,
                                'original_filename': uploaded_file.name
                            }
                        )
                        created_events.append(event)
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
                pdf_file = generator.generate_with_headers()
            elif generation_type == 'combined':
                pdf_file = generator.generate_combined_spread()
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
        return render(request, 'calendars/edit_event.html', {
            'event': event,
            'calendar': event.calendar,
            'form': form
        })

    def post(self, request, event_id):
        event = get_object_or_404(CalendarEvent, id=event_id, calendar__user=request.user)
        form = EventEditForm(request.POST, instance=event)

        if form.is_valid():
            form.save()
            messages.success(request, f"Event '{event.event_name}' updated successfully.")
            return redirect('calendars:calendar_detail', year=event.calendar.year)

        return render(request, 'calendars/edit_event.html', {
            'event': event,
            'calendar': event.calendar,
            'form': form
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
        return render(request, 'calendars/photo_editor_upload.html', {
            'calendar': calendar,
        })

    def post(self, request, year):
        calendar = get_object_or_404(Calendar, year=year, user=request.user)

        # Get form data
        uploaded_file = request.FILES.get('photo')
        month = int(request.POST.get('month'))
        day = int(request.POST.get('day'))
        event_name = request.POST.get('event_name')

        if not uploaded_file:
            messages.error(request, "Please select a photo to upload.")
            return redirect('calendars:photo_editor_upload', year=year)

        # Save temporary file for cropping
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        for chunk in uploaded_file.chunks():
            temp_file.write(chunk)
        temp_file.close()

        # Store data in session for the crop view
        request.session['crop_data'] = {
            'temp_path': temp_file.name,
            'original_filename': uploaded_file.name,
            'month': month,
            'day': day,
            'event_name': event_name,
        }

        return redirect('calendars:photo_crop', year=year)


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

        # Create a URL for the temporary image by copying to media/temp
        import shutil
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
        os.makedirs(temp_dir, exist_ok=True)

        temp_filename = f"crop_{os.path.basename(crop_data['temp_path'])}"
        temp_media_path = os.path.join(temp_dir, temp_filename)
        shutil.copy2(crop_data['temp_path'], temp_media_path)

        temp_image_url = f"{settings.MEDIA_URL}temp/{temp_filename}"

        # Format event date
        event_date = f"{crop_data['month']:02d}/{crop_data['day']:02d}/{year}"

        return render(request, 'calendars/photo_crop.html', {
            'calendar': calendar,
            'temp_image_url': temp_image_url,
            'temp_image_path': crop_data['temp_path'],
            'original_filename': crop_data['original_filename'],
            'event_name': crop_data['event_name'],
            'month': crop_data['month'],
            'day': crop_data['day'],
            'event_date': event_date,
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

            # Save cropped image to a temporary file
            temp_cropped = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            image.save(temp_cropped.name, 'JPEG', quality=85, optimize=True)
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
                # Clean up temp media file
                temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
                temp_filename = f"crop_{os.path.basename(temp_image_path)}"
                temp_media_path = os.path.join(temp_dir, temp_filename)
                if os.path.exists(temp_media_path):
                    os.unlink(temp_media_path)
            except OSError:
                pass

            # Clear session data
            if 'crop_data' in request.session:
                del request.session['crop_data']

            action = "created" if created else "updated"
            messages.success(request, f"Event '{event_name}' {action} successfully with cropped photo.")
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
