# CALENDAR-BUILDER - Project Setup Summary

**Generated on**: 2025-09-18 09:46:30

## 🎯 Project Overview

**Name**: calendar-builder  
**Description**: This is an app that will build the date part of the calendar and allows you to put a picture on each day of the calendar. It will also allow you to combine this pdf with the top part of the calendar.  
**Domain**: Technology/SaaS  
**Target Users**: customers  
**Python Version**: 3.13.1

## 🎨 Design & Theme

**Primary Color**: #2563eb  
**Secondary Color**: #64748b  
**Accent Color**: #0ea5e9  
**Design Style**: Creative  
**Border Radius**: 16px  
**Shadow Style**: Medium  
**Dark Mode**: Disabled  
**Mobile Navigation**: Hamburger

## ⚙️ Technical Configuration

**Development Database**: POSTGRESQL  
**Features Enabled**:
- ✅ Celery (Background Tasks)
- ❌ Redis
- ❌ REST API
- ❌ Sentry Error Tracking

**Remote Backup**: Not configured



## 🏗️ Architecture Details

**Development Workflow**:
- Local development with pyenv (no Docker)
- Hot reload with `python manage.py runserver`
- POSTGRESQL database for development

**Production Stack**:
- Docker Compose orchestration
- PostgreSQL database
- Nginx web server with security headers
- Gunicorn WSGI server
- Automated build/deploy via build.sh

**CSS Architecture**:
- Custom component system (NO Bootstrap/Tailwind)
- Mobile-first responsive design
- CSS variables for consistent theming
- Component-based organization in static/css/components/

## 📁 Generated Project Structure

```
calendar-builder/
├── CLAUDE.md                    # Project memory (IMPORTANT for AI context)
├── build.sh                     # Production deployment automation
├── Makefile                     # Development commands (make help)
├── .python-version              # Auto pyenv activation
├── .pre-commit-config.yaml      # Code quality automation
├── README.md                    # Project overview
│
├── apps/                        # Django applications
│   └── core/                   # Base functionality
├── config/                      # Django settings
│   └── settings/               # Environment-specific settings
├── static/css/                  # Custom CSS framework
│   ├── base.css                # Generated theme with your colors
│   └── components/             # Reusable components (buttons, forms, etc.)
├── templates/                   # Django templates
├── docs/                       # Comprehensive documentation
│   ├── SETUP_GUIDE.md         # Complete setup instructions
│   ├── STYLE_GUIDE.md         # Custom styling guidelines
│   └── CODING_GUIDE.md        # Development standards
│
├── requirements/               # Python dependencies
├── nginx/                      # Production nginx config
├── docker-compose.yml          # Production containers
└── Dockerfile                  # Production image
```

## 🚀 Key Commands Reference

**Development**:
```bash
make run          # Start development server
make test         # Run tests
make shell        # Django shell
make migrate      # Database migrations
make format       # Auto-format code
make lint         # Check code quality
```

**Production**:
```bash
make deploy       # Deploy with backup
make backup       # Backup database
./build.sh -r -d $(date +%Y%m%d)  # Full rebuild
```

## 🎯 Domain-Specific Context

**Industry**: Technology/SaaS  
**Compliance Requirements**: none  
**Special Features**: Will need to import and store photos. and then be able to minipulate PDFs.

## 📋 Next Development Tasks

1. **Django Setup**:
   - Move settings.py to config/settings/ structure
   - Create base, development, and production settings
   - Add 'apps.core' to INSTALLED_APPS

2. **Model Development**:
   - Define domain models in apps/core/models.py
   - Create migrations and migrate
   - Set up admin interface

3. **Frontend**:
   - Custom CSS components are ready in static/css/
   - Mobile-first templates in templates/
   - No Bootstrap/Tailwind - use custom system

4. **Quality Setup**:
   - Pre-commit hooks configured
   - Code formatting with black/isort
   - Linting with flake8

## 🤖 AI Assistant Instructions

When helping with this project:

1. **NEVER suggest Bootstrap/Tailwind** - We have a complete custom CSS system
2. **Always think mobile-first** - Every component starts with mobile design
3. **Use the custom CSS variables** - Primary: #2563eb, etc.
4. **Follow the build.sh pattern** - Production deployment via Docker
5. **Reference CLAUDE.md** - Contains living project context
6. **Domain focus**: This is a Technology/SaaS application for customers

## 🔧 Quick Context for Development

**Current Status**: Fresh project setup completed  
**Ready for**: Django project creation and initial model development  
**Architecture**: Same proven patterns as Keep-Logging project  
**Styling**: Custom creative theme with #2563eb primary color  
**Deployment**: Docker production, pyenv development

---

*This summary provides complete context for AI assistants and developers joining the project.*
