from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from PIL import Image
import os
import re
import uuid
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


class EventGroup(models.Model):
    """Model representing a group of events that can be reused across calendars"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_groups')
    name = models.CharField(max_length=100, help_text="Name of the event group")
    description = models.TextField(blank=True, help_text="Description of this event group")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ['user', 'name']

    def __str__(self):
        return self.name


class EventMaster(models.Model):
    """Model representing a master event that can be reused across calendars"""

    EVENT_TYPE_CHOICES = [
        ('birthday', 'Birthday'),
        ('anniversary', 'Anniversary'),
        ('holiday', 'Holiday'),
        ('appointment', 'Appointment'),
        ('reminder', 'Reminder'),
        ('custom', 'Custom Event'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='master_events')
    name = models.CharField(max_length=255, help_text="Name of the event or person")
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPE_CHOICES,
        default='custom',
        help_text="Type of event"
    )
    month = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Month number (1-12)"
    )
    day = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        help_text="Day number (1-31)"
    )
    year_occurred = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1900), MaxValueValidator(2100)],
        help_text="Optional: The year this event originally occurred (for birthdays, anniversaries, etc.)"
    )
    groups = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated list of group names this event belongs to"
    )
    description = models.TextField(blank=True, help_text="Additional details about the event")
    image = models.ImageField(
        upload_to='master_events/%Y/%m/',
        blank=True,
        null=True,
        help_text="Default image for this event (will be copied to calendar events)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['month', 'day', 'name']

    def __str__(self):
        if self.year_occurred:
            return f"{self.name} ({self.month}/{self.day}) - Year: {self.year_occurred}"
        return f"{self.name} ({self.month}/{self.day})"

    def get_display_name(self, for_year=None, user=None):
        """Get display name with optional year calculation"""
        display_name = self.name

        # Check user preferences for showing age numbers
        show_numbers = True
        if user:
            try:
                preferences = user.event_preferences
                show_numbers = preferences.show_age_numbers
            except UserEventPreferences.DoesNotExist:
                show_numbers = True

        if self.year_occurred and for_year and show_numbers:
            years_since = for_year - self.year_occurred

            if self.event_type == 'birthday' and years_since >= 0:
                # Calculate age for birthdays
                ordinal = self._get_ordinal(years_since)
                display_name = f"{self.name}'s {ordinal} Birthday"
            elif self.event_type == 'anniversary' and years_since > 0:
                # Calculate years for anniversaries
                ordinal = self._get_ordinal(years_since)
                display_name = f"{self.name} - {ordinal} Anniversary"
            elif years_since > 0:
                # For other events with year_occurred
                display_name = f"{self.name} ({years_since} years)"
        elif self.event_type == 'birthday':
            display_name = f"{self.name}'s Birthday"
        elif self.event_type == 'anniversary':
            display_name = f"{self.name} Anniversary"

        return display_name

    def _get_ordinal(self, number):
        """Convert number to ordinal (1st, 2nd, 3rd, etc.)"""
        if 10 <= number % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(number % 10, 'th')
        return f"{number}{suffix}"

    def get_groups_list(self):
        """Get list of groups from comma-separated string"""
        if self.groups:
            return [g.strip() for g in self.groups.split(',') if g.strip()]
        return []

    def set_groups_list(self, group_names):
        """Set groups from a list of group names"""
        self.groups = ', '.join(group_names)

    def add_to_group(self, group_name):
        """Add this event to a group"""
        groups = self.get_groups_list()
        if group_name not in groups:
            groups.append(group_name)
            self.set_groups_list(groups)
            self.save()

    def remove_from_group(self, group_name):
        """Remove this event from a group"""
        groups = self.get_groups_list()
        if group_name in groups:
            groups.remove(group_name)
            self.set_groups_list(groups)
            self.save()


class CalendarYear(models.Model):
    """Model to support multiple calendars per year"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calendar_years')
    year = models.IntegerField(
        validators=[MinValueValidator(1900), MaxValueValidator(2100)],
        help_text="The year for calendars"
    )
    name = models.CharField(
        max_length=100,
        help_text="Name to identify this calendar version",
        default="Default"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year', 'name']
        unique_together = ['user', 'year', 'name']

    def __str__(self):
        return f"{self.year} - {self.name}"


class UserEventPreferences(models.Model):
    """Model for storing user preferences for event management"""

    ADD_TO_MASTER_CHOICES = [
        ('always', 'Always add to master list'),
        ('ask', 'Ask me each time'),
        ('never', 'Never add to master list'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='event_preferences')
    add_to_master_list = models.CharField(
        max_length=10,
        choices=ADD_TO_MASTER_CHOICES,
        default='ask',
        help_text="When creating calendar events, how to handle master list"
    )
    show_age_numbers = models.BooleanField(
        default=True,
        help_text="Show age numbers for birthdays and anniversary years (e.g., '25th Birthday' vs 'Birthday')"
    )
    default_groups = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated list of default groups for new master events"
    )

    # Image combination preferences
    IMAGE_LAYOUT_CHOICES = [
        ('auto', 'Automatic - System chooses best layout'),
        ('side_by_side', 'Side by side - Images placed horizontally'),
        ('top_bottom', 'Top/Bottom - Images stacked vertically'),
        ('grid', 'Grid - Always use 2x2 grid layout'),
    ]

    image_combination_layout = models.CharField(
        max_length=15,
        choices=IMAGE_LAYOUT_CHOICES,
        default='auto',
        help_text="Default layout for combining multiple event images"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Event preferences for {self.user.username}"


class Calendar(models.Model):
    """Model representing a calendar for a specific year"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calendars')
    year = models.IntegerField(
        validators=[MinValueValidator(1900), MaxValueValidator(2100)],
        help_text="The year for this calendar"
    )
    calendar_year = models.ForeignKey(
        CalendarYear,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calendars',
        help_text="Optional: Link to a specific calendar year version"
    )
    public_share_token = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        unique=True,
        help_text="Token for public sharing - allows viewing without login"
    )
    is_publicly_shared = models.BooleanField(
        default=False,
        help_text="Whether this calendar is publicly shareable"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year']
        unique_together = ['user', 'year', 'calendar_year']

    def __str__(self):
        if self.calendar_year:
            return f"Calendar {self.year} - {self.calendar_year.name}"
        return f"Calendar {self.year}"

    def get_user_permission(self, user):
        """Get the permission level for a user on this calendar"""
        # Handle anonymous users
        if not user.is_authenticated:
            return None

        if self.user == user:
            return 'owner'

        try:
            share = self.shares.get(shared_with=user)
            return share.permission_level
        except CalendarShare.DoesNotExist:
            return None

    def can_view(self, user):
        """Check if user can view this calendar"""
        return self.get_user_permission(user) is not None

    def can_edit(self, user):
        """Check if user can edit this calendar"""
        permission = self.get_user_permission(user)
        return permission in ['owner', 'editor']

    def can_share(self, user):
        """Check if user can share this calendar (only owners can share)"""
        return self.get_user_permission(user) == 'owner'

    def get_shared_users(self):
        """Get all users this calendar is shared with"""
        return User.objects.filter(shared_calendars__calendar=self)

    def generate_public_share_token(self):
        """Generate a unique token for public sharing"""
        import secrets
        self.public_share_token = secrets.token_urlsafe(32)
        self.is_publicly_shared = True
        self.save()
        return self.public_share_token

    def get_public_share_url(self, request=None):
        """Get the public sharing URL for this calendar"""
        if not self.public_share_token:
            return None

        from django.urls import reverse
        if request:
            return request.build_absolute_uri(
                reverse('calendars:public_calendar', kwargs={'token': self.public_share_token})
            )
        return reverse('calendars:public_calendar', kwargs={'token': self.public_share_token})

    def disable_public_sharing(self):
        """Disable public sharing for this calendar"""
        self.public_share_token = None
        self.is_publicly_shared = False
        self.save()

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
    master_event = models.ForeignKey(
        EventMaster,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calendar_events',
        help_text="Optional: Link to a master event"
    )
    month = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Month number (1-12)"
    )
    day = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        help_text="Day number (1-31)"
    )
    event_name = models.CharField(max_length=255, help_text="Name of the event")
    combined_events = models.TextField(
        blank=True,
        help_text="Combined event names for dates with multiple events"
    )
    image = models.ImageField(
        upload_to=calendar_image_upload_path,
        help_text="Cropped image file for this event (used in PDF generation)"
    )
    full_image = models.ImageField(
        upload_to=calendar_image_upload_path,
        blank=True,
        null=True,
        help_text="Full-sized original image for digital calendar viewing"
    )
    original_filename = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['calendar', 'month', 'day', 'created_at']

    def __str__(self):
        return f"{self.calendar.year}-{self.month:02d}-{self.day:02d}: {self.event_name}"

    @property
    def event_date(self):
        """Get the event date as a datetime object"""
        from datetime import date
        return date(self.calendar.year, self.month, self.day)

    def get_display_name(self):
        """Get display name considering master event with year calculation"""
        if self.combined_events:
            return self.combined_events
        if self.master_event:
            return self.master_event.get_display_name(for_year=self.calendar.year, user=self.calendar.user)
        return self.event_name

    @classmethod
    def get_events_for_date(cls, calendar, month, day):
        """Get all events for a specific date"""
        return cls.objects.filter(calendar=calendar, month=month, day=day)

    @classmethod
    def has_multiple_events(cls, calendar, month, day):
        """Check if there are multiple events for a date"""
        return cls.get_events_for_date(calendar, month, day).count() > 1

    @classmethod
    def get_combined_display_name(cls, calendar, month, day):
        """Get combined display name for all events on a date"""
        events = cls.get_events_for_date(calendar, month, day)
        if events.count() <= 1:
            return events.first().get_display_name() if events.exists() else ""

        names = [event.get_display_name() for event in events]
        return " & ".join(names)

    @classmethod
    def get_combined_images(cls, calendar, month, day):
        """Get all images for events on a date"""
        events = cls.get_events_for_date(calendar, month, day)
        images = []
        full_images = []

        for event in events:
            if event.image:
                images.append(event.image)
            if event.full_image:
                full_images.append(event.full_image)

        return images, full_images

    @classmethod
    def create_combined_image(cls, calendar, month, day, target_width=320, target_height=200, layout_preference='auto'):
        """Create a combined image for multiple events on the same date

        layout_preference options:
        - 'auto': System chooses best layout (default)
        - 'side_by_side': Always use side-by-side for 2 images
        - 'top_bottom': Always use top/bottom for 2 images
        - 'grid': Always use grid layout
        """
        events = cls.get_events_for_date(calendar, month, day)
        if events.count() <= 1:
            return None

        try:
            from PIL import Image, ImageDraw, ImageFont
            import os
            from django.conf import settings
            from django.core.files.base import ContentFile
            import tempfile

            # Create a new image with the target dimensions
            combined_img = Image.new('RGB', (target_width, target_height), (255, 255, 255))

            event_list = list(events)
            num_events = len(event_list)

            if num_events == 2:
                # Handle layout preference for 2 images
                if layout_preference == 'top_bottom':
                    # Split horizontally (top/bottom)
                    for i, event in enumerate(event_list):
                        if event.image:
                            try:
                                with Image.open(event.image.path) as img:
                                    half_height = target_height // 2
                                    img_resized = img.resize((target_width, half_height), Image.Resampling.LANCZOS)
                                    y_pos = i * half_height
                                    combined_img.paste(img_resized, (0, y_pos))
                            except:
                                continue
                else:  # 'auto' or 'side_by_side'
                    # Split vertically (side by side) - default behavior
                    for i, event in enumerate(event_list):
                        if event.image:
                            try:
                                with Image.open(event.image.path) as img:
                                    half_width = target_width // 2
                                    img_resized = img.resize((half_width, target_height), Image.Resampling.LANCZOS)
                                    x_pos = i * half_width
                                    combined_img.paste(img_resized, (x_pos, 0))
                            except:
                                continue
            elif num_events == 3:
                # Top half for first image, bottom half split for other two
                for i, event in enumerate(event_list):
                    if event.image:
                        try:
                            with Image.open(event.image.path) as img:
                                if i == 0:
                                    # Top half
                                    half_height = target_height // 2
                                    img_resized = img.resize((target_width, half_height), Image.Resampling.LANCZOS)
                                    combined_img.paste(img_resized, (0, 0))
                                else:
                                    # Bottom half split
                                    quarter_height = target_height // 2
                                    half_width = target_width // 2
                                    img_resized = img.resize((half_width, quarter_height), Image.Resampling.LANCZOS)
                                    x_pos = (i - 1) * half_width
                                    combined_img.paste(img_resized, (x_pos, target_height // 2))
                        except:
                            continue
            elif num_events >= 4:
                # 2x2 grid
                for i, event in enumerate(event_list[:4]):  # Limit to 4 images
                    if event.image:
                        try:
                            with Image.open(event.image.path) as img:
                                half_width = target_width // 2
                                half_height = target_height // 2
                                img_resized = img.resize((half_width, half_height), Image.Resampling.LANCZOS)
                                x_pos = (i % 2) * half_width
                                y_pos = (i // 2) * half_height
                                combined_img.paste(img_resized, (x_pos, y_pos))
                        except:
                            continue

            # Add text overlay indicating number of events
            draw = ImageDraw.Draw(combined_img)
            text = f"{num_events} Events"

            try:
                # Try to use a bold font
                font = ImageFont.truetype("arial.ttf", 16)
            except:
                try:
                    font = ImageFont.truetype("DejaVuSans-Bold.ttf", 16)
                except:
                    font = ImageFont.load_default()

            # Get text bounding box
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Position text in top-right corner with background
            text_x = target_width - text_width - 5
            text_y = 5

            # Draw background rectangle
            draw.rectangle([text_x - 3, text_y - 2, text_x + text_width + 3, text_y + text_height + 2],
                         fill=(0, 0, 0, 128))

            # Draw text
            draw.text((text_x, text_y), text, fill=(255, 255, 255), font=font)

            # Save combined image
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            combined_img.save(temp_file.name, 'JPEG', quality=95)
            temp_file.close()

            return temp_file.name

        except Exception as e:
            print(f"Error creating combined image: {str(e)}")
            return None

    def add_additional_event(self, event_master):
        """Add an additional event to this date"""
        new_name = event_master.get_display_name(for_year=self.calendar.year, user=self.calendar.user)
        if self.combined_events:
            # Parse existing events and add new one
            events = [e.strip() for e in self.combined_events.split(' & ')]
            events.append(new_name)
        else:
            # Start with current event and add new one
            current = self.get_display_name()
            events = [current, new_name]

        self.combined_events = ' & '.join(events)
        self.event_name = f"Multiple Events ({len(events)})"
        self.save()

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
        # Skip auto-resize for bulk uploads (indicated by skip_resize kwarg)
        skip_resize = kwargs.pop('skip_resize', False)

        super().save(*args, **kwargs)

        if self.image and not skip_resize:
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
        unique_together = [['calendar', 'generation_type']]

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


class CalendarShare(models.Model):
    """Model for sharing calendars between users"""

    PERMISSION_CHOICES = [
        ('viewer', 'Viewer'),
        ('editor', 'Editor'),
    ]

    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE, related_name='shares')
    shared_with = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shared_calendars')
    shared_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calendars_shared_by_me')
    permission_level = models.CharField(max_length=10, choices=PERMISSION_CHOICES, default='viewer')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['calendar', 'shared_with']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.calendar} shared with {self.shared_with.username} ({self.permission_level})"


class CalendarInvitation(models.Model):
    """Model for calendar sharing invitations"""

    PERMISSION_CHOICES = [
        ('viewer', 'Viewer'),
        ('editor', 'Editor'),
    ]

    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField()
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invitations')
    permission_level = models.CharField(max_length=10, choices=PERMISSION_CHOICES, default='viewer')
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    accepted = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['calendar', 'email']
        ordering = ['-created_at']

    def __str__(self):
        return f"Invitation to {self.email} for {self.calendar}"

    def is_expired(self):
        """Check if the invitation has expired"""
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def accept_invitation(self, user):
        """Accept the invitation and create a CalendarShare"""
        if self.is_expired():
            raise ValueError("Invitation has expired")

        if self.accepted:
            raise ValueError("Invitation has already been accepted")

        # Create the share
        share, created = CalendarShare.objects.get_or_create(
            calendar=self.calendar,
            shared_with=user,
            defaults={
                'shared_by': self.invited_by,
                'permission_level': self.permission_level,
            }
        )

        # Mark invitation as accepted
        self.accepted = True
        self.save()

        return share


def calendar_header_upload_path(instance, filename):
    """Generate upload path for calendar header images"""
    return f'calendar_headers/{instance.calendar.user.id}/{instance.calendar.year}/{instance.month:02d}_{filename}'


class CalendarHeaderImage(models.Model):
    """Model for individual header images for each month of a calendar"""

    MONTH_CHOICES = [
        (0, 'Cover/Title Page'),
        (1, 'January'),
        (2, 'February'),
        (3, 'March'),
        (4, 'April'),
        (5, 'May'),
        (6, 'June'),
        (7, 'July'),
        (8, 'August'),
        (9, 'September'),
        (10, 'October'),
        (11, 'November'),
        (12, 'December'),
        (13, 'Back Cover'),
    ]

    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE, related_name='header_images')
    month = models.IntegerField(
        choices=MONTH_CHOICES,
        help_text="Month (0=Cover page, 1=January, etc.)"
    )
    image = models.ImageField(
        upload_to=calendar_header_upload_path,
        help_text="Header image for this month"
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional title/caption for this header"
    )
    original_filename = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['calendar', 'month']
        ordering = ['month']

    def __str__(self):
        month_name = self.get_month_display()
        return f"{self.calendar.year} {month_name} Header"

    @property
    def is_cover_page(self):
        """Check if this is the cover/title page"""
        return self.month == 0

    def get_month_name(self):
        """Get the full month name"""
        if self.month == 0:
            return "Cover"
        elif self.month == 13:
            return "Back Cover"
        import calendar
        return calendar.month_name[self.month] if 1 <= self.month <= 12 else "Unknown"

    def save(self, *args, **kwargs):
        """Override save to store original filename"""
        if self.image and hasattr(self.image, 'name'):
            self.original_filename = self.image.name
        super().save(*args, **kwargs)
