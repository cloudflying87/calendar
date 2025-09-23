from django.urls import path
from . import views
from . import views_events

app_name = 'calendars'

urlpatterns = [
    path('', views.CalendarListView.as_view(), name='calendar_list'),
    path('create/', views.CalendarCreateView.as_view(), name='calendar_create'),
    path('id/<int:calendar_id>/', views.CalendarDetailByIdView.as_view(), name='calendar_detail_by_id'),
    path('id/<int:calendar_id>/simple/', views.CalendarSimpleByIdView.as_view(), name='calendar_simple_by_id'),
    path('<int:calendar_id>/apply-events/', views_events.ApplyMasterEventsView.as_view(), name='apply_master_events'),
    path('<int:year>/upload/', views.ImageUploadView.as_view(), name='image_upload'),
    path('<int:year>/upload-edit/', views.PhotoEditorUploadView.as_view(), name='photo_editor_upload'),
    path('upload-edit/', views.UnifiedPhotoEditorView.as_view(), name='unified_photo_editor'),
    path('crop/', views.UnifiedPhotoCropView.as_view(), name='unified_photo_crop'),
    path('process-crop/', views.UnifiedProcessCropView.as_view(), name='unified_process_crop'),
    path('<int:year>/crop/', views.PhotoCropView.as_view(), name='photo_crop'),
    path('<int:year>/bulk-crop/', views.BulkCropView.as_view(), name='bulk_crop'),
    path('<int:year>/multi-crop/', views.MultiPhotoCropView.as_view(), name='multi_photo_crop'),
    path('<int:year>/process-crop/', views.ProcessCropView.as_view(), name='process_crop'),
    path('<int:year>/process-multi-crop/', views.ProcessMultiCropView.as_view(), name='process_multi_crop'),
    path('<int:year>/header/', views.HeaderUploadView.as_view(), name='header_upload'),
    path('id/<int:calendar_id>/header-images/', views.CalendarHeaderImagesView.as_view(), name='header_images'),
    path('id/<int:calendar_id>/holidays/', views.HolidayManagementView.as_view(), name='holiday_management'),
    path('<int:year>/generate/', views.GenerateCalendarView.as_view(), name='generate_calendar'),
    path('<int:year>/download/<str:generation_type>/', views.DownloadCalendarView.as_view(), name='download_calendar'),
    path('id/<int:calendar_id>/view-pdf/<str:generation_type>/', views.CalendarPDFViewerView.as_view(), name='view_pdf'),
    path('<int:year>/download-photos/', views.DownloadAllPhotosView.as_view(), name='download_all_photos'),
    path('id/<int:calendar_id>/delete/', views.DeleteCalendarView.as_view(), name='delete_calendar'),
    path('<int:year>/simple/', views.CalendarSimpleView.as_view(), name='calendar_simple'),
    path('<int:year>/<str:calendar_name>/simple/', views.CalendarSimpleView.as_view(), name='calendar_simple_named'),
    path('<int:year>/<str:calendar_name>/', views.CalendarDetailView.as_view(), name='calendar_detail_named'),
    path('<int:year>/', views.CalendarDetailView.as_view(), name='calendar_detail'),
    path('event/<int:event_id>/edit/', views.EditEventView.as_view(), name='edit_event'),
    path('event/<int:event_id>/edit-photo/', views.EditEventPhotoView.as_view(), name='edit_event_photo'),
    path('event/<int:event_id>/remove-photo/', views.RemoveEventPhotoView.as_view(), name='remove_event_photo'),
    path('event/<int:event_id>/delete/', views.DeleteEventView.as_view(), name='delete_event'),
    path('id/<int:calendar_id>/bulk-delete-events/', views.BulkDeleteEventsView.as_view(), name='bulk_delete_events'),
    path('pdf/<int:pdf_id>/delete/', views.DeleteGeneratedPDFView.as_view(), name='delete_generated_pdf'),

    # Temporary image serving for photo cropping
    path('temp-image/<str:token>/', views.TempImageView.as_view(), name='temp_image'),

    # Calendar sharing URLs
    path('id/<int:calendar_id>/sharing/', views.CalendarSharingView.as_view(), name='calendar_sharing'),
    path('<int:year>/share/', views.CalendarShareView.as_view(), name='calendar_share'),
    path('<int:year>/unshare/', views.CalendarUnshareView.as_view(), name='calendar_unshare'),
    path('accept/<str:token>/', views.AcceptInvitationView.as_view(), name='accept_invitation'),
    path('shared/', views.SharedCalendarsView.as_view(), name='shared_calendars'),

    # Public Calendar View (no login required)
    path('public/<str:token>/', views.PublicCalendarView.as_view(), name='public_calendar'),

    # Digital Calendar View
    path('id/<int:calendar_id>/digital/', views.DigitalCalendarView.as_view(), name='digital_calendar'),

    # Public sharing management
    path('id/<int:calendar_id>/enable-public-share/', views.EnablePublicShareView.as_view(), name='enable_public_share'),
    path('id/<int:calendar_id>/disable-public-share/', views.DisablePublicShareView.as_view(), name='disable_public_share'),

    # Master Events URLs
    path('master-events/', views_events.MasterEventListView.as_view(), name='master_events'),
    path('master-events/create/', views_events.MasterEventCreateView.as_view(), name='master_event_create'),
    path('master-events/<int:pk>/edit/', views_events.MasterEventUpdateView.as_view(), name='master_event_edit'),
    path('master-events/<int:pk>/delete/', views_events.MasterEventDeleteView.as_view(), name='master_event_delete'),
    path('master-events/<int:pk>/upload-image/', views_events.MasterEventImageUploadView.as_view(), name='master_event_upload_image'),
    path('master-events/<int:pk>/remove-image/', views_events.MasterEventRemoveImageView.as_view(), name='master_event_remove_image'),
    path('master-events/<int:pk>/crop-photo/', views.MasterEventPhotoCropView.as_view(), name='master_event_crop_photo'),
    path('master-events/<int:pk>/process-crop/', views.MasterEventProcessCropView.as_view(), name='master_event_process_crop'),
    path('master-events/export/', views_events.ExportMasterEventsView.as_view(), name='export_master_events'),
    path('master-events/import/', views_events.ImportMasterEventsView.as_view(), name='import_master_events'),
    path('master-events/delete-all/', views_events.DeleteAllMasterEventsView.as_view(), name='delete_all_master_events'),

    # Event Groups URLs
    path('event-groups/', views_events.EventGroupListView.as_view(), name='event_groups'),
    path('event-groups/create/', views_events.EventGroupCreateView.as_view(), name='event_group_create'),
    path('event-groups/<int:pk>/edit/', views_events.EventGroupUpdateView.as_view(), name='event_group_edit'),
    path('event-groups/<int:pk>/delete/', views_events.EventGroupDeleteView.as_view(), name='event_group_delete'),

    # Settings page (central hub)
    path('settings/', views_events.SettingsView.as_view(), name='settings'),

    # Duplicate Events Management
    path('manage-duplicates/', views_events.ManageDuplicateEventsView.as_view(), name='manage_duplicates'),

    # User Preferences
    path('preferences/', views_events.user_preferences_view, name='user_preferences'),

    # Bulk Add to Master List
    path('<int:calendar_id>/bulk-add-to-master/', views_events.BulkAddToMasterListView.as_view(), name='bulk_add_to_master_list'),

    # Single Event to Master List
    path('event/<int:event_id>/add-to-master/', views_events.AddEventToMasterListView.as_view(), name='add_event_to_master_list'),

    # Tweak Combined Images
    path('event/<int:event_id>/tweak-combined-image/', views_events.TweakCombinedImageView.as_view(), name='tweak_combined_image'),

    # API endpoints
    path('api/master-events/', views_events.get_master_events_json, name='api_master_events'),
]