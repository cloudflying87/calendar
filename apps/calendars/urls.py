from django.urls import path
from . import views

app_name = 'calendars'

urlpatterns = [
    path('', views.CalendarListView.as_view(), name='calendar_list'),
    path('create/', views.CalendarCreateView.as_view(), name='calendar_create'),
    path('<int:year>/', views.CalendarDetailView.as_view(), name='calendar_detail'),
    path('<int:year>/upload/', views.ImageUploadView.as_view(), name='image_upload'),
    path('<int:year>/upload-edit/', views.PhotoEditorUploadView.as_view(), name='photo_editor_upload'),
    path('<int:year>/crop/', views.PhotoCropView.as_view(), name='photo_crop'),
    path('<int:year>/multi-crop/', views.MultiPhotoCropView.as_view(), name='multi_photo_crop'),
    path('<int:year>/process-crop/', views.ProcessCropView.as_view(), name='process_crop'),
    path('<int:year>/process-multi-crop/', views.ProcessMultiCropView.as_view(), name='process_multi_crop'),
    path('<int:year>/header/', views.HeaderUploadView.as_view(), name='header_upload'),
    path('<int:year>/holidays/', views.HolidayManagementView.as_view(), name='holiday_management'),
    path('<int:year>/generate/', views.GenerateCalendarView.as_view(), name='generate_calendar'),
    path('<int:year>/download/<str:generation_type>/', views.DownloadCalendarView.as_view(), name='download_calendar'),
    path('<int:year>/download-photos/', views.DownloadAllPhotosView.as_view(), name='download_all_photos'),
    path('<int:year>/delete/', views.DeleteCalendarView.as_view(), name='delete_calendar'),
    path('event/<int:event_id>/edit/', views.EditEventView.as_view(), name='edit_event'),
    path('event/<int:event_id>/edit-photo/', views.EditEventPhotoView.as_view(), name='edit_event_photo'),
    path('event/<int:event_id>/remove-photo/', views.RemoveEventPhotoView.as_view(), name='remove_event_photo'),
    path('event/<int:event_id>/delete/', views.DeleteEventView.as_view(), name='delete_event'),
    path('pdf/<int:pdf_id>/delete/', views.DeleteGeneratedPDFView.as_view(), name='delete_generated_pdf'),

    # Temporary image serving for photo cropping
    path('temp-image/<str:token>/', views.TempImageView.as_view(), name='temp_image'),

    # Calendar sharing URLs
    path('<int:year>/share/', views.CalendarShareView.as_view(), name='calendar_share'),
    path('<int:year>/unshare/', views.CalendarUnshareView.as_view(), name='calendar_unshare'),
    path('accept/<str:token>/', views.AcceptInvitationView.as_view(), name='accept_invitation'),
    path('shared/', views.SharedCalendarsView.as_view(), name='shared_calendars'),
]