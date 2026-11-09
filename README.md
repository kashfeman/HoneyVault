# HoneyVault

**Intelligent Fake Data to Catch Insider Threats**

A university Information Security demonstration using synthetic decoy documents.
Stack: Python 3.12, Flask, Jinja2, HTML5, CSS3, vanilla JavaScript; SQLite later.

## Milestone 2: Frontend foundation

Includes a login UI, administrator dashboard, navy/cyan design system, reusable
layouts and components, responsive navigation, activity chart, severity indicators,
and recent-events table. All identities, documents, metrics, events and dates are
fixed fictional demo content, not live information.

**The preview is public and unprotected.** There is no authentication, session,
role enforcement, database, persistent data, download, audit collection or threat
detection. Optional login values are discarded; fields have no submission names.
Do not enter real credentials. Direct dashboard access requires no login.

## Exact local preview commands (PowerShell)

Run from the repository root with Python 3.12:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/preview_frontend.py
```

Skip environment creation if `.venv` already exists. No activation, `.env`, secret,
database setup or seeding is needed. Open http://127.0.0.1:5000/login or
http://127.0.0.1:5000/dashboard. Stop with Ctrl+C. The runner binds only to
127.0.0.1:5000 with debugging disabled; it is a development preview server.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Smoke tests cover page rendering, local assets, demo disclosures, public dashboard
access, table semantics, redirect behavior and exclusion of login inputs from
submission. Browser checks remain manual: inspect at 375px, 768px and 1440px;
tab through controls; use the skip link; open/close the mobile menu with
Enter/Escape; toggle password visibility; scroll the table; and verify navigation
and dashboard access with JavaScript disabled.

## Modular structure

- `app/__init__.py`: reserved for the future production application factory.
- `app/auth/`, `documents/`, `audit/`, `detection/`, `dashboard/`: existing backend
  package boundaries, reserved for later milestones.
- `app/templates/layouts/`: base HTML document and dashboard shell.
- `app/templates/components/`: sidebar, brand, headers, badges, demo notice,
  metrics and event-table macros.
- `app/templates/auth/login.html`: optional-input login UI preview.
- `app/templates/dashboard/index.html`: static synthetic dashboard.
- `app/static/css/main.css`: design tokens, components, responsive styles.
- `app/static/js/main.js`: menu and password visibility enhancements.
- `scripts/preview_frontend.py`: isolated preview factory, routes and fixtures.
- `tests/test_preview_frontend.py`: focused standard-library smoke tests.
- `docs/ARCHITECTURE.md`: architecture and future security assumptions.
- `requirements.txt`: Flask dependency.

All frontend assets and fonts are local/system resources, with no CDN, framework,
paid dependency or external request. Semantic landmarks, labels, textual severity,
visible focus outlines, skip navigation and a text alternative for the chart are
included. Navigation stays visible without JavaScript.

## Future backend integration

Preview routes and fixtures are separate from production packages. Future Flask
blueprints can reuse templates and supply view models after implementing real
security controls. Keep business rules and authorization out of templates. Jinja
autoescaping handles dynamic content. Private documents and SQLite belong under
ignored `instance/`; generated demo artifacts belong under ignored `generated/`.
Never put private documents in public static assets.

Planned capabilities include synthetic document generation, controlled previews
and downloads, UTC audit events, role checks, and deterministic explained alerts.
No real employee records, secrets, spyware, macros, hidden tracking or external
monitoring belong in this project. See [architecture](docs/ARCHITECTURE.md).
