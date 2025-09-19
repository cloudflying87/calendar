from django import forms
from django.core.validators import FileExtensionValidator
from .models import Calendar, CalendarHeader, CalendarEvent, Holiday, CalendarYear
from datetime import datetime


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