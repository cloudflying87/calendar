from django import template
from datetime import datetime

register = template.Library()

@register.filter
def split(value, delimiter):
    """Split a string by delimiter and return a list"""
    if not value:
        return []
    return value.split(delimiter)

@register.simple_tag
def calculate_current_age(year_occurred, event_type):
    """Calculate current age or years since an event occurred"""
    if not year_occurred:
        return None

    current_year = datetime.now().year
    years_since = current_year - year_occurred

    if years_since < 0:
        return None

    if event_type == 'birthday':
        if years_since == 0:
            return "Newborn"
        elif years_since == 1:
            return "1 year old"
        else:
            return f"{years_since} years old"
    elif event_type == 'anniversary':
        if years_since == 0:
            return "This year"
        elif years_since == 1:
            return "1 year"
        else:
            return f"{years_since} years"
    else:
        # For other event types, just show years since
        if years_since == 0:
            return "This year"
        elif years_since == 1:
            return "1 year ago"
        else:
            return f"{years_since} years ago"