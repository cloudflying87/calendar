#!/usr/bin/env python
"""
Script to upload existing media files to Cloudflare R2

This script:
1. Finds all media files in persistent_media/ directory
2. Uploads them to R2 bucket under media/ prefix
3. Preserves directory structure
4. Shows progress and summary

Usage:
    # From production server (inside web container)
    docker compose exec web python /app/upload_media_to_r2.py

    # Or from local staging environment
    export DJANGO_SETTINGS_MODULE=config.settings.staging
    python upload_media_to_r2.py
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple

# Setup Django
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
django.setup()

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files import File


def find_media_files() -> List[Path]:
    """
    Find all media files in persistent_media directory.
    Returns list of Path objects.
    """
    # Try both possible locations
    media_dirs = [
        Path('/app/persistent_media'),  # Docker container path
        Path(__file__).parent / 'persistent_media',  # Local path
    ]

    media_dir = None
    for path in media_dirs:
        if path.exists():
            media_dir = path
            break

    if not media_dir:
        # Try Docker volume path
        volume_path = Path('/app/media')
        if volume_path.exists():
            media_dir = volume_path
        else:
            print("❌ ERROR: No media directory found!")
            print("   Tried:")
            for path in media_dirs + [volume_path]:
                print(f"   - {path}")
            sys.exit(1)

    print(f"📁 Scanning: {media_dir}")

    files = []
    for root, dirs, filenames in os.walk(media_dir):
        for filename in filenames:
            # Skip hidden files and temp files
            if filename.startswith('.') or filename.endswith('~'):
                continue

            file_path = Path(root) / filename
            files.append(file_path)

    return files


def upload_file_to_r2(file_path: Path, media_root: Path) -> Tuple[bool, str]:
    """
    Upload a single file to R2.
    Returns (success, message)
    """
    try:
        # Get relative path from media root
        relative_path = file_path.relative_to(media_root)
        r2_path = str(relative_path)

        # Check if file already exists in R2
        if default_storage.exists(r2_path):
            return (True, f"⏭️  Skipped (already exists): {r2_path}")

        # Open and upload file
        with open(file_path, 'rb') as f:
            django_file = File(f, name=r2_path)
            default_storage.save(r2_path, django_file)

        return (True, f"✅ Uploaded: {r2_path}")

    except Exception as e:
        return (False, f"❌ Failed: {file_path} - {str(e)}")


def main():
    """Main upload process"""

    print("=" * 80)
    print("📤 Cloudflare R2 Media Upload Script")
    print("=" * 80)
    print()

    # Check R2 configuration
    if not hasattr(settings, 'AWS_S3_ENDPOINT_URL'):
        print("❌ ERROR: R2 storage not configured!")
        print("   Make sure you have R2_* environment variables set")
        print("   and DJANGO_SETTINGS_MODULE points to staging or production settings")
        sys.exit(1)

    print(f"🔧 Settings Module: {os.getenv('DJANGO_SETTINGS_MODULE')}")
    print(f"☁️  R2 Bucket: {settings.AWS_STORAGE_BUCKET_NAME}")
    print(f"🌐 CDN Domain: {settings.AWS_S3_CUSTOM_DOMAIN}")
    print()

    # Find all media files
    print("🔍 Finding media files...")
    files = find_media_files()

    if not files:
        print("⚠️  No media files found to upload!")
        return

    print(f"📊 Found {len(files)} files to process")
    print()

    # Confirm upload
    response = input("Continue with upload? [y/N]: ")
    if response.lower() not in ('y', 'yes'):
        print("❌ Upload cancelled")
        return

    print()
    print("🚀 Starting upload...")
    print("-" * 80)

    # Determine media root
    media_root = files[0].parent
    while media_root.name != 'persistent_media' and media_root.name != 'media':
        media_root = media_root.parent
        if media_root == media_root.parent:  # Reached filesystem root
            media_root = files[0].parent
            break

    # Upload files
    success_count = 0
    skip_count = 0
    fail_count = 0

    for i, file_path in enumerate(files, 1):
        success, message = upload_file_to_r2(file_path, media_root)
        print(f"[{i:04d}/{len(files):04d}] {message}")

        if success:
            if "Skipped" in message:
                skip_count += 1
            else:
                success_count += 1
        else:
            fail_count += 1

    # Summary
    print("-" * 80)
    print()
    print("=" * 80)
    print("📊 UPLOAD SUMMARY")
    print("=" * 80)
    print(f"✅ Uploaded:  {success_count}")
    print(f"⏭️  Skipped:   {skip_count} (already on R2)")
    print(f"❌ Failed:    {fail_count}")
    print(f"📦 Total:     {len(files)}")
    print()

    if fail_count > 0:
        print("⚠️  Some files failed to upload. Check error messages above.")
        sys.exit(1)
    else:
        print("🎉 All files uploaded successfully!")
        print()
        print("Next steps:")
        print("1. Test that media files are accessible from CDN")
        print(f"   Example: https://{settings.AWS_S3_CUSTOM_DOMAIN}/media/your-file.jpg")
        print("2. Update production .env to include R2 credentials")
        print("3. Deploy with new docker-compose.yml (no database, no volumes)")
        print("4. Run migration to move database to remote PostgreSQL")


if __name__ == '__main__':
    main()
