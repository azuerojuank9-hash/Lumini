# Design System

## Overview

LUMINI implements a complete CSS custom property (variable) design system with full dark and light theme support. All visual properties are driven by CSS variables defined in `theme.css`.

## Theme Variables

Defined in `static/css/theme.css`:

| Variable | Dark | Light | Purpose |
|---|---|---|---|
| `--bg` | `#080B14` | `#F8FAFC` | Page background |
| `--bg2` | `#0F172A` | `#FFFFFF` | Card/surface |
| `--bg3` | `#1E293B` | `#F1F5F9` | Elevated surface |
| `--bg4` | `#334155` | `#E2E8F0` | Border/hover |
| `--text` | `#F8FAFC` | `#0F172A` | Primary text |
| `--muted` | `#94A3B8` | `#64748B` | Secondary text |
| `--border` | `rgba(255,255,255,.06)` | `rgba(0,0,0,.08)` | Borders |
| `--accent` | Per-school | Per-school | Primary accent |
| `--accent2` | Per-school | Per-school | Secondary accent |
| `--radius-sm` | `6px` | `6px` | Small border radius |
| `--radius-md` | `10px` | `10px` | Medium border radius |
| `--radius-lg` | `14px` | `14px` | Large border radius |

## Accent Colors

Per-school accent colors are injected via the `accent_css()` context processor:

```python
def accent_css(colegio):
    primary = colegio.primary_color or '#7C3AED'
    secondary = colegio.secondary_color or '#6D28D9'
    # Returns --accent, --accent2, --accent-rgb
```

Templates override the `accent_css` block:

```jinja
{% block accent_css %}{{ accent_css(colegio) }}{% endblock %}
```

## Theme Toggle

The toggle is in `base.html` and managed by `static/js/theme.js`:
- Reads `localStorage.getItem('theme')` on load
- Sets `data-theme` attribute on `<html>`
- Persists choice to `localStorage`

## CSS File Loading Order

1. `base.css` — Reset, base element styles
2. `theme.css` — CSS variables (both themes)
3. `layout.css` — Grid, sidebar, main content
4. `buttons.css` — Button system
5. `forms.css` — Form elements
6. `tables.css` — Table styles
7. `cards.css` — Card components
8. `badges.css` — Badge components
9. `alerts.css` — Alert components
10. `animations.css` — Keyframes, transitions
11. `utilities.css` — Spacing, flex helpers
12. `dashboard.css` — Dashboard widgets
13. `attendance.css` — Attendance-specific
