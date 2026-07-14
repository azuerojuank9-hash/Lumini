# Frontend Architecture

## Overview

LUMINI uses a Jinja2 server-side rendering architecture with a modular design system. Templates are rendered on the server and enhanced with JavaScript for interactivity.

## Directory Structure

```
templates/
├── base.html              # Base skeleton (CSS/JS imports, layout blocks)
├── components.html         # Backward-compatible re-export file
├── components/             # Reusable Jinja macro library
│   ├── sidebar.html
│   ├── card.html
│   ├── table.html
│   ├── modal.html
│   ├── button.html
│   ├── badge.html
│   ├── alert.html
│   ├── toast.html
│   ├── form.html
│   ├── empty_state.html
│   ├── pagination.html
│   └── search.html
├── rector/                 # Rector sub-templates
├── *.html                  # 41 page templates (inherits base.html)
static/
├── css/                    # Modular design system
│   ├── base.css            # Reset, base elements
│   ├── theme.css           # CSS variables (dark/light)
│   ├── layout.css          # Grid, sidebar, main
│   ├── buttons.css         # Button system
│   ├── forms.css           # Form controls
│   ├── tables.css          # Tables, sorting
│   ├── cards.css           # Cards, stats cards
│   ├── badges.css          # Badges, status badges
│   ├── alerts.css          # Alerts, toasts
│   ├── dashboard.css       # Dashboard widgets
│   ├── attendance.css      # Attendance grid
│   ├── animations.css      # Keyframes, transitions
│   └── utilities.css       # Spacing, flex helpers
└── js/                     # Modular JavaScript
    ├── utils.js            # Debounce, throttle, format helpers
    ├── theme.js            # Dark/light theme toggle
    ├── tables.js           # Table sort, filter, row selection
    ├── modals.js           # Modal open/close
    ├── forms.js            # Form validation, required fields
    ├── dashboard.js        # Counter animation, chart init
    ├── attendance.js       # Attendance API calls
    ├── notifications.js    # Toast system, push notifications
    ├── lumini.js           # Legacy support (deferred)
    ├── pwa.js              # Service worker, PWA install
    └── notification-manager.js  # Legacy push notification
```

## Component Usage

Templates import macros from `components.html`:

```jinja
{% from "components.html" import sidebar_item, badge, card, btn, alert_error %}
```

### Available Macros

| Macro | Parameters | Description |
|---|---|---|
| `sidebar_item(url, icon, label, active, count)` | Full | Sidebar navigation item |
| `card(heading, body, icon, class, interactive, id)` | Full | Content card container |
| `stats_card(value, label, icon, color, change)` | Full | KPI statistics card |
| `btn(url, label, class, icon, onclick, type)` | Full | Button or link button |
| `modal(id, title, body, confirm_text, cancel_text)` | Full | Dialog modal |
| `badge(text, type, size, dot)` | Full | Inline badge |
| `status_badge(status)` | Map | Auto-colored status badge |
| `alert_error/alert_success/alert_warning/alert_info` | Full | Alert banners |
| `empty_state(icon, title, description, action_url, action_text)` | Full | Empty state placeholder |
| `input(name, label, value, type, placeholder, required, error)` | Full | Form input with validation |
| `pagination(current, total, base_url)` | Full | Page navigation |
| `search_bar(name, placeholder, value, id)` | Full | Search input |

## Theming

- Dark theme is default (`data-theme="dark"`)
- Light theme: `<html data-theme="light">`
- Accent colors injected per-school via `accent_css()` context processor
- CSS variables in `theme.css` drive all component colors
