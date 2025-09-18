# Coding Standards Template - Django Project

**INSTRUCTIONS**: This template provides comprehensive coding standards for your Django project. Customize the domain-specific sections for your industry/use case.

## 🎯 Core Principles

1. **Code Quality First**: Clean, readable, maintainable code
2. **Type Safety**: Use type hints throughout
3. **Test Everything**: Comprehensive test coverage
4. **Document Decisions**: Clear docstrings and comments
5. **Performance Matters**: Optimize database queries and response times
6. **Mobile-First**: Every feature works perfectly on mobile

## 📋 Python Standards

### Import Organization

Always organize imports at the top of files in this exact order:

```python
# Standard library imports
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union, Any
from decimal import Decimal

# Third-party imports
import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers, viewsets

# Local application imports
from apps.core.models import BaseModel, TimeStampedModel
from apps.core.utils import calculate_hash, validate_data
from .models import MyModel
from .serializers import MySerializer
```

### Code Style Requirements

```python
# Use black for formatting (line length: 88)
# Use isort for import sorting
# Use flake8 for linting
# Use mypy for type checking

# Example of properly formatted code:
from typing import Optional
from django.db import models


class Article(models.Model):
    """
    Article model with proper type hints and documentation.
    
    Attributes:
        title: Article title (max 200 chars)
        slug: URL-friendly identifier
        content: Article body text
        published_at: Publication timestamp
    """
    
    title: str = models.CharField(
        max_length=200,
        help_text=_("Article title")
    )
    slug: str = models.SlugField(
        unique=True,
        help_text=_("URL-friendly identifier")
    )
    content: str = models.TextField(
        help_text=_("Article content")
    )
    published_at: Optional[datetime] = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Publication date and time")
    )
    
    class Meta:
        verbose_name = _("Article")
        verbose_name_plural = _("Articles")
        ordering = ["-published_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["-published_at"]),
        ]
    
    def __str__(self) -> str:
        return self.title
    
    def save(self, *args, **kwargs) -> None:
        """Override save to auto-generate slug if needed."""
        if not self.slug:
            self.slug = self._generate_unique_slug()
        super().save(*args, **kwargs)
    
    def _generate_unique_slug(self) -> str:
        """Generate unique slug from title."""
        from django.utils.text import slugify
        
        base_slug = slugify(self.title)
        slug = base_slug
        counter = 1
        
        while self.__class__.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        return slug
```

## 🗄️ Django Best Practices

### Model Standards

```python
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class BaseModel(TimeStampedModel):
    """Abstract base model with common fields."""
    
    class Meta:
        abstract = True
    
    def clean(self) -> None:
        """Override for model-level validation."""
        super().clean()
        # Add custom validation here
    
    def save(self, *args, **kwargs) -> None:
        """Override save with validation."""
        self.full_clean()
        super().save(*args, **kwargs)


class DomainModel(BaseModel):
    """
    Domain-specific model example.
    
    CUSTOMIZE THIS SECTION FOR YOUR DOMAIN:
    - Aviation: Flight data validation
    - Healthcare: Patient data compliance  
    - Finance: Audit trail requirements
    - E-commerce: Inventory tracking
    """
    
    # Example fields - customize for your domain
    name = models.CharField(
        _("Name"),
        max_length=100,
        help_text=_("Primary identifier")
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=[
            ("active", _("Active")),
            ("inactive", _("Inactive")),
            ("pending", _("Pending")),
        ],
        default="pending"
    )
    priority = models.IntegerField(
        _("Priority"),
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        default=5,
        help_text=_("Priority level (1-10)")
    )
    
    class Meta:
        verbose_name = _("Domain Model")
        verbose_name_plural = _("Domain Models")
        ordering = ["priority", "name"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(priority__gte=1) & models.Q(priority__lte=10),
                name="priority_valid_range"
            ),
        ]
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["created_at"]),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.get_status_display()})"
```

### View Standards

```python
from typing import Any, Dict, Optional
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet, Prefetch
from django.http import HttpRequest, HttpResponse
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView


class OptimizedListView(LoginRequiredMixin, ListView):
    """
    Base list view with performance optimizations.
    
    Features:
    - Optimized querysets with select/prefetch_related
    - Pagination
    - Search and filtering
    - Mobile-responsive templates
    """
    
    paginate_by = 20
    context_object_name = "objects"
    
    def get_queryset(self) -> QuerySet:
        """Return optimized queryset."""
        queryset = super().get_queryset()
        
        # Always optimize database queries
        if hasattr(queryset.model, 'select_related_fields'):
            queryset = queryset.select_related(*queryset.model.select_related_fields)
        
        if hasattr(queryset.model, 'prefetch_related_fields'):
            queryset = queryset.prefetch_related(*queryset.model.prefetch_related_fields)
        
        # Add search functionality
        search_query = self.request.GET.get('search')
        if search_query and hasattr(self, 'search_fields'):
            from django.db.models import Q
            query = Q()
            for field in self.search_fields:
                query |= Q(**{f"{field}__icontains": search_query})
            queryset = queryset.filter(query)
        
        return queryset
    
    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add extra context."""
        context = super().get_context_data(**kwargs)
        context.update({
            'search_query': self.request.GET.get('search', ''),
            'page_title': getattr(self, 'page_title', 'List'),
            'can_add': self.request.user.has_perm(f"{self.model._meta.app_label}.add_{self.model._meta.model_name}"),
        })
        return context


class DomainModelListView(OptimizedListView):
    """Domain-specific list view example."""
    
    model = DomainModel
    template_name = "domain/model_list.html"
    page_title = "Domain Models"
    search_fields = ["name", "status"]
    
    def get_queryset(self) -> QuerySet:
        """Add domain-specific filtering."""
        queryset = super().get_queryset()
        
        # Filter by status if provided
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('priority', 'name')
```

### Form Standards

```python
from typing import Any, Dict
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import DomainModel


class BaseModelForm(forms.ModelForm):
    """Base form with common functionality."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add CSS classes for mobile-first styling
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'form-control',
                'placeholder': field.label,
            })
            
            # Mobile-friendly attributes
            if isinstance(field.widget, forms.EmailInput):
                field.widget.attrs.update({
                    'inputmode': 'email',
                    'autocomplete': 'email',
                })
            elif isinstance(field.widget, forms.NumberInput):
                field.widget.attrs.update({
                    'inputmode': 'numeric',
                })
    
    def clean(self) -> Dict[str, Any]:
        """Form-level validation."""
        cleaned_data = super().clean()
        
        # Add cross-field validation here
        # Example: validate business rules
        
        return cleaned_data


class DomainModelForm(BaseModelForm):
    """Domain-specific form with custom validation."""
    
    class Meta:
        model = DomainModel
        fields = ["name", "status", "priority"]
        widgets = {
            "name": forms.TextInput(attrs={"maxlength": 100}),
            "status": forms.Select(),
            "priority": forms.NumberInput(attrs={"min": 1, "max": 10}),
        }
    
    def clean_name(self) -> str:
        """Validate name field."""
        name = self.cleaned_data.get('name')
        if not name:
            raise ValidationError(_("Name is required"))
        
        # Check for duplicates (excluding current instance)
        queryset = DomainModel.objects.filter(name__iexact=name)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        
        if queryset.exists():
            raise ValidationError(_("A model with this name already exists"))
        
        return name.strip().title()
    
    def clean_priority(self) -> int:
        """Validate priority field."""
        priority = self.cleaned_data.get('priority')
        if priority is not None and (priority < 1 or priority > 10):
            raise ValidationError(_("Priority must be between 1 and 10"))
        return priority
```

## 🧪 Testing Standards

### Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Pytest configuration
├── factories.py             # Test data factories
├── test_models.py           # Model tests
├── test_views.py            # View tests
├── test_forms.py            # Form tests
├── test_utils.py            # Utility function tests
└── integration/             # Integration tests
    ├── __init__.py
    ├── test_user_workflows.py
    └── test_api_endpoints.py
```

### Test Examples

```python
# tests/test_models.py
import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.domain.models import DomainModel
from .factories import DomainModelFactory


class DomainModelTests(TestCase):
    """Test cases for DomainModel."""
    
    def setUp(self) -> None:
        """Set up test data."""
        self.model = DomainModelFactory(name="Test Model")
    
    def test_str_representation(self) -> None:
        """Test string representation."""
        expected = f"{self.model.name} ({self.model.get_status_display()})"
        self.assertEqual(str(self.model), expected)
    
    def test_slug_generation(self) -> None:
        """Test automatic slug generation."""
        model = DomainModel.objects.create(
            name="Test Model with Spaces",
            status="active"
        )
        self.assertEqual(model.slug, "test-model-with-spaces")
    
    def test_priority_validation(self) -> None:
        """Test priority field validation."""
        # Valid priority
        model = DomainModel(name="Valid", priority=5)
        model.full_clean()  # Should not raise
        
        # Invalid priority - too low
        model = DomainModel(name="Invalid Low", priority=0)
        with self.assertRaises(ValidationError):
            model.full_clean()
        
        # Invalid priority - too high
        model = DomainModel(name="Invalid High", priority=11)
        with self.assertRaises(ValidationError):
            model.full_clean()
    
    @pytest.mark.django_db
    def test_duplicate_name_prevention(self) -> None:
        """Test that duplicate names are prevented."""
        DomainModel.objects.create(name="Unique Name", status="active")
        
        with self.assertRaises(IntegrityError):
            DomainModel.objects.create(name="Unique Name", status="active")


# tests/factories.py
import factory
from factory.django import DjangoModelFactory

from apps.domain.models import DomainModel


class DomainModelFactory(DjangoModelFactory):
    """Factory for creating DomainModel instances."""
    
    class Meta:
        model = DomainModel
    
    name = factory.Sequence(lambda n: f"Model {n}")
    status = "active"
    priority = factory.Faker("random_int", min=1, max=10)


# tests/test_views.py
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from .factories import DomainModelFactory

User = get_user_model()


class DomainModelViewTests(TestCase):
    """Test cases for DomainModel views."""
    
    def setUp(self) -> None:
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.model = DomainModelFactory()
    
    def test_list_view_requires_login(self) -> None:
        """Test that list view requires authentication."""
        url = reverse("domain:model-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_list_view_authenticated(self) -> None:
        """Test list view for authenticated users."""
        self.client.force_login(self.user)
        url = reverse("domain:model-list")
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.model.name)
        self.assertTemplateUsed(response, "domain/model_list.html")
    
    def test_list_view_search(self) -> None:
        """Test search functionality in list view."""
        self.client.force_login(self.user)
        url = reverse("domain:model-list")
        response = self.client.get(url, {"search": self.model.name[:5]})
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.model.name)
```

### Performance Testing

```python
# tests/test_performance.py
import time
from django.test import TestCase
from django.test.utils import override_settings
from django.db import connection

from .factories import DomainModelFactory


class PerformanceTests(TestCase):
    """Test database query performance."""
    
    def setUp(self) -> None:
        """Create test data."""
        # Create multiple objects for realistic testing
        DomainModelFactory.create_batch(100)
    
    def test_list_view_query_count(self) -> None:
        """Test that list view doesn't have N+1 query problems."""
        from apps.domain.views import DomainModelListView
        
        view = DomainModelListView()
        view.request = self.request_factory.get("/")
        
        with self.assertNumQueries(1):  # Should be 1 optimized query
            list(view.get_queryset())
    
    def test_response_time(self) -> None:
        """Test response time is acceptable."""
        self.client.force_login(self.user)
        url = reverse("domain:model-list")
        
        start_time = time.time()
        response = self.client.get(url)
        end_time = time.time()
        
        self.assertEqual(response.status_code, 200)
        self.assertLess(end_time - start_time, 1.0)  # Less than 1 second
```

## 🚀 Performance Standards

### Database Optimization

```python
# Always use select_related and prefetch_related
queryset = (
    DomainModel.objects
    .select_related('user', 'category')  # Forward FKs
    .prefetch_related('tags', 'comments')  # Reverse FKs, M2M
    .filter(status='active')
    .order_by('-created_at')
)

# Use database indexes
class Meta:
    indexes = [
        models.Index(fields=['status', 'priority']),  # Composite index
        models.Index(fields=['-created_at']),         # Ordering field
        models.Index(fields=['slug']),                # Lookup field
    ]

# Use database constraints for data integrity
class Meta:
    constraints = [
        models.CheckConstraint(
            check=models.Q(priority__gte=1) & models.Q(priority__lte=10),
            name='priority_valid_range'
        ),
        models.UniqueConstraint(
            fields=['user', 'name'],
            name='unique_user_name'
        ),
    ]
```

### Caching Strategy

```python
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator

# View-level caching
@method_decorator(cache_page(60 * 15), name='dispatch')  # 15 minutes
class CachedListView(ListView):
    """List view with caching."""
    pass

# Template fragment caching
# In templates:
# {% load cache %}
# {% cache 300 model_list %}
#   <!-- expensive template code -->
# {% endcache %}

# Low-level caching
def get_expensive_data(key: str) -> Dict[str, Any]:
    """Get data with caching."""
    cache_key = f"expensive_data_{key}"
    data = cache.get(cache_key)
    
    if data is None:
        data = calculate_expensive_data(key)
        cache.set(cache_key, data, 60 * 30)  # 30 minutes
    
    return data
```

## 📱 Mobile-First Development

### Template Standards

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="{% block meta_description %}Default description{% endblock %}">
    
    <!-- Mobile-friendly meta tags -->
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="theme-color" content="#your-primary-color">
    
    <title>{% block title %}Project Name{% endblock %}</title>
    
    <!-- CSS - mobile-first stylesheets -->
    <link href="{% static 'css/base.css' %}" rel="stylesheet">
    {% block extra_css %}{% endblock %}
</head>
<body>
    <!-- Mobile-first navigation -->
    <nav class="navbar" role="navigation" aria-label="main navigation">
        <div class="navbar-brand">
            <a class="navbar-item" href="{% url 'home' %}">
                <img src="{% static 'img/logo.svg' %}" alt="Logo" width="32" height="32">
                <span class="navbar-title">Project Name</span>
            </a>
            
            <!-- Mobile menu toggle -->
            <button class="navbar-burger" 
                    aria-label="menu" 
                    aria-expanded="false" 
                    data-target="navbarMenu">
                <span aria-hidden="true"></span>
                <span aria-hidden="true"></span>
                <span aria-hidden="true"></span>
            </button>
        </div>
        
        <div id="navbarMenu" class="navbar-menu">
            <!-- Navigation items -->
        </div>
    </nav>
    
    <!-- Main content -->
    <main class="main-content" role="main">
        <!-- Mobile-friendly messages -->
        {% if messages %}
            <div class="messages-container">
                {% for message in messages %}
                    <div class="alert alert-{{ message.tags }}" role="alert">
                        {{ message }}
                        <button class="alert-close" aria-label="Close">×</button>
                    </div>
                {% endfor %}
            </div>
        {% endif %}
        
        {% block content %}{% endblock %}
    </main>
    
    <!-- Mobile-first JavaScript -->
    <script src="{% static 'js/base.js' %}"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

### Form Templates

```html
<!-- templates/forms/base_form.html -->
<form method="post" class="form" novalidate>
    {% csrf_token %}
    
    {% if form.non_field_errors %}
        <div class="alert alert-danger" role="alert">
            {{ form.non_field_errors }}
        </div>
    {% endif %}
    
    {% for field in form %}
        <div class="form-group{% if field.errors %} form-group--error{% endif %}">
            {% if field.field.widget.input_type != 'hidden' %}
                <label for="{{ field.id_for_label }}" class="form-label">
                    {{ field.label }}
                    {% if field.field.required %}
                        <span class="required" aria-label="required">*</span>
                    {% endif %}
                </label>
            {% endif %}
            
            {{ field }}
            
            {% if field.help_text %}
                <small class="form-help" id="{{ field.id_for_label }}_help">
                    {{ field.help_text }}
                </small>
            {% endif %}
            
            {% if field.errors %}
                <div class="form-errors" role="alert">
                    {{ field.errors }}
                </div>
            {% endif %}
        </div>
    {% endfor %}
    
    <div class="form-actions">
        <button type="submit" class="btn btn-primary">
            {% block submit_text %}Save{% endblock %}
        </button>
        
        <a href="{% block cancel_url %}{{ request.META.HTTP_REFERER|default:'/' }}{% endblock %}" 
           class="btn btn-secondary">
            Cancel
        </a>
    </div>
</form>
```

## 🔒 Security Standards

### Input Validation

```python
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
import re

class SecureModelForm(forms.ModelForm):
    """Form with security validations."""
    
    def clean_user_input(self) -> str:
        """Validate and sanitize user input."""
        value = self.cleaned_data.get('user_input', '')
        
        # Remove potentially dangerous characters
        sanitized = re.sub(r'[<>"\']', '', value)
        
        # Additional validation
        if len(sanitized) > 1000:
            raise ValidationError("Input too long")
        
        return sanitized.strip()

# Custom validators
phone_validator = RegexValidator(
    regex=r'^\+?1?\d{9,15}$',
    message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
)

class SecureModel(models.Model):
    """Model with secure field validation."""
    
    phone_number = models.CharField(
        max_length=17,
        validators=[phone_validator],
        help_text="Phone number in international format"
    )
```

### SQL Injection Prevention

```python
# ✅ Safe - using Django ORM
users = User.objects.filter(username=user_input)

# ✅ Safe - parameterized raw SQL
cursor.execute("SELECT * FROM users WHERE username = %s", [user_input])

# ❌ Dangerous - string concatenation
cursor.execute(f"SELECT * FROM users WHERE username = '{user_input}'")
```

## 📊 Domain-Specific Standards

### CUSTOMIZE THIS SECTION

**Replace this section with standards specific to your domain:**

#### For Aviation/Aerospace Projects:
```python
class FlightDataValidator:
    """Aviation-specific validation rules."""
    
    @staticmethod
    def validate_flight_time(departure: datetime, arrival: datetime) -> None:
        """Validate flight times against regulations."""
        if arrival <= departure:
            raise ValidationError("Arrival time must be after departure")
        
        duration = (arrival - departure).total_seconds() / 3600
        if duration > 16:  # FAR limits
            raise ValidationError("Flight time exceeds regulatory limits")
```

#### For Healthcare Projects:
```python
class PatientDataValidator:
    """Healthcare-specific validation rules."""
    
    @staticmethod
    def validate_patient_id(patient_id: str) -> None:
        """Validate patient ID format for HIPAA compliance."""
        if not re.match(r'^P\d{8}$', patient_id):
            raise ValidationError("Invalid patient ID format")
```

#### For Financial Projects:
```python
class FinancialValidator:
    """Financial-specific validation rules."""
    
    @staticmethod
    def validate_currency_amount(amount: Decimal) -> None:
        """Validate monetary amounts."""
        if amount < 0:
            raise ValidationError("Amount cannot be negative")
        if amount.as_tuple().exponent < -2:
            raise ValidationError("Amount cannot have more than 2 decimal places")
```

## 🚀 Deployment Standards

### Environment Configuration

```python
# config/settings/base.py
import os
from pathlib import Path
from decouple import config

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Security
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=lambda v: [s.strip() for s in v.split(',')])

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'OPTIONS': {
            'sslmode': config('DB_SSLMODE', default='prefer'),
        }
    }
}

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 1024*1024*10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['file'],
        'level': 'INFO',
    },
}
```

## 📋 Code Review Checklist

### Before Submitting Code

- [ ] All imports organized correctly
- [ ] Type hints added to all functions
- [ ] Docstrings written for all public methods
- [ ] Tests written and passing
- [ ] Database queries optimized
- [ ] Mobile-responsive templates
- [ ] Security considerations addressed
- [ ] Error handling implemented
- [ ] Logging added for important operations
- [ ] Performance tested
- [ ] Accessibility checked

### Code Review Points

- [ ] Code follows project style guide
- [ ] No hardcoded values (use settings/environment)
- [ ] Proper error handling and user feedback
- [ ] Database migrations are safe and reversible
- [ ] URLs follow consistent naming patterns
- [ ] Templates extend base templates correctly
- [ ] Forms include proper validation
- [ ] Views handle permissions correctly
- [ ] Models include appropriate indexes
- [ ] Tests cover edge cases

## 🛠️ Development Tools

### Required Tools

```bash
# Install development dependencies
pip install black isort flake8 mypy django-stubs pytest pytest-django coverage

# Pre-commit hooks
pip install pre-commit
pre-commit install

# Code formatting
black .
isort .

# Linting
flake8

# Type checking
mypy apps/

# Testing
pytest --cov=apps
```

### IDE Configuration

#### VS Code Settings (.vscode/settings.json)
```json
{
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    },
    "python.linting.mypyEnabled": true
}
```

---

## 📝 Documentation Requirements

### Docstring Standards

```python
def complex_function(
    data: Dict[str, Any], 
    threshold: float = 0.5,
    validate: bool = True
) -> Optional[List[str]]:
    """
    Process complex data with validation and filtering.
    
    Args:
        data: Dictionary containing raw data to process
        threshold: Minimum confidence threshold (0.0 to 1.0)
        validate: Whether to run validation checks
    
    Returns:
        List of processed strings, or None if processing failed
    
    Raises:
        ValidationError: If data validation fails
        ValueError: If threshold is out of range
    
    Examples:
        >>> process_data({"key": "value"}, threshold=0.8)
        ["processed_value"]
    """
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("Threshold must be between 0.0 and 1.0")
    
    # Implementation here
    pass
```

### README Template

```markdown
# Project Name

Brief description of what this project does.

## Quick Start

```bash
# Clone and setup
git clone <repository>
cd project-name

# Setup environment
pyenv activate project-name
pip install -r requirements/development.txt

# Run development server
python manage.py migrate
python manage.py runserver
```

## Development

- **Style Guide**: See `docs/STYLE_GUIDE.md`
- **Coding Standards**: See `docs/CODING_GUIDE.md`
- **Project Context**: See `CLAUDE.md`

## Testing

```bash
pytest --cov=apps
```

## Deployment

```bash
./build.sh -r -d $(date +%Y%m%d)
```
```

---

*This coding guide ensures consistent, maintainable, and secure code across your Django project. Customize the domain-specific sections for your particular use case.*