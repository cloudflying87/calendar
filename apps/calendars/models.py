from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from PIL import Image
import os
import re
from datetime import datetime, date, timedelta
import calendar as cal


def calendar_image_upload_path(instance, filename):
    """Generate upload path for calendar images"""
    return f'calendar_images/{instance.calendar.year}/{filename}'


def header_document_upload_path(instance, filename):
    """Generate upload path for header documents"""
    return f'calendar_headers/{instance.calendar.year}/{filename}'


def holiday_image_upload_path(instance, filename):
    """Generate upload path for holiday images"""
    return f'holiday_images/{instance.calendar.year}/{filename}'


class HolidayCalculator:
    """Helper class to calculate holiday dates for a given year"""

    @staticmethod
    def get_holiday_date(holiday_name, year):
        """Calculate the date for a specific holiday in a given year"""
        try:
            if holiday_name == 'new_years':
                return date(year, 1, 1)
            elif holiday_name == 'memorial_day':
                # Last Monday in May
                last_monday = HolidayCalculator._get_last_monday_of_month(year, 5)
                return last_monday
            elif holiday_name == 'independence_day':
                return date(year, 7, 4)
            elif holiday_name == 'labor_day':
                # First Monday in September
                first_monday = HolidayCalculator._get_first_monday_of_month(year, 9)
                return first_monday
            elif holiday_name == 'thanksgiving':
                # Fourth Thursday in November
                fourth_thursday = HolidayCalculator._get_nth_weekday_of_month(year, 11, 3, 4)  # 3=Thursday, 4=fourth
                return fourth_thursday
            elif holiday_name == 'christmas':
                return date(year, 12, 25)
            elif holiday_name == 'easter':
                return HolidayCalculator._calculate_easter(year)
            elif holiday_name == 'mothers_day':
                # Second Sunday in May
                second_sunday = HolidayCalculator._get_nth_weekday_of_month(year, 5, 6, 2)  # 6=Sunday, 2=second
                return second_sunday
            elif holiday_name == 'fathers_day':
                # Third Sunday in June
                third_sunday = HolidayCalculator._get_nth_weekday_of_month(year, 6, 6, 3)  # 6=Sunday, 3=third
                return third_sunday
            else:
                return None
        except Exception:
            return None

    @staticmethod
    def _get_first_monday_of_month(year, month):
        """Get the first Monday of a given month"""
        first_day = date(year, month, 1)
        days_ahead = 0 - first_day.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return first_day + timedelta(days=days_ahead)

    @staticmethod
    def _get_last_monday_of_month(year, month):
        """Get the last Monday of a given month"""
        # Get the last day of the month
        last_day = cal.monthrange(year, month)[1]
        last_date = date(year, month, last_day)

        # Find the last Monday
        days_back = (last_date.weekday() - 0) % 7
        if days_back == 0:  # If last day is already Monday
            return last_date
        return last_date - timedelta(days=days_back)

    @staticmethod
    def _get_nth_weekday_of_month(year, month, weekday, n):
        """Get the nth occurrence of a weekday in a month
        weekday: 0=Monday, 1=Tuesday, ..., 6=Sunday
        n: 1=first, 2=second, etc.
        """
        first_day = date(year, month, 1)
        # Find the first occurrence of the weekday
        days_ahead = weekday - first_day.weekday()
        if days_ahead < 0:
            days_ahead += 7

        # Calculate the nth occurrence
        target_date = first_day + timedelta(days=days_ahead + (n - 1) * 7)

        # Make sure it's still in the same month
        if target_date.month == month:
            return target_date
        else:
            return None

    @staticmethod
    def _calculate_easter(year):
        """Calculate Easter Sunday using the algorithm"""
        # Using the anonymous Gregorian algorithm
        a = year % 19
        b = year // 100
        c = year % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month = (h + l - 7 * m + 114) // 31
        day = ((h + l - 7 * m + 114) % 31) + 1
        return date(year, month, day)


class Calendar(models.Model):
    """Model representing a calendar for a specific year"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calendars')
    year = models.IntegerField(
        validators=[MinValueValidator(1900), MaxValueValidator(2100)],
        help_text="The year for this calendar"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year']
        unique_together = ['user', 'year']

    def __str__(self):
        return f"Calendar {self.year}"

    def delete(self, *args, **kwargs):
        """Override delete to clean up associated files"""
        # Delete all event images
        for event in self.events.all():
            if event.image:
                try:
                    if os.path.exists(event.image.path):
                        os.remove(event.image.path)
                except OSError:
                    pass

        # Delete header document
        if hasattr(self, 'header') and self.header.document:
            try:
                if os.path.exists(self.header.document.path):
                    os.remove(self.header.document.path)
            except OSError:
                pass

        # Delete generated PDFs
        for generated_pdf in self.generated_pdfs.all():
            if generated_pdf.pdf_file:
                try:
                    if os.path.exists(generated_pdf.pdf_file.path):
                        os.remove(generated_pdf.pdf_file.path)
                except OSError:
                    pass

        # Delete holiday images
        for holiday in self.holidays.all():
            if holiday.image:
                try:
                    if os.path.exists(holiday.image.path):
                        os.remove(holiday.image.path)
                except OSError:
                    pass

        super().delete(*args, **kwargs)


class CalendarEvent(models.Model):
    """Model representing an event/image for a specific day"""
    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE, related_name='events')
    month = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Month number (1-12)"
    )
    day = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        help_text="Day number (1-31)"
    )
    event_name = models.CharField(max_length=255, help_text="Name of the event")
    image = models.ImageField(
        upload_to=calendar_image_upload_path,
        help_text="Image file for this event"
    )
    original_filename = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['calendar', 'month', 'day']
        ordering = ['calendar', 'month', 'day']

    def __str__(self):
        return f"{self.calendar.year}-{self.month:02d}-{self.day:02d}: {self.event_name}"

    @classmethod
    def parse_filename(cls, filename):
        """
        Parse MMDD_eventname.* or MMDD eventname.* format filename
        Returns (month, day, event_name) or None if format doesn't match
        """
        # Remove file extension
        name_without_ext = os.path.splitext(filename)[0]

        # Pattern: MMDD_eventname or MMDD eventname (space or underscore separator)
        pattern = r'^(\d{2})(\d{2})[_\s](.+)$'
        match = re.match(pattern, name_without_ext)

        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            event_name = match.group(3).replace('_', ' ').strip()

            # Validate month and day
            if 1 <= month <= 12 and 1 <= day <= 31:
                return month, day, event_name

        return None

    def save(self, *args, **kwargs):
        """Override save to resize image if needed"""
        super().save(*args, **kwargs)

        if self.image:
            self.resize_image()

    def resize_image(self, target_width=320, target_height=200):
        """Resize image to optimal calendar dimensions (320x200)"""
        if not self.image:
            return

        try:
            with Image.open(self.image.path) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')

                # Only resize if image is not already the target size
                if img.size != (target_width, target_height):
                    # For cropped images from photo editor, resize to exact dimensions
                    # For legacy uploads, maintain aspect ratio
                    if abs(img.width / img.height - target_width / target_height) < 0.1:
                        # Image already has correct aspect ratio, resize to exact dimensions
                        img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                    else:
                        # Legacy image, maintain aspect ratio and fit within target
                        ratio = min(target_width / img.width, target_height / img.height)
                        if ratio < 1:
                            new_width = int(img.width * ratio)
                            new_height = int(img.height * ratio)
                            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                    img.save(self.image.path, 'JPEG', quality=85, optimize=True)
        except Exception as e:
            print(f"Error resizing image {self.image.path}: {e}")


class CalendarHeader(models.Model):
    """Model for storing calendar header documents"""
    calendar = models.OneToOneField(Calendar, on_delete=models.CASCADE, related_name='header')
    document = models.FileField(
        upload_to=header_document_upload_path,
        help_text="PDF document containing calendar headers/tops"
    )
    january_page = models.IntegerField(
        default=1,
        help_text="Page number in the document that contains January header"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Header for {self.calendar.year}"


class GeneratedCalendar(models.Model):
    """Model for storing generated calendar PDFs"""
    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE, related_name='generated_pdfs')
    pdf_file = models.FileField(upload_to='generated_calendars/')
    generation_type = models.CharField(
        max_length=50,
        choices=[
            ('calendar_only', 'Calendar Only'),
            ('with_headers', 'With Headers'),
            ('combined', 'Combined Spread'),
        ],
        default='calendar_only'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.calendar.year} - {self.get_generation_type_display()}"


class Holiday(models.Model):
    """Model for storing holiday selections for a calendar"""

    HOLIDAY_CHOICES = [
        ('new_years', 'New Year\'s Day'),
        ('easter', 'Easter'),
        ('mothers_day', 'Mother\'s Day'),
        ('fathers_day', 'Father\'s Day'),
        ('memorial_day', 'Memorial Day'),
        ('independence_day', 'Independence Day'),
        ('labor_day', 'Labor Day'),
        ('thanksgiving', 'Thanksgiving'),
        ('christmas', 'Christmas'),
    ]

    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE, related_name='holidays')
    holiday_name = models.CharField(max_length=50, choices=HOLIDAY_CHOICES)
    include_image = models.BooleanField(default=False, help_text="Include an image for this holiday")
    image = models.ImageField(
        upload_to=holiday_image_upload_path,
        blank=True,
        null=True,
        help_text="Optional image for this holiday"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['calendar', 'holiday_name']
        ordering = ['calendar', 'holiday_name']

    def __str__(self):
        return f"{self.calendar.year} - {self.get_holiday_name_display()}"

    def get_date(self):
        """Get the calculated date for this holiday"""
        return HolidayCalculator.get_holiday_date(self.holiday_name, self.calendar.year)

    def get_month_day(self):
        """Get month and day as a tuple"""
        holiday_date = self.get_date()
        if holiday_date:
            return holiday_date.month, holiday_date.day
        return None, None

    def save(self, *args, **kwargs):
        """Override save to create corresponding CalendarEvent"""
        super().save(*args, **kwargs)

        # Create or update corresponding CalendarEvent
        month, day = self.get_month_day()
        if month and day:
            holiday_display_name = self.get_holiday_name_display()

            # Create or update the calendar event
            event, created = CalendarEvent.objects.update_or_create(
                calendar=self.calendar,
                month=month,
                day=day,
                defaults={
                    'event_name': holiday_display_name,
                    'image': self.image if self.include_image and self.image else None,
                    'original_filename': f"holiday_{self.holiday_name}.jpg" if self.image else ""
                }
            )

    def delete(self, *args, **kwargs):
        """Override delete to remove corresponding CalendarEvent"""
        month, day = self.get_month_day()
        if month and day:
            # Delete corresponding calendar event if it's a holiday event
            try:
                event = CalendarEvent.objects.get(
                    calendar=self.calendar,
                    month=month,
                    day=day,
                    event_name=self.get_holiday_name_display()
                )
                event.delete()
            except CalendarEvent.DoesNotExist:
                pass  # Event doesn't exist, nothing to delete

        super().delete(*args, **kwargs)
