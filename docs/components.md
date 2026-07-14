# Component Library

## Jinja Macros

All reusable UI components are defined as Jinja2 macros in `templates/components/`. The `templates/components.html` file re-exports all macros for backward compatibility.

## Sidebar

**File:** `templates/components/sidebar.html`

```jinja
{% from "components.html" import sidebar_item, sidebar_section, sidebar with context %}

{{ sidebar_item(url, icon, label, active=false, count=0) }}
{{ sidebar_section(title) }}
```

## Card

**File:** `templates/components/card.html`

```jinja
{% from "components.html" import card, stats_card, kpi_card %}

{{ card("Title", "Body content") }}
{{ stats_card("150", "Students", "users", "accent", change=12) }}
{{ kpi_card("85%", "Attendance", "calendar-check") }}
```

## Alert

**File:** `templates/components/alert.html`

```jinja
{% from "components.html" import alert_error, alert_success, alert_warning, alert_info %}

{{ alert_error("Something went wrong", dismissible=true) }}
{{ alert_success("Operation completed") }}
```

## Badge

**File:** `templates/components/badge.html`

```jinja
{% from "components.html" import badge, status_badge %}

{{ badge("Active", "success") }}
{{ badge("Pending", "warning", dot=true) }}
{{ status_badge("publicado") }}  {# auto-colors: success #}
```

## Button

**File:** `templates/components/button.html`

```jinja
{% from "components.html" import btn %}

{{ btn(url="/path", label="Go", class="btn-primary") }}
{{ btn(label="Submit", type="submit", class="btn-primary") }}
```

## Modal

**File:** `templates/components/modal.html`

```jinja
{% from "components.html" import modal %}

{{ modal("my-modal", "Confirm", "Are you sure?") }}
```

## Form

**File:** `templates/components/form.html`

```jinja
{% from "components.html" import input %}

{{ input("email", label="Email", type="email", required=true) }}
{{ input("bio", label="Bio", type="textarea") }}
```

## CSS Classes Reference

| Component | Available Classes |
|---|---|
| Buttons | `.btn`, `.btn-primary`, `.btn-secondary`, `.btn-ghost`, `.btn-danger`, `.btn-sm`, `.btn-lg`, `.btn-icon`, `.btn-icon-sm` |
| Cards | `.card`, `.card-head`, `.card-body`, `.card-interactive`, `.stats-card`, `.kpi-card` |
| Forms | `.form-group`, `.form-input`, `.form-select`, `.form-textarea`, `.form-label`, `.form-error`, `.form-hint`, `.has-error`, `.form-checkbox`, `.form-radio` |
| Tables | `.table-sticky`, `.table-compact`, `.table-striped`, `.sortable`, `.sort-asc`, `.sort-desc`, `.table-search`, `.table-filter-input` |
| Badges | `.badge`, `.badge-success`, `.badge-danger`, `.badge-warning`, `.badge-info`, `.badge-neutral`, `.badge-sm`, `.badge-dot`, `.badge-count` |
| Alerts | `.alert`, `.alert-error`, `.alert-success`, `.alert-warning`, `.alert-info`, `.alert-icon`, `.alert-content` |
| Toast | `.toast-container`, `.toast`, `.toast-success`, `.toast-error`, `.toast-info`, `.toast-enter`, `.toast-exit` |
| Layout | `.sidebar`, `.sidebar-item`, `.sidebar-header`, `.sidebar-nav`, `.sidebar-footer`, `.main`, `.hamburger`, `.sidebar-overlay` |
| Utilities | `.flex`, `.flex-wrap`, `.flex-between`, `.gap-sm`, `.gap-md`, `.gap-lg`, `.mt-sm`, `.mb-md`, `.mt-lg`, `.text-center`, `.text-muted`, `.fade-in` |
