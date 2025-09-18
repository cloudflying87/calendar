# Project Style Guide Template

**INSTRUCTIONS**: This template creates a custom style guide for your Django project. Answer the questionnaire below, then run the theme generator to create your custom CSS system.

## Theme Configuration Questionnaire

Please answer these questions to generate your project's custom CSS framework:

### 1. Project Identity

**Project Name**: calendar-builder *(e.g., "AirlineOps", "MedTracker")*

**Project Type**:
- [ ] Business/Enterprise Application
- [ ] Consumer Web App
- [ ] Internal Dashboard/Tool
- [ ] E-commerce Platform
- [ ] Content Management System
- [ ] Other: _________________

**Industry/Domain**:
- [ ] Aviation/Aerospace
- [ ] Healthcare/Medical
- [ ] Finance/Banking
- [ ] Education
- [ ] Government
- [ ] Technology/SaaS
- [ ] Other: _________________

### 2. Brand Colors

**Primary Color**: #2563eb *(Main brand color for buttons, links, headers)*
**Secondary Color**: #64748b *(Supporting color for accents, highlights)*
**Accent Color**: #0ea5e9 *(Special indicators, badges, alerts)*

**Neutral Preferences**:
- [ ] Warm grays (#f8f9fa, #6c757d, etc.)
- [ ] Cool grays (#f1f3f4, #5f6368, etc.)
- [ ] Pure grays (#ffffff, #808080, #000000)

### 3. Design Style

**Overall Aesthetic**:
- [ ] Professional & Corporate (clean, trustworthy)
- [ ] Modern & Minimal (lots of white space, simple)
- [ ] Friendly & Approachable (rounded corners, warm colors)
- [ ] Technical & Precise (sharp lines, data-focused)
- [ ] Creative & Bold (unique elements, standout design)

**Border Radius Preference**:
- [ ] Sharp corners (0px) - Technical/precise feel
- [ ] Subtle rounding (4px) - Professional balance
- [ ] Medium rounding (8px) - Friendly and modern
- [ ] High rounding (16px+) - Very approachable

**Shadow Style**:
- [ ] No shadows (flat design)
- [ ] Subtle shadows (barely visible depth)
- [ ] Medium shadows (clear depth)
- [ ] Strong shadows (pronounced 3D effect)

### 4. Typography

**Font Style Preference**:
- [ ] System fonts (fastest, familiar) - `-apple-system, BlinkMacSystemFont, "Segoe UI"`
- [ ] Google Fonts - Professional: _________________ *(e.g., "Inter", "Roboto")*
- [ ] Google Fonts - Friendly: _________________ *(e.g., "Open Sans", "Lato")*
- [ ] Custom fonts: _________________

**Heading Style**:
- [ ] Bold and prominent (strong hierarchy)
- [ ] Subtle and refined (minimal contrast)
- [ ] Mixed weights (varied visual interest)

### 5. Component Preferences

**Button Style**:
- [ ] Solid fill (filled background)
- [ ] Outline only (border, transparent background)
- [ ] Ghost buttons (minimal, text-like)
- [ ] Mixed approach (primary solid, secondary outline)

**Form Input Style**:
- [ ] Full border (traditional, clear boundaries)
- [ ] Underline only (minimal, modern)
- [ ] Filled background (material design style)
- [ ] Floating labels (space-efficient)

**Card Style**:
- [ ] Bordered cards (clear separation)
- [ ] Shadow cards (elevated appearance)
- [ ] Minimal cards (subtle background difference)
- [ ] No cards (flat sections)

### 6. Mobile Experience

**Navigation Style**:
- [ ] Top navbar (traditional desktop-style)
- [ ] Bottom tabs (mobile-native)
- [ ] Hamburger menu (space-efficient)
- [ ] Drawer/sidebar (slide-out menu)

**Touch Target Preference**:
- [ ] Standard (44px) - iOS guideline
- [ ] Large (48px) - Android guideline
- [ ] Extra large (56px) - accessibility focused

**Mobile-First Breakpoints**:
- [ ] Standard: 576px, 768px, 992px, 1200px
- [ ] Mobile-focused: 375px, 768px, 1024px
- [ ] Custom: _________________, _________________, _________________

### 7. Dark Mode

**Dark Mode Support**:
- [ ] Yes, with automatic detection (prefers-color-scheme)
- [ ] Yes, with manual toggle only
- [ ] No dark mode needed
- [ ] Undecided (implement basic support)

**Dark Mode Style** *(if supported)*:
- [ ] Pure black backgrounds (#000000)
- [ ] Dark gray backgrounds (#121212, #1e1e1e)
- [ ] Tinted dark (slight color tint matching brand)

### 8. Animation & Interaction

**Animation Preference**:
- [ ] None (maximum performance, no distractions)
- [ ] Minimal (subtle transitions only)
- [ ] Moderate (smooth interactions, tasteful effects)
- [ ] Rich (engaging animations, delightful micro-interactions)

**Loading Indicators**:
- [ ] Simple spinner
- [ ] Progress bars
- [ ] Skeleton screens (content placeholders)
- [ ] Custom animated logo/icon

### 9. Data Display

**Table Style**:
- [ ] Striped rows (alternating backgrounds)
- [ ] Bordered (grid lines)
- [ ] Minimal (hover effects only)
- [ ] Card-based (mobile-friendly)

**Status Indicators**:
- [ ] Color-coded backgrounds
- [ ] Colored text
- [ ] Icons with color
- [ ] Badges/pills

**Priority Levels** *(for alerts, notifications)*:
- Success Color: #_________ *(or use default green)*
- Warning Color: #_________ *(or use default orange)*
- Error Color: #_________ *(or use default red)*
- Info Color: #_________ *(or use default blue)*

### 10. Industry-Specific Preferences

**Special Requirements**:
- [ ] Accessibility compliance (WCAG 2.1 AA)
- [ ] High contrast for readability
- [ ] Print-friendly layouts
- [ ] Offline-first design considerations
- [ ] Real-time data displays
- [ ] Map/geospatial interfaces
- [ ] Charts and data visualization

**Regulatory/Compliance**:
- [ ] Medical (HIPAA considerations)
- [ ] Financial (security emphasis)
- [ ] Aviation (safety-critical appearance)
- [ ] Government (accessibility, contrast)
- [ ] None specific

---

## Generated Theme Variables

*After completing the questionnaire above, run: `python scripts/generate_theme.py`*

The generator will create your custom `static/css/base.css` with variables like:

```css
:root {
    /* Brand Colors - FROM YOUR ANSWERS */
    --primary-color: #your-primary-color;
    --secondary-color: #your-secondary-color;
    --accent-color: #your-accent-color;
    
    /* Generated Semantic Colors */
    --success-color: #28a745; /* or your custom */
    --warning-color: #ffc107; /* or your custom */
    --danger-color: #dc3545;  /* or your custom */
    --info-color: #17a2b8;    /* or your custom */
    
    /* Calculated Neutrals */
    --bg-primary: #ffffff;
    --bg-secondary: #f8f9fa;
    --text-primary: #212529;
    --text-secondary: #6c757d;
    
    /* Design System */
    --border-radius: 4px; /* from your choice */
    --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto;
    
    /* Spacing System */
    --spacing-xs: 0.25rem;
    --spacing-sm: 0.5rem;
    --spacing-md: 1rem;
    --spacing-lg: 1.5rem;
    --spacing-xl: 2rem;
    
    /* Component Sizing */
    --button-height: 44px; /* mobile-first */
    --input-height: 44px;
    --touch-target: 44px;
}

/* Dark Mode Variables (if selected) */
[data-theme="dark"] {
    --bg-primary: #1a1a1a;
    --bg-secondary: #2d2d2d;
    --text-primary: #f0f0f0;
    --text-secondary: #b0b0b0;
}
```

## Component Architecture

Your custom CSS system will include these component files:

### Core Files
- `static/css/base.css` - CSS variables, typography, utilities
- `static/css/components/buttons.css` - All button variants
- `static/css/components/forms.css` - Form controls and layouts
- `static/css/components/cards.css` - Card components
- `static/css/components/modals.css` - Modal dialogs
- `static/css/components/tables.css` - Data tables
- `static/css/components/navigation.css` - Navigation components

### Mobile-First Patterns

Every component follows mobile-first design:

```css
/* Mobile first (default) */
.component {
    padding: var(--spacing-sm);
    font-size: 1rem;
}

/* Tablet and up */
@media (min-width: 768px) {
    .component {
        padding: var(--spacing-md);
        font-size: 0.875rem;
    }
}
```

## Usage Guidelines

### CSS Class Naming Convention

Following BEM methodology with semantic names:

```html
<!-- Component classes -->
<div class="card">
  <div class="card__header">
    <h3 class="card__title">Title</h3>
  </div>
  <div class="card__body">
    <p class="card__text">Content</p>
  </div>
</div>

<!-- Utility classes -->
<div class="text-center mt-3 mb-2">
  <button class="btn btn--primary btn--large">
    Primary Action
  </button>
</div>
```

### Responsive Design Approach

Always start with mobile, enhance for larger screens:

```css
/* ✅ Good - Mobile first */
.hero-section {
    padding: 2rem 1rem;
    text-align: center;
}

@media (min-width: 768px) {
    .hero-section {
        padding: 4rem 2rem;
        text-align: left;
    }
}

/* ❌ Avoid - Desktop first */
.hero-section {
    padding: 4rem 2rem;
    text-align: left;
}

@media (max-width: 767px) {
    .hero-section {
        padding: 2rem 1rem;
        text-align: center;
    }
}
```

### Dark Mode Implementation

When dark mode is enabled, use the generated CSS variables:

```css
.custom-component {
    background-color: var(--bg-primary);
    color: var(--text-primary);
    border: 1px solid var(--border-color);
}

/* Automatically works in dark mode - no additional CSS needed */
```

## Theme Generator Script

Create `scripts/generate_theme.py`:

```python
#!/usr/bin/env python3
"""
Theme Generator Script
Reads answers from STYLE_GUIDE.md and generates custom CSS
"""

import re
import os
from pathlib import Path

def extract_answers_from_style_guide():
    """Extract answers from the style guide questionnaire."""
    style_guide_path = Path("docs/STYLE_GUIDE.md")
    if not style_guide_path.exists():
        print("❌ STYLE_GUIDE.md not found")
        return None
    
    content = style_guide_path.read_text()
    answers = {}
    
    # Extract filled-in answers
    # Project Name
    name_match = re.search(r'\*\*Project Name\*\*:\s*([^\n\*]+)', content)
    if name_match:
        answers['project_name'] = name_match.group(1).strip()
    
    # Colors
    primary_match = re.search(r'\*\*Primary Color\*\*:\s*#([a-fA-F0-9]{6})', content)
    if primary_match:
        answers['primary_color'] = f"#{primary_match.group(1)}"
    
    # Add more extraction logic here...
    
    return answers

def generate_css_from_answers(answers):
    """Generate CSS content from questionnaire answers."""
    primary = answers.get('primary_color', '#0066cc')
    secondary = answers.get('secondary_color', '#6c757d')
    
    css_content = f'''/* Generated Theme - {answers.get('project_name', 'Project')} */

:root {{
    /* Brand Colors */
    --primary-color: {primary};
    --secondary-color: {secondary};
    
    /* Add more generated variables... */
}}'''
    
    return css_content

if __name__ == "__main__":
    print("🎨 Generating theme from style guide...")
    answers = extract_answers_from_style_guide()
    
    if answers:
        css_content = generate_css_from_answers(answers)
        
        # Write to base.css
        css_dir = Path("static/css")
        css_dir.mkdir(parents=True, exist_ok=True)
        
        (css_dir / "base.css").write_text(css_content)
        print("✅ Theme generated successfully!")
    else:
        print("❌ Please fill out the questionnaire in STYLE_GUIDE.md first")
```

## Implementation Checklist

After completing the questionnaire:

- [ ] Fill out all questionnaire answers above
- [ ] Run `python scripts/generate_theme.py`
- [ ] Verify `static/css/base.css` was created
- [ ] Test light mode appearance
- [ ] Test dark mode (if enabled)
- [ ] Check mobile responsive behavior
- [ ] Validate accessibility (color contrast, touch targets)
- [ ] Update `CLAUDE.md` with theme decisions

## Maintenance Notes

- **Color Changes**: Update questionnaire answers and re-run generator
- **New Components**: Follow the established CSS variable system
- **Responsive Issues**: Always start with mobile-first approach
- **Accessibility**: Test with screen readers and keyboard navigation
- **Performance**: CSS variables enable efficient theming with minimal CSS

---

*This style guide ensures consistent, accessible, mobile-first design while maintaining complete control over your project's visual identity.*