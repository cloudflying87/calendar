from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Calendar, CalendarEvent, CalendarHeader, GeneratedCalendar, Holiday,
    CalendarShare, CalendarInvitation, EventGroup, EventMaster,
    CalendarYear, UserEventPreferences, CalendarHeaderImage
)


@admin.register(Calendar)
class CalendarAdmin(admin.ModelAdmin):
    list_display = ['year', 'event_count', 'has_header', 'created_at']
    list_filter = ['created_at']
    search_fields = ['year']
    readonly_fields = ['created_at', 'updated_at']

    def event_count(self, obj):
        return obj.events.count()
    event_count.short_description = "Events"

    def has_header(self, obj):
        return hasattr(obj, 'header')
    has_header.boolean = True
    has_header.short_description = "Has Header"


class CalendarEventInline(admin.TabularInline):
    model = CalendarEvent
    extra = 0
    fields = ['month', 'day', 'event_name', 'image', 'image_preview']
    readonly_fields = ['image_preview']

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image.url)
        return "No image"
    image_preview.short_description = "Preview"


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ['calendar', 'month', 'day', 'event_name', 'image_preview', 'created_at']
    list_filter = ['calendar', 'month', 'created_at']
    search_fields = ['event_name', 'calendar__year']
    readonly_fields = ['original_filename', 'created_at', 'updated_at', 'image_preview']
    list_select_related = ['calendar']

    fieldsets = (
        (None, {
            'fields': ('calendar', 'month', 'day', 'event_name')
        }),
        ('Images', {
            'fields': ('image', 'full_image', 'image_preview', 'original_filename')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" height="100" style="object-fit: cover;" />', obj.image.url)
        return "No image"
    image_preview.short_description = "Preview"


@admin.register(CalendarHeader)
class CalendarHeaderAdmin(admin.ModelAdmin):
    list_display = ['calendar', 'january_page', 'created_at']
    list_filter = ['created_at']
    search_fields = ['calendar__year']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(GeneratedCalendar)
class GeneratedCalendarAdmin(admin.ModelAdmin):
    list_display = ['calendar', 'generation_type', 'pdf_link', 'created_at']
    list_filter = ['generation_type', 'created_at']
    search_fields = ['calendar__year']
    readonly_fields = ['created_at']

    def pdf_link(self, obj):
        if obj.pdf_file:
            return format_html('<a href="{}" target="_blank">Download PDF</a>', obj.pdf_file.url)
        return "No PDF"
    pdf_link.short_description = "PDF File"


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ['calendar', 'holiday_name', 'calculated_date', 'include_image', 'image_preview', 'created_at']
    list_filter = ['holiday_name', 'include_image', 'created_at']
    search_fields = ['calendar__year', 'holiday_name']
    readonly_fields = ['calculated_date', 'created_at', 'image_preview']

    def calculated_date(self, obj):
        date = obj.get_date()
        if date:
            return date.strftime('%B %d, %Y')
        return "Unknown"
    calculated_date.short_description = "Date"

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image.url)
        return "No image"
    image_preview.short_description = "Preview"



@admin.register(CalendarShare)
class CalendarShareAdmin(admin.ModelAdmin):
    list_display = ["calendar", "shared_with", "shared_by", "permission_level", "created_at"]
    list_filter = ["permission_level", "created_at"]
    search_fields = ["calendar__year", "shared_with__username", "shared_with__email", "shared_by__username"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(CalendarInvitation)  
class CalendarInvitationAdmin(admin.ModelAdmin):
    list_display = ["calendar", "email", "invited_by", "permission_level", "accepted", "is_expired_status", "created_at"]
    list_filter = ["permission_level", "accepted", "created_at"]
    search_fields = ["calendar__year", "email", "invited_by__username"]
    readonly_fields = ["token", "created_at", "is_expired_status"]

    def is_expired_status(self, obj):
        return obj.is_expired()
    is_expired_status.boolean = True
    is_expired_status.short_description = "Expired"


@admin.register(EventGroup)
class EventGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'description', 'created_at']
    list_filter = ['created_at', 'user']
    search_fields = ['name', 'description', 'user__username']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(EventMaster)
class EventMasterAdmin(admin.ModelAdmin):
    list_display = ['name', 'event_type', 'month', 'day', 'year_occurred', 'user', 'image_preview', 'created_at']
    list_filter = ['event_type', 'month', 'user', 'created_at']
    search_fields = ['name', 'groups', 'description', 'user__username']
    readonly_fields = ['created_at', 'updated_at', 'image_preview']

    fieldsets = (
        (None, {
            'fields': ('user', 'name', 'event_type', 'month', 'day', 'year_occurred')
        }),
        ('Organization', {
            'fields': ('groups', 'description')
        }),
        ('Images', {
            'fields': ('image', 'full_image', 'image_preview')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image.url)
        return "No image"
    image_preview.short_description = "Preview"


@admin.register(CalendarYear)
class CalendarYearAdmin(admin.ModelAdmin):
    list_display = ['year', 'name', 'user', 'calendar_count', 'created_at']
    list_filter = ['year', 'user', 'created_at']
    search_fields = ['name', 'user__username']
    readonly_fields = ['created_at', 'updated_at']

    def calendar_count(self, obj):
        return obj.calendars.count()
    calendar_count.short_description = "Calendar Count"


@admin.register(UserEventPreferences)
class UserEventPreferencesAdmin(admin.ModelAdmin):
    list_display = ['user', 'add_to_master_list', 'show_age_numbers', 'image_combination_layout', 'created_at']
    list_filter = ['add_to_master_list', 'show_age_numbers', 'image_combination_layout', 'created_at']
    search_fields = ['user__username', 'default_groups']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(CalendarHeaderImage)
class CalendarHeaderImageAdmin(admin.ModelAdmin):
    list_display = ['calendar', 'month_name', 'title', 'image_preview', 'created_at']
    list_filter = ['month', 'calendar__year', 'created_at']
    search_fields = ['title', 'calendar__year', 'original_filename']
    readonly_fields = ['original_filename', 'created_at', 'updated_at', 'image_preview']

    fieldsets = (
        (None, {
            'fields': ('calendar', 'month', 'title')
        }),
        ('Image', {
            'fields': ('image', 'image_preview', 'original_filename')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def month_name(self, obj):
        return obj.get_month_display()
    month_name.short_description = "Month"

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" height="60" style="object-fit: cover;" />', obj.image.url)
        return "No image"
    image_preview.short_description = "Preview"
