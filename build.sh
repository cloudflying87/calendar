#!/bin/bash

# ============================================================================
# Django Project Build Script Template
# Based on Keep-Logging's proven deployment automation
# 
# CUSTOMIZE THESE VARIABLES FOR YOUR PROJECT:
# ============================================================================

# PROJECT CONFIGURATION - CHANGE THESE
PROJECT_NAME="calendar-builder"                    # ← CHANGE THIS
REMOTE_SERVER="your-user@your-server-ip"           # ← CHANGE THIS (optional)
REMOTE_BACKUP_DIR="/path/to/backups"               # ← CHANGE THIS (optional)

# Auto-generated container names (usually don't need to change)
DB_CONTAINER="${PROJECT_NAME}-db-1"
WEB_CONTAINER="${PROJECT_NAME}-web-1"
NGINX_CONTAINER="${PROJECT_NAME}-nginx-1"
CLOUDFLARED_CONTAINER="${PROJECT_NAME}-cloudflared-1"  # Optional

# Default values
BACKUP_all=false
BACKUP_data=false
BACKUP_local=false
REBUILD=false
SOFT_REBUILD=false
RESTORE=false
ALL=false
MIGRATE=false
DOWNLOAD=false
MIGRATION_FIX=false

# Load from environment file
source ./.env.prod 2>/dev/null || source ./.env 2>/dev/null || true
DB_NAME="${DB_NAME:-${PROJECT_NAME}_db}"
DB_USER="${DB_USER:-${PROJECT_NAME}_user}"

# Color codes for better output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to display help
show_help() {
    echo -e "${BLUE}Build Script - ${PROJECT_NAME} Deployment Tool${NC}"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo -e "${YELLOW}Options:${NC}"
    echo "  -h, --help        Show this help message"
    echo "  -d, --date DATE   Date for database filenames (required for backup/restore operations)"
    echo "  -b, --backup      Backup database (all 3 formats: data, full, clean)"
    echo "  -l, --local       Local backup (all formats without Docker)"
    echo "  -r, --rebuild     Full rebuild (stop, remove, prune, migrate & restore)"
    echo "  -s, --soft        Soft rebuild (preserves database, git pull & migrate only)"
    echo "  -o, --restore     Restore database from backup"
    echo "  -m, --migrate     Run Django migrations"
    echo "  -w, --download    Download backup from remote server"
    echo "  -f, --fixmigration Enable migration fixes for restore (use with -o or -r)"
    echo ""
    echo -e "${GREEN}Examples:${NC}"
    echo "  $0 -b -d 2024-01-15       # Backup with date 2024-01-15"
    echo "  $0 -l -d 2024-01-15       # Local backup with date 2024-01-15"
    echo "  $0 -r -d 2024-01-15       # Full rebuild with restore"
    echo "  $0 -s                     # Soft rebuild (no date needed)"
    echo "  $0 -w -d 2024-01-15       # Download backup from remote"
    echo "  $0 -r -d 2024-01-15 -f    # Full rebuild with migration fixes"
    echo ""
    echo -e "${YELLOW}Project Configuration:${NC}"
    echo "  Project Name: ${PROJECT_NAME}"
    echo "  Database: ${DB_NAME}"
    echo "  User: ${DB_USER}"
    echo "  Remote Server: ${REMOTE_SERVER:-'Not configured'}"
}

# Function to wait for database
wait_for_database() {
    echo -e "${YELLOW}Waiting for database to be ready...${NC}"
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if sudo docker exec $DB_CONTAINER pg_isready -U $DB_USER > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Database is ready!${NC}"
            return 0
        fi
        echo -e "${YELLOW}Waiting for database... (attempt $attempt/$max_attempts)${NC}"
        sleep 2
        ((attempt++))
    done
    
    echo -e "${RED}✗ ERROR: Database failed to become ready${NC}"
    return 1
}

# Function to create backup directory
ensure_backup_dir() {
    if [ ! -d "./backups" ]; then
        echo -e "${YELLOW}Creating backup directory...${NC}"
        mkdir -p ./backups
    fi
}

# Function to run Django migrations
run_migrations() {
    echo -e "${BLUE}Running Django migrations...${NC}"
    
    # Collect static files
    echo -e "${YELLOW}Collecting static files...${NC}"
    sudo docker compose exec web python manage.py collectstatic --noinput --clear
    echo -e "${GREEN}✓ Static files collected${NC}"
    
    # Check for new migrations
    echo -e "${YELLOW}Checking for new migrations...${NC}"
    sudo docker compose exec web python manage.py makemigrations --dry-run --verbosity=0 > /tmp/migration_check.log 2>&1
    if grep -q "would create" /tmp/migration_check.log; then
        echo -e "${YELLOW}New migrations detected, creating them...${NC}"
        # Add your app names here
        for app in core; do  # ← ADD YOUR APP NAMES HERE
            sudo docker compose exec web python manage.py makemigrations $app
        done
    else
        echo -e "${GREEN}✓ No new migrations needed${NC}"
    fi
    rm -f /tmp/migration_check.log
    
    # Apply all migrations
    echo -e "${YELLOW}Applying database migrations...${NC}"
    sudo docker compose exec web python manage.py migrate
    echo -e "${GREEN}✓ Migrations completed${NC}"
}

# Function to backup database (all formats)
backup_database() {
    local backup_date=$1
    local is_local=$2
    
    echo -e "${BLUE}Backing up database in all formats: $backup_date${NC}"
    
    if [ "$is_local" = true ]; then
        # Local backup without Docker - only exclude cache table
        local local_db_name="${DB_NAME}"  # Adjust if different in local setup
        pg_dump $local_db_name -a -O -T cache_table --format=plain --file=/Users/$(whoami)/backups/${PROJECT_NAME}_backup_${backup_date}_data.sql
        pg_dump $local_db_name -O -T cache_table --format=plain --file=/Users/$(whoami)/backups/${PROJECT_NAME}_backup_${backup_date}.sql
        pg_dump $local_db_name -c -O -T cache_table --format=plain --file=/Users/$(whoami)/backups/${PROJECT_NAME}_backup_${backup_date}_clean.sql
        
        echo -e "${GREEN}✓ Local backup completed${NC}"
        
        # Copy to remote if configured
        if [ -n "$REMOTE_SERVER" ] && [ "$REMOTE_SERVER" != "your-user@your-server-ip" ]; then
            echo -e "${YELLOW}Copying to remote server...${NC}"
            scp /Users/$(whoami)/backups/${PROJECT_NAME}_backup_${backup_date}*.sql $REMOTE_SERVER:$REMOTE_BACKUP_DIR/
        fi
    else
        # Docker backup
        ensure_backup_dir
        
        # Create all three backup formats - only exclude cache table
        sudo docker exec -it $DB_CONTAINER pg_dump -U $DB_USER $DB_NAME -a -O -T cache_table --format=plain --file=/var/lib/postgresql/data/${PROJECT_NAME}_backup_${backup_date}_data.sql
        sudo docker exec -it $DB_CONTAINER pg_dump -U $DB_USER $DB_NAME -O -T cache_table --format=plain --file=/var/lib/postgresql/data/${PROJECT_NAME}_backup_${backup_date}.sql
        sudo docker exec -it $DB_CONTAINER pg_dump -U $DB_USER $DB_NAME -c -O -T cache_table --format=plain --file=/var/lib/postgresql/data/${PROJECT_NAME}_backup_${backup_date}_clean.sql
        
        # Copy from container to host
        sudo docker cp $DB_CONTAINER:/var/lib/postgresql/data/${PROJECT_NAME}_backup_${backup_date}_data.sql ./backups/
        sudo docker cp $DB_CONTAINER:/var/lib/postgresql/data/${PROJECT_NAME}_backup_${backup_date}.sql ./backups/
        sudo docker cp $DB_CONTAINER:/var/lib/postgresql/data/${PROJECT_NAME}_backup_${backup_date}_clean.sql ./backups/
        
        # Copy to remote if configured
        if [ -n "$REMOTE_SERVER" ] && [ "$REMOTE_SERVER" != "your-user@your-server-ip" ]; then
            echo -e "${YELLOW}Copying to remote server...${NC}"
            scp ./backups/${PROJECT_NAME}_backup_${backup_date}*.sql $REMOTE_SERVER:$REMOTE_BACKUP_DIR/
        fi
        
        echo -e "${GREEN}✓ Docker backup completed${NC}"
    fi
}

# Function to download backup from remote
download_backup() {
    local backup_date=$1
    
    if [ -z "$REMOTE_SERVER" ] || [ "$REMOTE_SERVER" = "your-user@your-server-ip" ]; then
        echo -e "${RED}✗ Remote server not configured${NC}"
        return 1
    fi
    
    echo -e "${BLUE}Downloading backup from remote server: $backup_date${NC}"
    ensure_backup_dir
    
    # Download all backup formats
    for suffix in "_data.sql" ".sql" "_clean.sql"; do
        local filename="${PROJECT_NAME}_backup_${backup_date}${suffix}"
        if scp $REMOTE_SERVER:$REMOTE_BACKUP_DIR/$filename ./backups/ 2>/dev/null; then
            echo -e "${GREEN}✓ Downloaded: $filename${NC}"
        else
            echo -e "${YELLOW}⚠ Warning: Could not download $filename${NC}"
        fi
    done
    
    # List downloaded files
    ls -la ./backups/${PROJECT_NAME}_backup_${backup_date}* 2>/dev/null || echo -e "${RED}✗ No backup files found for date: $backup_date${NC}"
}

# Function to apply migration-specific fixes for restore compatibility
apply_migration_fixes() {
    echo -e "${YELLOW}Applying migration fixes for restore compatibility...${NC}"
    
    # First, clear django_migrations to avoid duplicate key conflicts
    echo -e "${YELLOW}Clearing django_migrations table to prevent duplicate key errors...${NC}"
    sudo docker exec -it $DB_CONTAINER psql -d $DB_NAME -U $DB_USER -c "TRUNCATE django_migrations CASCADE;"
    echo -e "${GREEN}✓ django_migrations table cleared${NC}"
    
    # Add project-specific migration fixes here
    sudo docker exec -i $DB_CONTAINER bash -c 'cat > /var/lib/postgresql/data/migration_fixes.sql << '\''EOF'\''
-- Migration fixes for restore compatibility
-- Add your project-specific fixes here

DO $$ 
BEGIN
    -- Example: Handle new fields added in recent migrations
    -- IF EXISTS (SELECT 1 FROM information_schema.columns 
    --            WHERE table_name = '\''your_table'\'' 
    --            AND column_name = '\''your_field'\'') THEN
    --     ALTER TABLE your_table ALTER COLUMN your_field DROP NOT NULL;
    --     RAISE NOTICE '\''Temporarily removed NOT NULL constraint from your_table.your_field'\'';
    -- END IF;
    
    RAISE NOTICE '\''Migration fixes completed'\'';
    
END $$;
EOF'
    
    # Run the migration fixes
    sudo docker exec -it $DB_CONTAINER psql -d $DB_NAME -U $DB_USER -f /var/lib/postgresql/data/migration_fixes.sql
    
    # Clean up
    sudo docker exec -i $DB_CONTAINER rm -f /var/lib/postgresql/data/migration_fixes.sql
    
    echo -e "${GREEN}✓ Migration fixes applied successfully${NC}"
}

# Function to restore migration constraints after successful restore
restore_migration_constraints() {
    echo -e "${YELLOW}Restoring migration constraints after data restore...${NC}"
    
    sudo docker exec -i $DB_CONTAINER bash -c 'cat > /var/lib/postgresql/data/restore_constraints.sql << '\''EOF'\''
-- Restore constraints and set default values after data restore

DO $$ 
BEGIN
    -- Example: Fix and restore constraints
    -- IF EXISTS (SELECT 1 FROM information_schema.columns 
    --            WHERE table_name = '\''your_table'\'' 
    --            AND column_name = '\''your_field'\'') THEN
    --     UPDATE your_table SET your_field = false WHERE your_field IS NULL;
    --     ALTER TABLE your_table ALTER COLUMN your_field SET NOT NULL;
    --     RAISE NOTICE '\''Fixed and restored NOT NULL constraint for your_table.your_field'\'';
    -- END IF;
    
    RAISE NOTICE '\''Constraint restoration completed'\'';
    
END $$;
EOF'
    
    # Run the constraint restoration
    sudo docker exec -it $DB_CONTAINER psql -d $DB_NAME -U $DB_USER -f /var/lib/postgresql/data/restore_constraints.sql
    
    # Clean up
    sudo docker exec -i $DB_CONTAINER rm -f /var/lib/postgresql/data/restore_constraints.sql
    
    echo -e "${GREEN}✓ Migration constraints restored successfully${NC}"
}

# Function to restore database with enhanced error handling
restore_database() {
    local backup_date=$1
    
    echo -e "${BLUE}Restoring database from backup: $backup_date${NC}"
    
    # Try full backup first, fall back to data-only
    if [ -f "./backups/${PROJECT_NAME}_backup_${backup_date}.sql" ]; then
        backup_file="${PROJECT_NAME}_backup_${backup_date}.sql"
        echo -e "${GREEN}Using full backup (schema + data)${NC}"
    elif [ -f "./backups/${PROJECT_NAME}_backup_${backup_date}_data.sql" ]; then
        backup_file="${PROJECT_NAME}_backup_${backup_date}_data.sql"
        echo -e "${YELLOW}Using data-only backup${NC}"
    else
        echo -e "${RED}✗ ERROR: No backup file found for date: ${backup_date}${NC}"
        echo -e "${RED}Looked for: ./backups/${PROJECT_NAME}_backup_${backup_date}.sql${NC}"
        echo -e "${RED}        and: ./backups/${PROJECT_NAME}_backup_${backup_date}_data.sql${NC}"
        return 1
    fi
    
    wait_for_database || return 1
    
    # Apply migration fixes if requested
    if [ "$MIGRATION_FIX" = true ]; then
        apply_migration_fixes
    fi
    
    # Copy backup to container
    sudo docker cp ./backups/${backup_file} $DB_CONTAINER:/var/lib/postgresql/data/
    
    # Run the actual restore
    echo -e "${YELLOW}Running database restore...${NC}"
    echo "=================================================================================="
    
    if sudo docker exec -i $DB_CONTAINER psql -d $DB_NAME -U $DB_USER -f /var/lib/postgresql/data/${backup_file}; then
        restore_status=0
        echo "=================================================================================="
        echo -e "${GREEN}✓ Database restore completed successfully${NC}"
    else
        restore_status=$?
        echo "=================================================================================="
        echo -e "${RED}✗ Database restore FAILED with exit code: $restore_status${NC}"
        echo -e "${RED}Check the error messages above for details${NC}"
        return $restore_status
    fi
    
    # Restore migration constraints if fixes were applied
    if [ "$MIGRATION_FIX" = true ]; then
        restore_migration_constraints
    fi
    
    # Clean up backup file from container
    sudo docker exec -i $DB_CONTAINER rm -f /var/lib/postgresql/data/${backup_file}
    
    echo -e "${GREEN}✓ Database restore completed${NC}"
}

# Function to stop containers
stop_containers() {
    local preserve_db=$1
    
    echo -e "${YELLOW}Stopping containers...${NC}"
    if [ "$preserve_db" = true ]; then
        # Soft rebuild - preserve database
        sudo docker stop $WEB_CONTAINER $NGINX_CONTAINER 2>/dev/null || true
        # Add other containers but not DB
        if [ -n "$CLOUDFLARED_CONTAINER" ]; then
            sudo docker stop $CLOUDFLARED_CONTAINER 2>/dev/null || true
        fi
    else
        # Full rebuild - stop all
        sudo docker stop $DB_CONTAINER $WEB_CONTAINER $NGINX_CONTAINER 2>/dev/null || true
        if [ -n "$CLOUDFLARED_CONTAINER" ]; then
            sudo docker stop $CLOUDFLARED_CONTAINER 2>/dev/null || true
        fi
    fi
}

# Function to remove containers
remove_containers() {
    local preserve_db=$1
    
    echo -e "${YELLOW}Removing containers...${NC}"
    if [ "$preserve_db" = true ]; then
        # Soft rebuild - preserve database
        sudo docker rm $WEB_CONTAINER $NGINX_CONTAINER 2>/dev/null || true
        if [ -n "$CLOUDFLARED_CONTAINER" ]; then
            sudo docker rm $CLOUDFLARED_CONTAINER 2>/dev/null || true
        fi
    else
        # Full rebuild - remove all
        sudo docker rm $DB_CONTAINER $WEB_CONTAINER $NGINX_CONTAINER 2>/dev/null || true
        if [ -n "$CLOUDFLARED_CONTAINER" ]; then
            sudo docker rm $CLOUDFLARED_CONTAINER 2>/dev/null || true
        fi
    fi
}

# Function to remove volumes
remove_volumes() {
    local preserve_db=$1
    
    echo -e "${YELLOW}Removing volumes...${NC}"
    # Always remove these to ensure fresh files
    sudo docker volume rm ${PROJECT_NAME}_static_volume 2>/dev/null || true
    sudo docker volume rm ${PROJECT_NAME}_media_volume 2>/dev/null || true
    sudo docker volume rm ${PROJECT_NAME}_log_volume 2>/dev/null || true
    
    if [ "$preserve_db" = false ]; then
        # Full rebuild - also remove database
        sudo docker volume rm ${PROJECT_NAME}_postgres_data 2>/dev/null || true
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            show_help
            exit 0
            ;;
        -d|--date)
            USER_DATE="$2"
            shift 2
            ;;
        -b|--backup)
            BACKUP_all=true
            shift
            ;;
        -l|--local)
            BACKUP_local=true
            shift
            ;;
        -r|--rebuild)
            REBUILD=true
            shift
            ;;
        -s|--soft)
            SOFT_REBUILD=true
            shift
            ;;
        -o|--restore)
            RESTORE=true
            shift
            ;;
        -m|--migrate)
            MIGRATE=true
            shift
            ;;
        -w|--download)
            DOWNLOAD=true
            shift
            ;;
        -f|--fixmigration)
            MIGRATION_FIX=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Check if date is provided when needed
if [[ ("$BACKUP_all" = true || "$BACKUP_local" = true || "$RESTORE" = true || "$DOWNLOAD" = true || "$REBUILD" = true) && -z "$USER_DATE" ]]; then
    echo -e "${RED}✗ Error: Date (-d or --date) is required for this operation${NC}"
    show_help
    exit 1
fi

# Set default date if needed
if [ -z "$USER_DATE" ]; then
    USER_DATE=$(date +%Y%m%d)
fi

# Display selected operations
echo -e "${BLUE}=== ${PROJECT_NAME} Build Script ===${NC}"
echo -e "${YELLOW}Running build with the following options:${NC}"
echo "Date: $USER_DATE"
echo "Backup: $BACKUP_all"
echo "Local Backup: $BACKUP_local"
echo "Rebuild: $REBUILD"
echo "Soft Rebuild: $SOFT_REBUILD"
echo "Restore: $RESTORE"
echo "Migrate: $MIGRATE"
echo "Download: $DOWNLOAD"
echo "Migration Fix: $MIGRATION_FIX"
echo "-----------------------------------"

# Execute operations

# Download backup
if [ "$DOWNLOAD" = true ]; then
    download_backup $USER_DATE
fi

# Backup operations
if [ "$BACKUP_all" = true ]; then
    backup_database $USER_DATE false
fi

if [ "$BACKUP_local" = true ]; then
    backup_database $USER_DATE true
fi

# Soft rebuild
if [ "$SOFT_REBUILD" = true ]; then
    echo -e "${BLUE}Starting soft rebuild...${NC}"
    
    # Git pull
    echo -e "${YELLOW}Pulling latest changes from git...${NC}"
    git pull
    
    # Stop and remove containers (preserve database)
    stop_containers true
    remove_containers true
    
    # Remove volumes (preserve database)
    remove_volumes true
    
    # Prune and rebuild
    echo -e "${YELLOW}Cleaning up unused Docker images...${NC}"
    sudo docker image prune -f
    echo -e "${GREEN}✓ Image cleanup completed${NC}"
    
    echo -e "${YELLOW}Rebuilding images with --no-cache (this may take several minutes)...${NC}"
    sudo docker compose build --no-cache
    echo -e "${GREEN}✓ Images rebuilt successfully${NC}"
    
    # Start containers
    echo -e "${YELLOW}Starting containers...${NC}"
    sudo docker compose up -d
    echo -e "${GREEN}✓ Containers started${NC}"
    
    # Wait and run migrations
    wait_for_database
    run_migrations
    
    echo -e "${GREEN}🎉 Soft rebuild completed!${NC}"
fi

# Full rebuild
if [ "$REBUILD" = true ]; then
    echo -e "${BLUE}Starting full rebuild...${NC}"
    
    # Git pull
    echo -e "${YELLOW}Pulling latest changes from git...${NC}"
    git pull
    
    # Stop and remove everything
    stop_containers false
    remove_containers false
    remove_volumes false
    
    # Prune and rebuild
    echo -e "${YELLOW}Cleaning up unused Docker images...${NC}"
    sudo docker image prune -f
    echo -e "${GREEN}✓ Image cleanup completed${NC}"
    
    echo -e "${YELLOW}Rebuilding images with --no-cache (this may take several minutes)...${NC}"
    sudo docker compose build --no-cache
    echo -e "${GREEN}✓ Images rebuilt successfully${NC}"
    
    # Start containers
    echo -e "${YELLOW}Starting containers...${NC}"
    sudo docker compose up -d
    echo -e "${GREEN}✓ Containers started${NC}"
    
    # Wait for database
    wait_for_database
    
    # Check if we have a full backup - if so, restore first then migrate
    if [ -f "./backups/${PROJECT_NAME}_backup_${USER_DATE}.sql" ]; then
        echo -e "${GREEN}Full backup found - restoring database first, then running migrations${NC}"
        if restore_database $USER_DATE; then
            run_migrations
            echo -e "${GREEN}🎉 Full rebuild completed successfully!${NC}"
        else
            echo -e "${RED}✗ Full rebuild FAILED - database restore failed${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}No full backup found - running migrations first, then restoring data${NC}"
        run_migrations
        if restore_database $USER_DATE; then
            echo -e "${GREEN}🎉 Full rebuild completed successfully!${NC}"
        else
            echo -e "${RED}✗ Full rebuild FAILED - database restore failed${NC}"
            exit 1
        fi
    fi
fi

# Standalone restore
if [ "$RESTORE" = true ] && [ "$REBUILD" = false ]; then
    if restore_database $USER_DATE; then
        echo -e "${GREEN}🎉 Standalone restore completed successfully!${NC}"
    else
        echo -e "${RED}✗ Standalone restore FAILED${NC}"
        exit 1
    fi
fi

# Standalone migrate
if [ "$MIGRATE" = true ] && [ "$REBUILD" = false ] && [ "$SOFT_REBUILD" = false ]; then
    run_migrations
fi

echo -e "${GREEN}🎉 Build script completed successfully!${NC}"