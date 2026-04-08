from django.core.management.base import BaseCommand
from apps.calendars.models import CalendarEvent, Calendar
import os


class Command(BaseCommand):
    help = 'Check which calendar event images are missing for PDF generation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--calendar-id',
            type=int,
            help='Check specific calendar by ID',
        )
        parser.add_argument(
            '--year',
            type=int,
            help='Check calendars for specific year',
        )

    def handle(self, *args, **options):
        calendars = Calendar.objects.all()

        if options['calendar_id']:
            calendars = calendars.filter(id=options['calendar_id'])
        elif options['year']:
            calendars = calendars.filter(year=options['year'])

        for calendar in calendars:
            self.stdout.write(self.style.SUCCESS(f"\n{'=' * 80}"))
            self.stdout.write(self.style.SUCCESS(f"Calendar: {calendar.year} - {calendar.calendar_year.name if calendar.calendar_year else 'Unnamed'}"))
            self.stdout.write(self.style.SUCCESS(f"{'=' * 80}"))

            events = CalendarEvent.objects.filter(calendar=calendar).order_by('month', 'day')

            missing_images = []
            for event in events:
                if event.image:
                    image_path = event.image.path
                    if not os.path.exists(image_path):
                        missing_images.append({
                            'month': event.month,
                            'day': event.day,
                            'name': event.event_name,
                            'path': event.image.name,
                            'full_path': image_path
                        })
                        self.stdout.write(self.style.ERROR(
                            f"  {event.month}/{event.day}: {event.event_name}"
                        ))
                        self.stdout.write(self.style.ERROR(
                            f"    Missing: {image_path}"
                        ))
                        if event.full_image:
                            full_exists = os.path.exists(event.full_image.path)
                            self.stdout.write(
                                f"    Full image: {event.full_image.path} "
                                f"({'EXISTS' if full_exists else 'MISSING'})"
                            )

            if not missing_images:
                self.stdout.write(self.style.SUCCESS("  ✓ All images present!"))
            else:
                self.stdout.write(self.style.WARNING(
                    f"\n  Total missing images: {len(missing_images)}"
                ))
