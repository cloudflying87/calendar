# Calendar Builder Migration to Remote PostgreSQL + R2 CDN

Complete step-by-step guide for migrating Calendar Builder from local Docker infrastructure to remote PostgreSQL and Cloudflare R2 CDN.

## Overview

**Current Setup:**
- PostgreSQL in Docker container (local)
- Media files in Docker volumes (⚠️ **LOST during soft rebuild!**)
- Static files served by WhiteNoise
- All data on same server

**Target Setup:**
- PostgreSQL on remote server (172.16.29.5)
- Static/media files on Cloudflare R2 CDN
- Stateless Docker containers (no data loss on rebuild)

**Benefits:**
- ✅ **No more lost files on rebuild!** (stateless containers)
- ✅ Better performance (CDN edge caching)
- ✅ Better scalability (database scales independently)
- ✅ Lower server load (no database container)
- ✅ Easier backups (centralized database)
- ✅ Simplified deployment (no volume management)

---

## Prerequisites Checklist

- [ ] Remote PostgreSQL server at 172.16.29.5 is accessible
- [ ] Cloudflare R2 bucket created with API credentials
- [ ] Backups of current database created (./build.sh -b -d YYYYMMDD)
- [ ] SSH access to production server
- [ ] Local development environment ready
- [ ] Dependencies installed: django-storages[s3], boto3 (already in requirements)

---

## Phase 1: Database Setup

### Step 1: Create Database on Remote Server

SSH to the remote PostgreSQL server:

```bash
ssh user@172.16.29.5
```

Create the database and user:

```sql
sudo -u postgres psql

-- Create database
CREATE DATABASE calendar_db;

-- Create user with strong password
CREATE USER calendar_user WITH PASSWORD 'your-secure-password-here';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE calendar_db TO calendar_user;

-- Connect to new database
\c calendar_db

-- Grant schema permissions
GRANT ALL ON SCHEMA public TO calendar_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO calendar_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO calendar_user;

-- Exit
\q
```

### Step 2: Verify Remote Access

The server should already be configured for remote access (from HaleHub migration). Verify `pg_hba.conf` includes:

```conf
# /etc/postgresql/*/main/pg_hba.conf
host    calendar_db    calendar_user    172.16.29.0/24    md5
```

If not, add it and restart PostgreSQL:

```bash
sudo systemctl restart postgresql
```

### Step 3: Test Connection from Production Server

From your production server:

```bash
psql "postgresql://calendar_user:your-password@172.16.29.5:5432/calendar_db" -c "SELECT version();"
```

If this works, you're ready to proceed! ✅

---

## Phase 2: Staging Environment (Local Testing)

### Step 1: Fill in Staging Credentials

Copy the template and fill in your credentials:

```bash
cd ~/Coding/calendar
cp .env.staging.template .env.staging
nano .env.staging
```

Fill in:
- `DATABASE_URL` - Use your database credentials (calendar_user@172.16.29.5/calendar_db)
- `R2_ACCESS_KEY_ID` - From Cloudflare R2
- `R2_SECRET_ACCESS_KEY` - From Cloudflare R2
- `R2_BUCKET_NAME` - Your R2 bucket name (e.g., 'calendar-builder')
- `R2_ENDPOINT_URL` - Your R2 endpoint (from Cloudflare)
- `R2_PUBLIC_DOMAIN` - Your CDN domain (e.g., 'cdn.yourdomain.com')

### Step 2: Install Dependencies

The new R2/S3 storage dependencies are already in requirements/base.txt:

```bash
pip install -r requirements/base.txt
```

This includes:
- `django-storages[s3]>=1.14.2`
- `boto3>=1.34.0`

### Step 3: Set Up SSH Tunnel to Remote Database

For local testing, create an SSH tunnel to the remote database:

```bash
ssh -L 5433:172.16.29.5:5432 globemaster -N -f
```

Update `.env.staging` to use the tunnel:

```bash
DATABASE_URL=postgresql://calendar_user:your-password@localhost:5433/calendar_db
```

### Step 4: Test Staging Locally

```bash
export DJANGO_SETTINGS_MODULE=config.settings.staging
source .env.staging  # Or use direnv
python manage.py runserver 8050
```

Visit http://localhost:8050 and verify:
- [ ] Site loads without errors
- [ ] Can connect to remote database (check logs)
- [ ] Static files exist (may not load from R2 yet - that's OK)

---

## Phase 3: Database Migration

### Step 1: Export Current Database

On production server:

```bash
cd ~/path/to/calendar  # Or wherever your docker-compose.yml is

# Use the existing build.sh script to create a backup
./build.sh -b -d $(date +%Y%m%d)

# This creates backup in ./backups/calendar_backup_YYYYMMDD.sql
```

### Step 2: Clean the SQL Dump

The build.sh script creates clean backups already, but verify:

```bash
head -20 ./backups/calendar_backup_*.sql  # Check for DROP/CREATE statements
```

If needed, clean it:

```bash
cd ./backups
grep -v "DROP DATABASE" calendar_backup_*.sql > clean_backup.sql
grep -v "CREATE DATABASE" clean_backup.sql > final_backup.sql
```

### Step 3: Import to Remote Database

```bash
psql "postgresql://calendar_user:your-password@172.16.29.5:5432/calendar_db" < backups/calendar_backup_YYYYMMDD.sql
```

### Step 4: Verify Migration

```bash
# Count tables
psql "postgresql://calendar_user:your-password@172.16.29.5:5432/calendar_db" -c "\dt" | wc -l

# Check sample data
psql "postgresql://calendar_user:your-password@172.16.29.5:5432/calendar_db" -c "SELECT COUNT(*) FROM auth_user;"
psql "postgresql://calendar_user:your-password@172.16.29.5:5432/calendar_db" -c "SELECT COUNT(*) FROM calendars_calendarevent;"
psql "postgresql://calendar_user:your-password@172.16.29.5:5432/calendar_db" -c "SELECT COUNT(*) FROM calendars_eventmaster;"
```

---

## Phase 4: Media Files Migration

### Step 1: Count Existing Media Files

On production server:

```bash
# Check Docker volume for media files (if using docker volume)
docker volume inspect calendar_media_volume

# Or check persistent_media directory (if using bind mount)
find persistent_media -type f 2>/dev/null | wc -l
du -sh persistent_media/ 2>/dev/null

# Check what's actually in the Docker volume
docker run --rm -v calendar_media_volume:/data alpine ls -laR /data
```

### Step 2: Upload Media Files to R2

**IMPORTANT**: First, you need to extract media files from the Docker volume:

```bash
# On production server
cd ~/path/to/calendar

# Extract media files from Docker volume to persistent_media directory
docker run --rm -v calendar_media_volume:/source -v $(pwd)/persistent_media:/dest alpine sh -c "cp -r /source/* /dest/"

# Verify extraction
find persistent_media -type f | wc -l

# Now upload to R2 using staging environment
export DJANGO_SETTINGS_MODULE=config.settings.staging
python upload_media_to_r2.py
```

Or run directly in the container:

```bash
# Copy script to container
docker cp upload_media_to_r2.py calendar-web-1:/app/

# Run upload (this may take a while)
docker compose exec web python /app/upload_media_to_r2.py
```

The script will:
- Find all files in persistent_media/
- Upload each to R2 under media/ prefix
- Skip files that already exist
- Show progress and summary

### Step 3: Verify Media Files on R2

Check a few sample files in your browser:

```
https://your-cdn-domain.com/media/profile_images/sample.jpg
```

---

## Phase 5: Static Files Migration

### Step 1: Configure Production Settings

We'll do this in the next phase, but for now you can test collectstatic locally:

```bash
# With staging settings
export DJANGO_SETTINGS_MODULE=config.settings.staging
python manage.py collectstatic --noinput
```

This uploads all static files (CSS, JS, images) to R2.

---

## Phase 6: Production Configuration

### Step 1: Update Production Settings

Good news! Production settings have already been updated in `config/settings/production.py`.

The settings now automatically detect and use R2 storage when R2 credentials are provided:
- If R2 credentials exist → Use R2 for static/media
- If DATABASE_URL exists → Use remote PostgreSQL
- Otherwise → Fall back to local storage

**No code changes needed!** Just configure environment variables.

Original production.py code for reference:

```python
# Already implemented in config/settings/production.py:
# - Auto-detects R2 credentials
# - Uses config.storage.MediaStorage and config.storage.StaticStorage
# - Falls back to local storage if R2 not configured
```

### Step 2: Create Production .env File

Use the template provided:

```bash
# On production server
cd ~/path/to/calendar
cp .env.prod.template .env.prod
nano .env.prod
```

Fill in your actual credentials:

```bash
# Django Settings
DEBUG=False
SECRET_KEY=your-production-secret-key-CHANGE-THIS
ALLOWED_HOSTS=calendar.flyhomemnlab.com
DJANGO_SETTINGS_MODULE=config.settings.production

# Database (Remote PostgreSQL)
DATABASE_URL=postgresql://calendar_user:your-password@172.16.29.5:5432/calendar_db

# R2 Static/Media Files
R2_ACCESS_KEY_ID=your-r2-access-key-id
R2_SECRET_ACCESS_KEY=your-r2-secret-access-key
R2_BUCKET_NAME=calendar-builder
R2_ENDPOINT_URL=https://your-account-id.r2.cloudflarestorage.com
R2_PUBLIC_DOMAIN=cdn.yourdomain.com

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=Calendar Builder <noreply@calendar.flyhomemnlab.com>

# Cloudflare
CLOUDFLARE_TUNNEL_TOKEN=your-tunnel-token
DOMAIN_NAME=calendar.flyhomemnlab.com

# Project
PROJECT_NAME=calendar-builder
```

### Step 3: Use New Stateless Docker Compose

The new stateless docker-compose configuration is ready in `docker-compose.r2.yml`:

**Key changes:**
- ❌ No `db` service (using remote PostgreSQL)
- ❌ No `postgres_data` volume (database is remote)
- ❌ No `static_volume` or `media_volume` (using R2)
- ✅ Only `log_volume` for application logs
- ✅ Stateless containers that can rebuild anytime

Original configuration for reference:

See `docker-compose.r2.yml` for the complete configuration.

### Step 4: Use New Deployment Script

The new stateless deployment script is ready: `build_r2.sh`

**Features:**
- ✅ Tests remote database connection before deploying
- ✅ Verifies R2 credentials
- ✅ No backup/restore logic (database is external)
- ✅ Simplified deployment process
- ✅ Automatic static file collection to R2

Quick reference:

```bash
./build_r2.sh              # Standard deployment
./build_r2.sh --rebuild    # Full rebuild (stop, remove, rebuild images)
./build_r2.sh --collectstatic  # Just collect static files to R2
```

See `build_r2.sh` for full implementation.

---

## Phase 7: Deployment

### Step 1: Commit All Changes

```bash
git add .
git commit -m "feat: Migrate to remote PostgreSQL and R2 CDN"
git push origin main
```

### Step 2: Deploy

On production server:

```bash
cd ~/path/to/calendar

# First time deployment with rebuild
./build_r2.sh --rebuild

# Or standard deployment
./build_r2.sh
```

### Step 3: Verify

```bash
# Check containers (using new docker-compose file)
docker compose -f docker-compose.r2.yml ps

# Check logs
docker compose -f docker-compose.r2.yml logs -f web

# Test site
curl https://calendar.flyhomemnlab.com/

# Test static files from R2
curl -I https://cdn.yourdomain.com/static/css/base.css

# Test media files from R2 (if any were uploaded)
curl -I https://cdn.yourdomain.com/media/calendars/sample.jpg
```

---

## Rollback Plan

If something goes wrong:

### Quick Rollback

```bash
# Use the old docker-compose.yml
docker compose -f docker-compose.yml up -d

# Or revert config files
git checkout HEAD~1 config/settings/production.py

# Remove R2 credentials from .env.prod (will fall back to local storage)
nano .env.prod  # Comment out R2_* and DATABASE_URL variables
```

### Full Rollback

Your database backup is still available:

```bash
# Restore local database (if you reverted to old docker-compose.yml)
docker compose exec db psql -U calendar_builder_user calendar_builder_db < backups/calendar_backup_YYYYMMDD.sql

# Or use the build.sh restore feature
./build.sh -o -d YYYYMMDD
```

---

## Troubleshooting

### Database Connection Issues

**Problem:** Cannot connect to remote database

**Solutions:**
- Check firewall allows port 5432
- Verify pg_hba.conf has correct IP ranges
- Test connection with `psql` directly
- Check credentials in .env.prod

### R2 Upload Errors

**Problem:** 403 Forbidden when uploading to R2

**Solutions:**
- Verify R2 API token has "Admin Read & Write" permissions
- Check R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY are correct
- Ensure bucket name matches R2_BUCKET_NAME

**Problem:** Files upload but don't display (404)

**Solutions:**
- Set AWS_QUERYSTRING_AUTH = False
- Verify bucket is public or has correct access policy
- Check AWS_S3_CUSTOM_DOMAIN is set correctly
- Use @property for custom_domain in storage backend

### Static Files Not Loading

**Problem:** Static files 404 or wrong URL

**Solutions:**
- Check STATIC_URL points to CDN
- Verify collectstatic ran successfully
- Check storage backend location = 'static'
- Ensure custom_domain property returns correct domain

---

## Success Metrics

After migration, you should see:

- ✅ Site loads normally
- ✅ All static files (CSS, JS) load from CDN
- ✅ All media files (images) load from CDN
- ✅ Database queries work normally
- ✅ File uploads save to R2
- ✅ Docker uses ~70% less resources (no database container)
- ✅ Page load times improved (CDN caching)

---

## Next Steps

After successful migration:

1. **Monitor Performance**: Check page load times and CDN hit rates
2. **Set Up Backups**: Automate database backups on remote server
3. **Update Documentation**: Document new infrastructure
4. **Clean Up**: Remove old database volumes after confirming migration success

---

---

## Quick Reference: Migration Checklist

### Pre-Migration
- [ ] Create database on remote PostgreSQL (172.16.29.5)
- [ ] Set up Cloudflare R2 bucket and get credentials
- [ ] Backup current database: `./build.sh -b -d $(date +%Y%m%d)`
- [ ] Extract media files from Docker volume (if applicable)

### Migration Steps
1. [ ] Export database from local container
2. [ ] Import database to remote PostgreSQL
3. [ ] Upload media files to R2 using `upload_media_to_r2.py`
4. [ ] Create `.env.prod` with R2 and database credentials
5. [ ] Test with staging environment locally
6. [ ] Commit all changes to git
7. [ ] Deploy: `./build_r2.sh --rebuild`
8. [ ] Verify site loads and files are accessible
9. [ ] Monitor logs for any issues

### Post-Migration Cleanup
- [ ] Delete old Docker volumes (after confirming everything works)
- [ ] Update backup scripts for remote database
- [ ] Document R2 and database credentials in secure location
- [ ] Update documentation with new deployment process

---

**Last Updated:** 2026-04-08
**Calendar Builder Version:** 1.0
**Based on:** Keep-Logging migration guide
