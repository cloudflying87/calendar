#!/usr/bin/env python
"""
Script to regenerate missing cropped/thumbnail images from full images

This script:
1. Finds all EventMaster records with full_image but missing cropped image file
2. Regenerates the cropped version from the full image
3. Updates the database if needed

Usage:
    # From production server (inside web container)
    docker compose exec web python /app/regenerate_missing_thumbnails.py

    # Or from local development
    python manage.py shell < regenerate_missing_thumbnails.py
"""

import os
import sys
from pathlib import Path
from PIL import Image
from io import BytesIO

# Setup Django
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
django.setup()

from django.conf import settings
from django.core.files.base import ContentFile
from apps.calendars.models import EventMaster


def regenerate_thumbnail(event, target_width=320, target_height=200):
    """
    Regenerate cropped thumbnail from full image
    Based on CalendarEvent.resize_image() logic
    """
    if not event.full_image:
        print(f"  ❌ No full image for {event.name}")
        return False

    try:
        # Check if full image file exists
        if not event.full_image.storage.exists(event.full_image.name):
            print(f"  ❌ Full image file doesn't exist: {event.full_image.name}")
            return False

        # Open full image
        with event.full_image.open('rb') as f:
            img = Image.open(f)
            img = img.convert('RGB')

            # Calculate aspect ratios
            img_ratio = img.width / img.height
            target_ratio = target_width / target_height

            # Crop to target aspect ratio first
            if img_ratio > target_ratio:
                # Image is wider - crop width
                new_width = int(img.height * target_ratio)
                left = (img.width - new_width) // 2
                img = img.crop((left, 0, left + new_width, img.height))
            elif img_ratio < target_ratio:
                # Image is taller - crop height
                new_height = int(img.width / target_ratio)
                top = (img.height - new_height) // 2
                img = img.crop((0, top, img.width, top + new_height))

            # Resize to target dimensions
            img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

            # Save to bytes buffer
            buffer = BytesIO()
            img.save(buffer, 'JPEG', quality=85, optimize=True)
            buffer.seek(0)

            # Generate filename for cropped version
            full_name = Path(event.full_image.name)
            cropped_name = str(full_name).replace('full_', 'cropped_')
            cropped_name = cropped_name.replace('.jpeg', '.jpeg').replace('.jpg', '.jpg').replace('.png', '.jpeg')

            # Save to image field
            event.image.save(
                Path(cropped_name).name,
                ContentFile(buffer.read()),
                save=True
            )

            print(f"  ✅ Regenerated: {cropped_name}")
            return True

    except Exception as e:
        print(f"  ❌ Error regenerating thumbnail: {e}")
        return False


def main():
    """Find and regenerate all missing thumbnails"""

    print("=" * 80)
    print("🔧 Regenerating Missing Thumbnails from Full Images")
    print("=" * 80)
    print()

    # Find all EventMaster records with full images
    events_with_full = EventMaster.objects.exclude(full_image='')
    print(f"📊 Found {events_with_full.count()} events with full images")
    print()

    missing_count = 0
    regenerated_count = 0
    error_count = 0

    for event in events_with_full:
        # Check if cropped image exists
        if not event.image or not event.image.storage.exists(event.image.name):
            missing_count += 1
            print(f"[{missing_count}] {event.name} ({event.month}/{event.day})")
            print(f"  Missing: {event.image.name if event.image else '(no image field)'}")
            print(f"  Has full: {event.full_image.name}")

            # Regenerate
            if regenerate_thumbnail(event):
                regenerated_count += 1
            else:
                error_count += 1
            print()

    # Summary
    print("=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"🔍 Total events checked: {events_with_full.count()}")
    print(f"❌ Missing thumbnails: {missing_count}")
    print(f"✅ Successfully regenerated: {regenerated_count}")
    print(f"⚠️  Errors: {error_count}")
    print()

    if regenerated_count > 0:
        print("🎉 Thumbnails regenerated successfully!")
        print()
        print("Next steps:")
        print("1. Check your calendar - thumbnails should now appear")
        print("2. Consider migrating to R2 storage to prevent future data loss")
    elif missing_count == 0:
        print("✅ No missing thumbnails found - all good!")
    else:
        print("⚠️  Some thumbnails could not be regenerated")
        print("Check error messages above for details")


if __name__ == '__main__':
    main()
