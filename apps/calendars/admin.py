from django.contrib import admin
from django.utils.html import format_html
from .models import Calendar, CalendarEvent, CalendarHeader, GeneratedCalendar, Holiday


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
        ('Image', {
            'fields': ('image', 'image_preview', 'original_filename')
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
