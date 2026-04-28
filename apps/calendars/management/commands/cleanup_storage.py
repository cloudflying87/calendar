"""
Management command to find and remove orphaned files in storage (R2/S3 or local).

Usage:
  python manage.py cleanup_storage --dry-run   # Show what would be deleted
  python manage.py cleanup_storage             # Delete orphaned files
  python manage.py cleanup_storage --prefix temp/  # Only check temp/ folder
"""

from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage
from django.db.models import Q
from apps.calendars.models import (
    CalendarEvent, CalendarHeader, GeneratedCalendar,
    Holiday, EventMaster,
)

try:
    from apps.calendars.models import CalendarHeaderImage
    HAS_HEADER_IMAGE = True
except ImportError:
    HAS_HEADER_IMAGE = False


def _iter_storage(prefix=''):
    """Yield every file key under prefix using paginated listdir."""
    dirs, files = default_storage.listdir(prefix)
    for filename in files:
        path = f"{prefix}/{filename}" if prefix else filename
        yield path
    for subdir in dirs:
        subpath = f"{prefix}/{subdir}" if prefix else subdir
        yield from _iter_storage(subpath)


def _collect_db_files():
    """Return a set of all file names referenced by database records."""
    names = set()

    for obj in CalendarEvent.objects.exclude(Q(image='') | Q(image=None)):
        names.add(obj.image.name)
    for obj in CalendarEvent.objects.exclude(Q(full_image='') | Q(full_image=None)):
        names.add(obj.full_image.name)

    for obj in EventMaster.objects.exclude(Q(image='') | Q(image=None)):
        names.add(obj.image.name)
    for obj in EventMaster.objects.exclude(Q(full_image='') | Q(full_image=None)):
        names.add(obj.full_image.name)

    for obj in CalendarHeader.objects.exclude(Q(document='') | Q(document=None)):
        names.add(obj.document.name)

    for obj in GeneratedCalendar.objects.exclude(Q(pdf_file='') | Q(pdf_file=None)):
        names.add(obj.pdf_file.name)

    for obj in Holiday.objects.exclude(Q(image='') | Q(image=None)):
        names.add(obj.image.name)

    if HAS_HEADER_IMAGE:
        for obj in CalendarHeaderImage.objects.exclude(Q(image='') | Q(image=None)):
            names.add(obj.image.name)

    return names


class Command(BaseCommand):
    help = 'Find and remove orphaned files in storage not referenced by any database record'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List orphaned files without deleting them',
        )
        parser.add_argument(
            '--prefix',
            default='',
            help='Only scan files under this storage prefix (e.g. "temp/" or "calendar_images/")',
        )
        parser.add_argument(
            '--delete-temp',
            action='store_true',
            help='Delete all files under temp/ regardless of DB references (temp files are never in DB)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        prefix = options['prefix'].rstrip('/')
        delete_temp = options['delete_temp']

        self.stdout.write('Collecting database file references...')
        db_files = _collect_db_files()
        self.stdout.write(f'  Found {len(db_files)} files referenced in database.')

        self.stdout.write(f'Scanning storage{f" under {prefix!r}" if prefix else ""}...')
        try:
            all_storage_files = list(_iter_storage(prefix))
        except NotImplementedError:
            self.stderr.write(
                'Storage backend does not support listdir(). '
                'Cannot enumerate files. Use the R2/S3 console instead.'
            )
            return

        self.stdout.write(f'  Found {len(all_storage_files)} files in storage.')

        orphaned = []
        temp_files = []
        for path in all_storage_files:
            if path.startswith('temp/'):
                temp_files.append(path)
            elif path not in db_files:
                orphaned.append(path)

        self.stdout.write(f'\n--- Results ---')
        self.stdout.write(f'Temp files (not in DB by design): {len(temp_files)}')
        self.stdout.write(f'Orphaned files (in storage, not in DB): {len(orphaned)}')
        self.stdout.write(f'Valid files (in both storage and DB): {len(all_storage_files) - len(temp_files) - len(orphaned)}')

        if orphaned:
            self.stdout.write('\nOrphaned files:')
            for path in sorted(orphaned):
                size = ''
                try:
                    size = f'  ({default_storage.size(path):,} bytes)'
                except Exception:
                    pass
                self.stdout.write(f'  {path}{size}')

        if temp_files and (delete_temp or dry_run):
            self.stdout.write('\nTemp files:')
            for path in sorted(temp_files):
                self.stdout.write(f'  {path}')

        if dry_run:
            total = len(orphaned) + (len(temp_files) if delete_temp else 0)
            self.stdout.write(f'\nDry run: would delete {total} file(s). Run without --dry-run to delete.')
            return

        deleted = 0
        errors = 0

        targets = list(orphaned)
        if delete_temp:
            targets += temp_files

        for path in targets:
            try:
                default_storage.delete(path)
                deleted += 1
                self.stdout.write(f'  Deleted: {path}')
            except Exception as e:
                errors += 1
                self.stderr.write(f'  Error deleting {path}: {e}')

        self.stdout.write(f'\nDone. Deleted {deleted} file(s), {errors} error(s).')
