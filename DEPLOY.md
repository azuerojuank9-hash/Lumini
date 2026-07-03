# Deployment

## Production Server

The app uses **Waitress** as the production WSGI server. Set `FLASK_ENV=production`:

```bash
FLASK_ENV=production python flask_app.py
```

If Waitress is not installed, it falls back to the Flask dev server with a warning.

## Configuration

All configuration is managed through environment variables (see [INSTALL.md](INSTALL.md)).

## Backup

The app automatically:
- Copies `master.db` and all `colegios_db/*.db` to `backups/` every 24h
- Uses `shutil.copy2` which preserves metadata
- Starts the first backup 30s after the app launches

## Security Notes

- `SESSION_COOKIE_HTTPONLY = True` — prevents JS access to session cookies
- `SESSION_COOKIE_SAMESITE = 'Lax'` — CSRF protection
- `SESSION_COOKIE_SECURE = True` in production — cookies only sent over HTTPS
- CSRF tokens are validated on all POST/PUT/DELETE requests
- Brute-force protection: IP-based rate limiting after failed login attempts
- Passwords are hashed with bcrypt (new registrations) or SHA256+salt (legacy)
- Registration codes are required for teacher/coordinator/rector signup

## Logs

- Written to `lumini.log` (rotated manually, currently unbounded)
- Also output to stdout
- Backups are logged at INFO level
- All errors include slug, operation, and exception message

## Requirements for Production

- PostgreSQL is not used — the app uses SQLite. For multi-instance deployments, consider migrating to a client-server database or ensure the DB files are on shared storage.
- SendGrid API key is required for email functionality (report cards, notifications)
