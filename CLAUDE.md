# CLAUDE.md - Project Memory & Context

**INSTRUCTIONS**: This is your project's living memory. Update this document as your project evolves. It serves as context for AI assistants and documentation for developers.

## Project Overview

**Project Name**: calendar-builder  
**Description**: This is an app that will build the date part of the calendar and allows you to put a picture on each day of the calendar. It will also allow you to combine this pdf with the top part of the calendar.  
**Industry/Domain**: Technology/SaaS  
**Target Users**: customers  
**Current Status**: Development  

### Quick Summary
This is an app that will build the date part of the calendar and allows you to put a picture on each day of the calendar. It will also allow you to combine this pdf with the top part of the calendar.. Built for customers in the Technology/SaaS industry.

## Key Architecture

### Backend Stack
- **Framework**: Django 5.0+ with Python 3.11+
- **Database**: PostgreSQL 15+
- **Cache**: Redis (optional)
- **Task Queue**: Celery (if needed)
- **Authentication**: Django built-in (customize as needed)

### Frontend Approach  
- **Styling**: Custom CSS component system (NO Bootstrap/Tailwind)
- **JavaScript**: Vanilla JS or minimal framework
- **Design**: Mobile-first responsive design
- **Theme**: [Generated from style guide questionnaire]

### Infrastructure
- **Development**: pyenv + local Django server
- **Production**: Docker Compose with Nginx
- **Database**: PostgreSQL in production
- **Deployment**: Automated via build.sh script

## Current Major Components

### Apps Structure
```
apps/
├── core/           # [Description of core functionality]
├── [app_name]/     # [Description of this app]
├── [app_name]/     # [Description of this app]  
└── [app_name]/     # [Description of this app]
```

### Key Models
- **[ModelName]**: [Brief description and purpose]
- **[ModelName]**: [Brief description and purpose]
- **[ModelName]**: [Brief description and purpose]

### Important URLs
- **Admin**: `/admin/` - Django admin interface
- **API**: `/api/` - API endpoints (if applicable)
- **[Feature]**: `/[url]/` - [Description]

## Current Major Projects & Status

### 🚧 Active Development
**[Current Feature/Project Name]** - Status: [In Progress/Planning/Review]  
**Priority**: [High/Medium/Low]  
**Description**: [What you're currently working on]
**Key Files**: [List main files being modified]
**Next Steps**: [What needs to be done next]

### 📋 Planned Features
**[Planned Feature 1]** - [Brief description and timeline]  
**[Planned Feature 2]** - [Brief description and timeline]  
**[Planned Feature 3]** - [Brief description and timeline]

### ✅ Recently Completed  
**[Recent Feature]** - [Date completed] - [Brief description]
**[Recent Feature]** - [Date completed] - [Brief description]

## Database Schema Context

### Core Models
```python
# Key model relationships and constraints
[ModelName]:
  - Field descriptions
  - Important relationships  
  - Business rules/constraints
  - Indexes and performance considerations
```

### Important Relationships
- [Model A] → [Model B]: [Description of relationship]
- [Model C] ← [Model D]: [Description of relationship]

## Custom CSS System

### Theme Configuration
Based on questionnaire answers in `docs/STYLE_GUIDE.md`:

- **Primary Color**: #2563eb - [Usage description]
- **Secondary Color**: #2563eb - [Usage description]  
- **Accent Color**: #2563eb - [Usage description]
- **Design Style**: Creative
- **Border Radius**: 16px

### Component Architecture
```
static/css/
├── base.css              # CSS variables, typography, utilities
├── components/           # Reusable components
│   ├── buttons.css      # Button variants and states
│   ├── forms.css        # Form controls and layouts
│   ├── cards.css        # Card components
│   ├── modals.css       # Modal dialogs
│   └── tables.css       # Data table styles
└── apps/                # App-specific styles
    ├── [app_name].css   # App-specific styling
    └── [app_name].css   # App-specific styling
```

### Key CSS Patterns
- **Mobile-First**: All components start with mobile styles
- **CSS Variables**: Consistent theming with `var(--color-primary)`
- **BEM Methodology**: `.component__element--modifier` naming
- **Responsive**: Breakpoints at 576px, 768px, 992px, 1200px

## Development Workflow

### Daily Development
```bash
# Start development session
pyenv activate calendar-builder
python manage.py runserver

# Common tasks
python manage.py makemigrations
python manage.py migrate
python manage.py shell
python manage.py test
```

### Production Deployment
```bash
# Full rebuild with backup
./build.sh -r -d $(date +%Y%m%d)

# Soft rebuild (preserve database)  
./build.sh -s

# Backup only
./build.sh -b -d $(date +%Y%m%d)
```

### Code Quality
```bash
# Format and lint
black .
isort .
flake8

# Type checking
mypy apps/

# Test with coverage
pytest --cov=apps
```

## Domain-Specific Context

### [CUSTOMIZE THIS SECTION FOR YOUR DOMAIN]

#### For Aviation Projects:
- **Regulatory Context**: FAR compliance requirements
- **Data Validation**: Flight time limits, currency requirements
- **Safety Considerations**: Audit trails, data integrity
- **Key Calculations**: Flight time, currency, duty limits

#### For Healthcare Projects:
- **Compliance**: HIPAA requirements
- **Data Security**: Patient data protection
- **Audit Requirements**: Complete audit trails
- **Key Features**: Patient records, appointments, billing

#### For E-commerce Projects:
- **Payment Processing**: Stripe/PayPal integration
- **Inventory Management**: Stock tracking
- **Order Fulfillment**: Shipping integration
- **Customer Experience**: Reviews, recommendations

#### For Financial Projects:
- **Compliance**: SOX, financial regulations
- **Security**: Encryption, secure transactions
- **Reporting**: Financial statements, analytics
- **Integration**: Banking APIs, payment processors

## Technical Decisions & Rationale

### Architecture Decisions
**Decision**: [e.g., "Custom CSS instead of Bootstrap"]  
**Rationale**: [Why this decision was made]  
**Trade-offs**: [What was gained/lost]  
**Date**: [When decided]

**Decision**: [e.g., "pyenv for development, Docker for production"]  
**Rationale**: [Why this decision was made]  
**Trade-offs**: [What was gained/lost]  
**Date**: [When decided]

### Technology Choices
**Database**: PostgreSQL - [Why PostgreSQL over alternatives]
**Cache**: [Redis/None] - [Caching strategy and reasoning]
**Frontend**: Custom CSS - [Why no frameworks]
**Testing**: pytest + Django Test - [Testing approach]

## Performance Considerations

### Database Optimization
- **Indexes**: [List important indexes and why]
- **Query Optimization**: [Key querysets with select_related/prefetch_related]
- **Caching Strategy**: [What's cached and for how long]

### Frontend Performance
- **CSS**: [Minification, critical path CSS]
- **JavaScript**: [Bundling, async loading strategies]
- **Images**: [Optimization, responsive images]
- **Mobile**: [Specific mobile performance considerations]

## Security Implementation

### Authentication & Authorization
- **User Model**: [Custom user model or Django default]
- **Permissions**: [Permission system approach]
- **Sessions**: [Session configuration]

### Data Protection
- **Input Validation**: [Validation approach and tools]
- **SQL Injection**: [Prevention methods]
- **XSS Protection**: [Template escaping, CSP headers]
- **CSRF**: [CSRF token implementation]

### [Domain-Specific Security]
- **[Industry requirement]**: [How it's implemented]
- **[Compliance standard]**: [How it's met]

## Integration Points

### External Services
**Service**: [e.g., Email provider] - [How it's used]  
**Service**: [e.g., Payment processor] - [How it's used]  
**Service**: [e.g., Maps API] - [How it's used]

### APIs
**Internal API**: [Description of your API endpoints]  
**External APIs**: [Third-party APIs you consume]

## Deployment & Infrastructure

### Environment Configuration
```bash
# Required environment variables
SECRET_KEY=your-secret-key
DEBUG=False
DB_NAME=project_db
DB_USER=project_user
DB_PASSWORD=secure-password
# [Add other required vars]
```

### Production Setup
- **Server**: [Hosting provider/setup]
- **Database**: [PostgreSQL configuration]
- **Static Files**: [WhiteNoise/CDN setup]
- **SSL**: [Certificate setup]
- **Monitoring**: [Error tracking, performance monitoring]

### Backup Strategy
- **Database**: Automated daily backups via build.sh
- **Media Files**: [Backup strategy for user uploads]
- **Code**: Git repository + [additional backup if any]

## Testing Strategy

### Test Coverage
- **Models**: [Coverage level and key test cases]
- **Views**: [Coverage level and key test cases]  
- **Forms**: [Coverage level and key test cases]
- **Integration**: [Key user workflows tested]

### Test Data
- **Factories**: [Factory classes for test data]
- **Fixtures**: [Static test data files]
- **Test Database**: [Test database configuration]

## Common Issues & Solutions

### Development Issues
**Issue**: [Common problem]  
**Solution**: [How to fix it]  
**Prevention**: [How to avoid it]

**Issue**: [Common problem]  
**Solution**: [How to fix it]  
**Prevention**: [How to avoid it]

### Production Issues  
**Issue**: [Common problem]  
**Solution**: [How to fix it]  
**Monitoring**: [How to detect it early]

## Quick Reference Commands

### Development
```bash
# Create new app
python manage.py startapp [app_name]

# Database operations
python manage.py makemigrations [app_name]
python manage.py migrate
python manage.py dbshell

# User management
python manage.py createsuperuser
python manage.py changepassword [username]

# Development server
python manage.py runserver
python manage.py runserver 0.0.0.0:8000  # For external access
```

### Production
```bash
# Deploy with backup/restore
./build.sh -r -d YYYYMMDD

# Backup database
./build.sh -b -d $(date +%Y%m%d)

# Soft rebuild (preserve data)
./build.sh -s

# View logs
docker compose logs -f web
docker compose logs -f db
```

### Debugging
```bash
# Django shell with extensions
python manage.py shell_plus

# Database queries debug
python manage.py shell_plus --print-sql

# Show URLs
python manage.py show_urls
```

## File Structure Reference

### Key Files & Directories
```
project_name/
├── CLAUDE.md                    # This file - project memory
├── build.sh                     # Production deployment script
├── manage.py                    # Django management
├── requirements/                # Python dependencies
│   ├── base.txt                # Core requirements
│   ├── development.txt         # Dev-only requirements
│   └── production.txt          # Production requirements
├── config/                     # Django project configuration
│   ├── settings/               # Environment-specific settings
│   ├── urls.py                 # Main URL configuration
│   └── wsgi.py                 # WSGI configuration
├── apps/                       # Django applications
├── static/                     # Static files (CSS, JS, images)
├── templates/                  # Django templates
├── media/                      # User uploads
├── docs/                       # Documentation
│   ├── STYLE_GUIDE.md         # Project style guide
│   └── CODING_GUIDE.md        # Development standards
├── tests/                      # Test suite
├── scripts/                    # Utility scripts
├── docker-compose.yml          # Production containers
├── Dockerfile                  # Production image
├── .env.example               # Environment variables template
└── .gitignore                 # Git ignore rules
```

## Project History & Evolution

### Version History
**v1.0** - 2025-09-18 - [Initial release with core features]  
**v1.1** - 2025-09-18 - [Major feature additions]  
**v1.2** - 2025-09-18 - [Performance improvements, bug fixes]

### Major Milestones
- **2025-09-18**: Project started
- **2025-09-18**: [Significant milestone]
- **2025-09-18**: [Production deployment]
- **2025-09-18**: [Major feature launch]

## Team & Contacts

### Key People
**Developer**: [Name/Contact]  
**Designer**: [Name/Contact] (if applicable)  
**Product Owner**: [Name/Contact] (if applicable)

### External Contacts
**Hosting Provider**: [Contact info]  
**Domain Registrar**: [Contact info]  
**Third-party Services**: [List with contacts]

---

## Maintenance Notes

### Regular Tasks
- **Weekly**: Review error logs, check performance metrics
- **Monthly**: Update dependencies, security patches
- **Quarterly**: Full backup verification, security audit

### Update Log
**2025-09-18**: [What was updated/changed]  
**2025-09-18**: [What was updated/changed]  
**2025-09-18**: [What was updated/changed]

---

*Last Updated: 2025-09-18*  
*Next Major Review: 2025-09-18*  
*Current Focus: [What you're working on]*

## Context for AI Assistants

When working with this project, remember:

1. **Custom CSS System**: Never suggest Bootstrap/Tailwind - we have a complete custom system
2. **Mobile-First**: All UI decisions should start with mobile
3. **pyenv Development**: Local development uses pyenv, not Docker
4. **build.sh Deployment**: Production uses the build.sh script for all operations
5. **Domain Context**: [Add specific domain knowledge that AI should remember]
6. **Architecture Patterns**: [Key patterns to follow]
7. **Performance Requirements**: [Specific performance constraints]
8. **Security Requirements**: [Specific security considerations]

### Current Work Context
**Active Feature**: [What's currently being developed]  
**Blockers**: [Any current blockers or challenges]  
**Recent Changes**: [What was recently modified]  
**Next Priorities**: [What's coming up next]