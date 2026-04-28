#!/bin/bash

# ============================================================================
# Build Script for Calendar Builder
# Uses Remote PostgreSQL + Cloudflare R2 CDN
# ============================================================================
#
# Usage:
#   ./build.sh              # Standard deployment
#   ./build.sh --rebuild    # Full rebuild (stop, remove, rebuild images)
#   ./build.sh --collectstatic  # Just collect static files to R2
#
# ============================================================================

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_NAME="calendar"
REBUILD=false
COLLECTSTATIC_ONLY=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -r|--rebuild)
            REBUILD=true
            shift
            ;;
        -c|--collectstatic)
            COLLECTSTATIC_ONLY=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  -r, --rebuild        Full rebuild (stop, remove, rebuild images)"
            echo "  -c, --collectstatic  Just collect static files to R2"
            echo "  -h, --help           Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Calendar Builder - Stateless Deployment (R2 + Remote DB) ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Load environment
if [ -f ./.env ]; then
    set -a
    source ./.env
    set +a
    echo -e "${GREEN}✓ Loaded .env${NC}"
else
    echo -e "${RED}✗ ERROR: .env not found!${NC}"
    exit 1
fi

# Test remote database connection
echo ""
echo -e "${YELLOW}Testing remote database connection...${NC}"
if psql "$DATABASE_URL" -c "SELECT 1" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Remote database connected${NC}"
else
    echo -e "${RED}✗ ERROR: Cannot connect to remote database!${NC}"
    echo -e "${RED}  DATABASE_URL: $DATABASE_URL${NC}"
    exit 1
fi

# Test R2 credentials
echo ""
echo -e "${YELLOW}Checking R2 configuration...${NC}"
if [ -z "$R2_ACCESS_KEY_ID" ] || [ -z "$R2_BUCKET_NAME" ]; then
    echo -e "${RED}✗ ERROR: R2 credentials not configured!${NC}"
    echo -e "${RED}  Make sure R2_* variables are set in .env${NC}"
    exit 1
fi
echo -e "${GREEN}✓ R2 bucket: $R2_BUCKET_NAME${NC}"
echo -e "${GREEN}✓ CDN domain: $R2_PUBLIC_DOMAIN${NC}"

# Collectstatic only
if [ "$COLLECTSTATIC_ONLY" = true ]; then
    echo ""
    echo -e "${BLUE}Collecting static files to R2...${NC}"
    docker compose run --rm web python manage.py collectstatic --noinput
    echo -e "${GREEN}✓ Static files uploaded to R2${NC}"
    exit 0
fi

# Pull latest code
echo ""
echo -e "${YELLOW}Pulling latest code from git...${NC}"
git pull origin main || git pull origin master || echo -e "${YELLOW}⚠ Git pull failed (maybe not a git repo?)${NC}"

# Full rebuild
if [ "$REBUILD" = true ]; then
    echo ""
    echo -e "${BLUE}═══ FULL REBUILD MODE ═══${NC}"
    echo -e "${YELLOW}Stopping containers...${NC}"
    docker compose down

    echo -e "${YELLOW}Removing old images...${NC}"
    docker image prune -f

    echo -e "${YELLOW}Building images (no cache)...${NC}"
    DOCKER_BUILDKIT=1 BUILDKIT_PROVENANCE_MODE=disabled docker compose build --no-cache
else
    echo ""
    echo -e "${BLUE}═══ STANDARD DEPLOYMENT ═══${NC}"
    echo -e "${YELLOW}Building images...${NC}"
    docker compose build
fi

# Start services
echo ""
echo -e "${YELLOW}Starting services...${NC}"
docker compose up -d
echo -e "${GREEN}✓ Services started${NC}"

# Wait for web to be healthy
echo ""
echo -e "${YELLOW}Waiting for web service to be healthy...${NC}"
MAX_ATTEMPTS=30
attempt=1
while [ $attempt -le $MAX_ATTEMPTS ]; do
    if docker compose ps web | grep -q "healthy"; then
        echo -e "${GREEN}✓ Web service is healthy!${NC}"
        break
    fi
    echo -e "${YELLOW}Waiting... (attempt $attempt/$MAX_ATTEMPTS)${NC}"
    sleep 2
    ((attempt++))
done

if [ $attempt -gt $MAX_ATTEMPTS ]; then
    echo -e "${RED}✗ WARNING: Web service did not become healthy${NC}"
    echo -e "${YELLOW}Check logs: docker compose logs web${NC}"
fi

# Run migrations on remote database
echo ""
echo -e "${YELLOW}Running database migrations on remote DB...${NC}"
docker compose exec web python manage.py migrate --noinput
echo -e "${GREEN}✓ Migrations completed${NC}"

# Collect static files to R2
echo ""
echo -e "${YELLOW}Collecting static files to R2...${NC}"
docker compose exec web python manage.py collectstatic --noinput
echo -e "${GREEN}✓ Static files uploaded to R2${NC}"

# Show status
echo ""
echo -e "${BLUE}═══ DEPLOYMENT STATUS ═══${NC}"
docker compose ps

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                 DEPLOYMENT COMPLETE!                      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Your application is now running with:${NC}"
echo -e "${GREEN}  • Remote PostgreSQL database at 172.16.29.5${NC}"
echo -e "${GREEN}  • Static/Media files on Cloudflare R2 CDN${NC}"
echo -e "${GREEN}  • Stateless containers (no volumes to manage)${NC}"
echo ""
echo -e "${YELLOW}Useful commands:${NC}"
echo "  docker compose logs -f web    # View logs"
echo "  docker compose ps             # Check status"
echo "  docker compose restart web    # Restart web"
echo ""
