from django import forms
from django.core.validators import FileExtensionValidator
from .models import Calendar, CalendarHeader, CalendarEvent, Holiday, CalendarYear, EventMaster, UserPDFSettings
from datetime import datetime
import calendar


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class CalendarForm(forms.ModelForm):
    calendar_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Optional: Name for this calendar version (e.g., Family, Work, etc.)'
        }),
        help_text="Give this calendar a name to distinguish it from others for the same year"
    )

    copy_from_calendar = forms.ModelChoiceField(
        queryset=Calendar.objects.none(),
        required=False,
        empty_label="Create blank calendar",
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Optionally copy events and photos from an existing calendar"
    )

    class Meta:
        model = Calendar
        fields = ['year']
        widgets = {
            'year': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1900,
                'max': 2100,
                'value': datetime.now().year
            })
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Populate copy_from_calendar options with user's existing calendars
        if self.user:
            self.fields['copy_from_calendar'].queryset = Calendar.objects.filter(
                user=self.user
            ).order_by('-year')

    def clean(self):
        cleaned_data = super().clean()
        year = cleaned_data.get('year')
        calendar_name = cleaned_data.get('calendar_name') or 'Default'

        if self.user and year:
            # Check if this specific combination already exists
            existing_calendar_year = CalendarYear.objects.filter(
                user=self.user,
                year=year,
                name=calendar_name
            ).first()

            if existing_calendar_year:
                raise forms.ValidationError(
                    f"You already have a calendar named '{calendar_name}' for {year}. "
                    f"Please choose a different name."
                )

        return cleaned_data


class ImageUploadForm(forms.Form):
    images = MultipleFileField(
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif'])],
        help_text="Select multiple images with MMDD_eventname.* or MMDD eventname.* format"
    )

    def clean_images(self):
        images = self.files.getlist('images')
        if not images:
            raise forms.ValidationError("Please select at least one image.")

        # Validate file size (max 10MB per file)
        max_size = 10 * 1024 * 1024  # 10MB
        for image in images:
            if image.size > max_size:
                raise forms.ValidationError(f"File {image.name} is too large. Maximum size is 10MB.")

        return images


class HeaderUploadForm(forms.ModelForm):
    class Meta:
        model = CalendarHeader
        fields = ['document', 'january_page']
        widgets = {
            'document': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf'
            }),
            'january_page': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 100,
                'value': 1
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['document'].validators = [
            FileExtensionValidator(allowed_extensions=['pdf'])
        ]
        self.fields['document'].help_text = "Upload a PDF document containing calendar headers"
        self.fields['january_page'].help_text = "Page number where January header starts"


class EventEditForm(forms.ModelForm):
    class Meta:
        model = CalendarEvent
        fields = ['event_name']
        widgets = {
            'event_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter event name',
                'maxlength': 255
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['event_name'].label = 'Event Name'
        self.fields['event_name'].help_text = 'Update the name for this event'


class HolidayManagementForm(forms.Form):
    """Form for managing holiday selections for a calendar"""

    def __init__(self, *args, **kwargs):
        calendar = kwargs.pop('calendar', None)
        super().__init__(*args, **kwargs)

        # Create fields for each holiday
        for holiday_code, holiday_name in Holiday.HOLIDAY_CHOICES:
            # Checkbox field for including the holiday
            self.fields[f'include_{holiday_code}'] = forms.BooleanField(
                required=False,
                label=f'Include {holiday_name}',
                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
            )

            # File field for holiday image
            self.fields[f'image_{holiday_code}'] = forms.ImageField(
                required=False,
                label=f'{holiday_name} Image',
                validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif'])],
                widget=forms.FileInput(attrs={
                    'class': 'form-control',
                    'accept': 'image/*'
                }),
                help_text='Optional image for this holiday'
            )

        # Pre-populate with existing holiday selections if calendar exists
        if calendar:
            existing_holidays = Holiday.objects.filter(calendar=calendar)
            for holiday in existing_holidays:
                self.fields[f'include_{holiday.holiday_name}'].initial = True
                # Note: We can't pre-populate file fields with existing images
                # Users will need to re-upload if they want to change images

    def save(self, calendar):
        """Save the holiday selections for the given calendar"""
        # First, delete all existing holidays for this calendar
        Holiday.objects.filter(calendar=calendar).delete()

        # Create new holiday instances based on form data
        for holiday_code, holiday_name in Holiday.HOLIDAY_CHOICES:
            include_field = f'include_{holiday_code}'
            image_field = f'image_{holiday_code}'

            if self.cleaned_data.get(include_field):
                image = self.cleaned_data.get(image_field)
                holiday = Holiday.objects.create(
                    calendar=calendar,
                    holiday_name=holiday_code,
                    include_image=bool(image),
                    image=image
                )


class AddEventToMasterListForm(forms.Form):
    """Form for adding a calendar event to the master event list"""

    EVENT_TYPE_CHOICES = [
        ('custom', 'Custom Event'),
        ('birthday', 'Birthday'),
        ('anniversary', 'Anniversary'),
    ]

    master_event_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter the master event name'
        }),
        help_text="Name for this event in your master list"
    )

    event_type = forms.ChoiceField(
        choices=EVENT_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Type of event for automatic naming"
    )

    birth_year = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': 1900,
            'max': 2100,
            'placeholder': 'Year of birth'
        }),
        help_text="Birth year for automatic age calculation"
    )

    anniversary_year = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': 1900,
            'max': 2100,
            'placeholder': 'Anniversary year'
        }),
        help_text="Year of anniversary for automatic calculation"
    )


    event_group = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="No group",
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Optional: Add this event to a group"
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        event = kwargs.pop('event', None)
        super().__init__(*args, **kwargs)

        if user:
            from .models import EventGroup
            self.fields['event_group'].queryset = EventGroup.objects.filter(user=user)

        if event:
            # Pre-populate with event name
            self.initial['master_event_name'] = event.event_name

    def clean(self):
        cleaned_data = super().clean()
        event_type = cleaned_data.get('event_type')
        birth_year = cleaned_data.get('birth_year')
        anniversary_year = cleaned_data.get('anniversary_year')

        if event_type == 'birthday' and not birth_year:
            raise forms.ValidationError("Birth year is required for birthday events.")

        if event_type == 'anniversary' and not anniversary_year:
            raise forms.ValidationError("Anniversary year is required for anniversary events.")

        return cleaned_data


class CalendarEditForm(forms.Form):
    """Form for editing calendar name"""
    calendar_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter calendar name (e.g., Family, Work, etc.)'
        }),
        help_text="Name for this calendar version"
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.calendar = kwargs.pop('calendar', None)
        super().__init__(*args, **kwargs)

        # Pre-populate with current name
        if self.calendar and self.calendar.calendar_year:
            self.fields['calendar_name'].initial = self.calendar.calendar_year.name

    def clean_calendar_name(self):
        calendar_name = self.cleaned_data.get('calendar_name')

        if not calendar_name:
            raise forms.ValidationError("Calendar name cannot be empty.")

        # Check if this name already exists for this user/year (excluding current calendar)
        if self.user and self.calendar:
            existing = CalendarYear.objects.filter(
                user=self.user,
                year=self.calendar.year,
                name=calendar_name
            ).exclude(id=self.calendar.calendar_year.id if self.calendar.calendar_year else None).exists()

            if existing:
                raise forms.ValidationError(
                    f"You already have a calendar named '{calendar_name}' for {self.calendar.year}. "
                    f"Please choose a different name."
                )

        return calendar_name


class MasterEventForm(forms.ModelForm):
    """Form for creating and editing master events"""

    # Single date input replaces the separate month/day dropdowns
    date = forms.CharField(
        label='Date',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'MM/DD or MM/DD/YYYY',
            'id': 'id_date',
            'autocomplete': 'off',
            'maxlength': '10',
        }),
    )

    # Hidden fields — populated from the date field in clean()
    month = forms.IntegerField(required=False, widget=forms.HiddenInput())
    day = forms.IntegerField(required=False, widget=forms.HiddenInput())

    # Group multi-select — choices populated in __init__ from user's EventGroups
    group_names = forms.MultipleChoiceField(
        label='Groups',
        required=False,
        choices=[],
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'group-checkbox-list'}),
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Default event type to birthday for new events
        if not self.instance.pk:
            self.fields['event_type'].initial = 'birthday'

        # Pre-populate date field from existing instance
        if self.instance.pk and self.instance.month and self.instance.day:
            self.fields['date'].initial = f"{self.instance.month:02d}/{self.instance.day:02d}"

        # Populate group choices from the user's EventGroups
        if user:
            from .models import EventGroup
            group_names = list(
                EventGroup.objects.filter(user=user).values_list('name', flat=True).order_by('name')
            )
            self.fields['group_names'].choices = [(name, name) for name in group_names]
            # Pre-select groups that match existing EventGroup names
            if self.instance.pk and self.instance.groups:
                current = [g.strip() for g in self.instance.groups.split(',') if g.strip()]
                self.fields['group_names'].initial = [g for g in current if g in group_names]

    def clean_date(self):
        date_str = self.cleaned_data.get('date', '').strip()
        if not date_str:
            raise forms.ValidationError("Date is required.")

        parts = date_str.replace('-', '/').split('/')
        try:
            if len(parts) == 2:
                month, day, year = int(parts[0]), int(parts[1]), None
            elif len(parts) == 3:
                month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
            else:
                raise ValueError
        except ValueError:
            raise forms.ValidationError("Enter date as MM/DD or MM/DD/YYYY.")

        if not (1 <= month <= 12):
            raise forms.ValidationError("Month must be between 1 and 12.")
        if not (1 <= day <= 31):
            raise forms.ValidationError("Day must be between 1 and 31.")
        if year is not None and not (1900 <= year <= 2100):
            raise forms.ValidationError("Year must be between 1900 and 2100.")

        return {'month': month, 'day': day, 'year': year}

    def clean(self):
        cleaned_data = super().clean()

        # Populate month/day from the parsed date field
        date_data = cleaned_data.get('date')
        if date_data and isinstance(date_data, dict):
            cleaned_data['month'] = date_data['month']
            cleaned_data['day'] = date_data['day']
            # Auto-fill year_occurred from the date if not already entered
            if date_data['year'] and not cleaned_data.get('year_occurred'):
                cleaned_data['year_occurred'] = date_data['year']

        # Convert selected group checkboxes to comma-separated string
        group_names = cleaned_data.pop('group_names', [])
        cleaned_data['groups'] = ', '.join(group_names) if group_names else ''

        return cleaned_data

    class Meta:
        model = EventMaster
        fields = ['name', 'event_type', 'month', 'day', 'year_occurred', 'groups', 'description', 'image']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter event or person name',
                'required': True
            }),
            'event_type': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_event_type'
            }),
            'year_occurred': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional: Year (e.g., 1990)',
                'min': 1900,
                'max': 2100,
                'id': 'id_year_occurred'
            }),
            'groups': forms.HiddenInput(attrs={'id': 'id_groups'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional: Add notes or description',
                'id': 'id_description'
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
                'id': 'id_image',
                'style': 'display: none;'
            })
        }


class UserPDFSettingsForm(forms.ModelForm):
    """Form for managing user PDF generation settings"""

    class Meta:
        model = UserPDFSettings
        fields = [
            'image_size', 'event_text_size', 'day_number_size',
            'text_transparency', 'text_bg_color', 'text_position',
            'layout_compactness'
        ]
        widgets = {
            'image_size': forms.RadioSelect(),
            'event_text_size': forms.RadioSelect(),
            'day_number_size': forms.RadioSelect(),
            'text_transparency': forms.NumberInput(attrs={'type': 'range', 'min': '0', 'max': '100', 'step': '1'}),
            'text_bg_color': forms.RadioSelect(),
            'text_position': forms.RadioSelect(),
            'layout_compactness': forms.RadioSelect(),
        }


class CalendarPDFOverrideForm(forms.ModelForm):
    """Form for managing per-calendar PDF setting overrides"""

    use_custom_settings = forms.BooleanField(
        required=False,
        initial=False,
        label="Use custom PDF settings for this calendar",
        help_text="Enable this to override your default PDF settings for this specific calendar"
    )

    class Meta:
        model = Calendar
        fields = [
            'pdf_override_image_size', 'pdf_override_event_text_size',
            'pdf_override_day_number_size', 'pdf_override_text_transparency',
            'pdf_override_text_bg_color', 'pdf_override_text_position',
            'pdf_override_layout_compactness'
        ]
        widgets = {
            'pdf_override_image_size': forms.RadioSelect(),
            'pdf_override_event_text_size': forms.RadioSelect(),
            'pdf_override_day_number_size': forms.RadioSelect(),
            'pdf_override_text_transparency': forms.NumberInput(attrs={'type': 'range', 'min': '0', 'max': '100', 'step': '1'}),
            'pdf_override_text_bg_color': forms.RadioSelect(),
            'pdf_override_text_position': forms.RadioSelect(),
            'pdf_override_layout_compactness': forms.RadioSelect(),
        }
        labels = {
            'pdf_override_image_size': 'Image Size',
            'pdf_override_event_text_size': 'Event Text Size',
            'pdf_override_day_number_size': 'Day Number Size',
            'pdf_override_text_transparency': 'Text Transparency',
            'pdf_override_text_bg_color': 'Text Background Color',
            'pdf_override_text_position': 'Text Position',
            'pdf_override_layout_compactness': 'Layout Compactness',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Check if any overrides are set
        if self.instance and self.instance.pk:
            has_overrides = any([
                self.instance.pdf_override_image_size,
                self.instance.pdf_override_event_text_size,
                self.instance.pdf_override_day_number_size,
                self.instance.pdf_override_text_transparency is not None,
                self.instance.pdf_override_text_bg_color,
                self.instance.pdf_override_text_position,
                self.instance.pdf_override_layout_compactness,
            ])
            self.fields['use_custom_settings'].initial = has_overrides