# Django Project Starter Guide

A complete guide for creating new Django projects using proven patterns from Keep-Logging. This guide creates production-ready projects with custom CSS systems, mobile-first design, and comprehensive deployment automation.

## Quick Start

### 1. Copy Template Files
```bash
# Create new project directory
mkdir my-new-project
cd my-new-project

# Copy these 5 template files:
cp ~/templates/DJANGO_PROJECT_STARTER_GUIDE.md .
cp ~/templates/build_template.sh ./build.sh
cp ~/templates/STYLE_GUIDE_TEMPLATE.md ./docs/STYLE_GUIDE.md
cp ~/templates/CODING_GUIDE_TEMPLATE.md ./docs/CODING_GUIDE.md  
cp ~/templates/CLAUDE_TEMPLATE.md ./CLAUDE.md
```

### 2. Customize Project Settings
```bash
# Edit build.sh - change these lines:
PROJECT_NAME="my-new-project"
DB_NAME="${PROJECT_NAME}_db"
DB_USER="${PROJECT_NAME}_user"

# Edit CLAUDE.md with your project details
# Run style guide questionnaire (see Style Guide section)
```

### 3. Create Django Project
```bash
# Set up Python environment
pyenv virtualenv 3.11.8 my-new-project
pyenv activate my-new-project

# Install Django and dependencies
pip install django psycopg2-binary python-decouple

# Create Django project
django-admin startproject config .
python manage.py startapp core

# Initial setup
python manage.py migrate
python manage.py createsuperuser
```

### 4. Development Workflow
```bash
# Daily development (local with pyenv)
pyenv activate my-new-project
python manage.py runserver

# Production deployment (Docker via build.sh)
./build.sh -r -d $(date +%Y%m%d)
```

## Project Philosophy

### Core Principles
1. **Mobile-First Design**: Every interface starts mobile and scales up
2. **Custom CSS System**: No Bootstrap/Tailwind - complete brand control
3. **pyenv Development**: Local development with hot reload
4. **Docker Production**: Containerized deployment with build.sh automation
5. **Living Documentation**: CLAUDE.md tracks project evolution

### Architecture Pattern
```
project_name/
├── CLAUDE.md                  # Project memory and context
├── build.sh                   # Production deployment automation
├── docker-compose.yml         # Production containers
├── Dockerfile                 # Production image
├── docker-entrypoint.sh       # Container initialization
│
├── config/                    # Django project settings
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py           # Shared settings
│   │   ├── development.py    # pyenv + SQLite/PostgreSQL
│   │   └── production.py     # Docker + PostgreSQL
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── apps/                      # Django applications
│   ├── core/                 # Base functionality
│   │   ├── models.py         # Abstract base models
│   │   ├── views.py          # Base views and mixins
│   │   ├── utils.py          # Shared utilities
│   │   ├── validators.py     # Custom validators
│   │   └── templates/core/
│   │       ├── base.html     # Main base template
│   │       └── includes/     # Reusable includes
│   │
│   └── [domain_apps]/        # Feature-specific apps
│
├── static/                   # Static files (custom CSS system)
│   ├── css/
│   │   ├── base.css         # CSS variables + core styles
│   │   ├── components/      # Reusable component styles
│   │   │   ├── buttons.css
│   │   │   ├── forms.css
│   │   │   ├── cards.css
│   │   │   └── modals.css
│   │   └── apps/           # App-specific styles
│   ├── js/
│   │   ├── base.js         # Core JavaScript
│   │   └── components/     # Component JavaScript
│   └── img/
│
├── templates/               # Global templates
├── media/                  # User uploads
├── docs/                   # Documentation
│   ├── STYLE_GUIDE.md     # Project-specific style guide
│   ├── CODING_GUIDE.md    # Development standards
│   └── API.md             # API documentation
│
├── scripts/               # Utility scripts
├── tests/                 # Test suite
└── requirements/          # Dependencies
    ├── base.txt
    ├── development.txt
    └── production.txt
```

## Development Environment Setup

### Python Environment (pyenv)
```bash
# Install specific Python version
pyenv install 3.11.8

# Create project virtual environment
pyenv virtualenv 3.11.8 project-name
pyenv activate project-name

# Create .python-version file for auto-activation
echo "project-name" > .python-version
```

### Requirements Structure
Create `requirements/base.txt`:
```
Django>=5.0,<5.1
psycopg2-binary>=2.9.5
python-decouple>=3.8
Pillow>=10.0.0
django-extensions>=3.2.0
```

Create `requirements/development.txt`:
```
-r base.txt
django-debug-toolbar>=4.2.0
black>=23.0.0
isort>=5.12.0
flake8>=6.0.0
pytest>=7.4.0
pytest-django>=4.7.0
```

Create `requirements/production.txt`:
```
-r base.txt
gunicorn>=21.2.0
whitenoise>=6.6.0
sentry-sdk>=1.32.0
```

### Django Settings Structure

Create `config/settings/base.py`:
```python
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Security
SECRET_KEY = config('SECRET_KEY', default='change-me-in-production')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=lambda v: [s.strip() for s in v.split(',')])

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'django_extensions',
]

LOCAL_APPS = [
    'apps.core',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
```

Create `config/settings/development.py`:
```python
from .base import *

# Development settings
DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# Database - SQLite for simple development, PostgreSQL if needed
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Optional: Use PostgreSQL in development too
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': config('DB_NAME', default='project_dev'),
#         'USER': config('DB_USER', default='postgres'),
#         'PASSWORD': config('DB_PASSWORD', default='postgres'),
#         'HOST': config('DB_HOST', default='localhost'),
#         'PORT': config('DB_PORT', default='5432'),
#     }
# }

# Add debug toolbar if available
try:
    import debug_toolbar
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
    INTERNAL_IPS = ['127.0.0.1']
except ImportError:
    pass
```

Create `config/settings/production.py`:
```python
from .base import *

# Production settings
DEBUG = False
ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=lambda v: [s.strip() for s in v.split(',')])

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='db'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

# Static files with WhiteNoise
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Security settings
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True

# Optional: HTTPS settings for production
# SECURE_SSL_REDIRECT = True
# SECURE_HSTS_SECONDS = 31536000
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_HSTS_PRELOAD = True

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/app/logs/django.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

## Style Guide Integration

### Theme Generation Process
1. **Answer questionnaire** in `docs/STYLE_GUIDE.md`
2. **Run theme generator**: `python scripts/generate_theme.py`
3. **CSS variables generated** in `static/css/base.css`
4. **Components automatically themed**

### Custom CSS Architecture
Following Keep-Logging's proven pattern:

```css
/* static/css/base.css - Generated from your theme choices */
:root {
    /* Brand Colors - FROM QUESTIONNAIRE */
    --primary-color: #your-choice;
    --secondary-color: #your-choice;
    --accent-color: #your-choice;
    
    /* Semantic Colors */
    --bg-primary: var(--white);
    --bg-secondary: var(--gray-100);
    --text-primary: var(--gray-900);
    --text-secondary: var(--gray-600);
    
    /* Spacing System */
    --spacing-xs: 0.25rem;
    --spacing-sm: 0.5rem;
    --spacing-md: 1rem;
    --spacing-lg: 1.5rem;
    --spacing-xl: 2rem;
    
    /* Mobile-first breakpoints */
    --breakpoint-sm: 576px;
    --breakpoint-md: 768px;
    --breakpoint-lg: 992px;
    --breakpoint-xl: 1200px;
}

/* Dark mode support */
[data-theme="dark"] {
    --bg-primary: #1a1a1a;
    --bg-secondary: #2d2d2d;
    --text-primary: #f0f0f0;
    --text-secondary: #b0b0b0;
}

/* Mobile-first base styles */
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    line-height: 1.6;
    color: var(--text-primary);
    background-color: var(--bg-primary);
    margin: 0;
    padding: 0;
}

/* Responsive container */
.container {
    width: 100%;
    padding: 0 var(--spacing-md);
    margin: 0 auto;
}

@media (min-width: 576px) { .container { max-width: 540px; } }
@media (min-width: 768px) { .container { max-width: 720px; } }
@media (min-width: 992px) { .container { max-width: 960px; } }
@media (min-width: 1200px) { .container { max-width: 1140px; } }
```

## Docker Production Setup

### docker-compose.yml
```yaml
version: '3.8'

services:
  db:
    image: postgres:15
    restart: always
    volumes:
      - postgres_data:/var/lib/postgresql/data/
    env_file:
      - ./.env
    ports:
      - "5433:5432"
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -d ${DB_NAME} -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  web:
    build: ./
    restart: always
    volumes:
      - static_volume:/app/staticfiles
      - media_volume:/app/media
      - log_volume:/app/logs
    depends_on:
      - db
    env_file:
      - ./.env
    environment:
      - DJANGO_SETTINGS_MODULE=config.settings.production

  nginx:
    build: ./nginx
    restart: always
    volumes:
      - static_volume:/app/staticfiles
      - media_volume:/app/media  
    depends_on:
      - web
    # Add ports or Cloudflare tunnel config as needed

volumes:
  postgres_data:
  static_volume:
  media_volume:
  log_volume:
```

### Environment Files
Create `.env.example`:
```bash
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com

# Database
DB_NAME=project_db
DB_USER=project_user
DB_PASSWORD=secure-password-here
DB_HOST=db
DB_PORT=5432

# Optional: Email, Sentry, etc.
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
SENTRY_DSN=your-sentry-dsn
```

## Testing Setup

### Basic Test Structure
```python
# tests/test_models.py
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()

class ModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_user_creation(self):
        self.assertEqual(self.user.username, 'testuser')
        self.assertTrue(self.user.check_password('testpass123'))
```

### Run Tests
```bash
# Development
python manage.py test

# With coverage (install coverage first)
coverage run --source='.' manage.py test
coverage report
coverage html
```

## Common Commands

### Development
```bash
# Daily workflow
pyenv activate project-name
python manage.py runserver

# Database operations
python manage.py makemigrations
python manage.py migrate
python manage.py shell_plus

# Testing
python manage.py test
black .
isort .
flake8
```

### Production (via build.sh)
```bash
# Full deployment with backup
./build.sh -r -d $(date +%Y%m%d)

# Soft rebuild (preserve database)
./build.sh -s

# Backup only
./build.sh -b -d $(date +%Y%m%d)

# Restore from backup
./build.sh -o -d 20241201
```

## Next Steps After Setup

1. **Customize CLAUDE.md** with your project details
2. **Complete style guide questionnaire** and generate theme
3. **Create your first app**: `python manage.py startapp your_app`
4. **Add to INSTALLED_APPS** in settings
5. **Create models, views, templates** following the coding guide
6. **Write tests** for everything
7. **Document major decisions** in CLAUDE.md

## Troubleshooting

### Common Issues
- **pyenv not activating**: Check `.python-version` file exists
- **Static files not loading**: Run `python manage.py collectstatic`
- **Database errors**: Check `.env` file and database settings
- **Build script failing**: Verify Docker is running and `.env` is configured

### Getting Help
- Check `CLAUDE.md` for project-specific context
- Review `docs/CODING_GUIDE.md` for standards
- Look at Keep-Logging as reference implementation
- Use `python manage.py shell_plus` for debugging

---

This starter guide creates production-ready Django projects with proven patterns. Each project gets custom theming, comprehensive deployment automation, and maintainable architecture from day one.