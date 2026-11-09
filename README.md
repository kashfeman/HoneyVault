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

## Employee portal and document library preview

The employee experience extends the existing theme and local preview runner.
Open these public routes (no login or role checks):

| Route | Purpose |
| --- | --- |
| `/employee` | Welcome, library summary and recently updated documents |
| `/employee/documents` | Searchable employee library with category and sorting controls |
| `/employee/documents/doc-102` | Example fictional CSV preview |
| `/employee/documents/doc-101` | Example fictional TXT preview |
| `/dashboard/documents` | Library inside the administrator layout |
| `/dashboard/documents/doc-102` | Document preview inside the administrator layout |

The original `/login`, `/dashboard` and root redirect remain available. The login
page and administrator navigation link to the employee preview. Unknown document
references show a 404 page with a library recovery link.

`scripts/frontend_data.py` is the single source of six public document fixtures,
their metadata and text content. These include ordinary working resources and
plausible budget/planning examples. There is deliberately no decoy classification,
sensitivity or authorization field in these records or employee responses.
Administrator library pages use the same public fixtures, not a security inventory.

Search matches title, description, category, owner and format (case insensitive).
Apply combines search, category and sort using a GET request against local fixtures;
it works without JavaScript. Example:
`/employee/documents?q=budget&category=Finance&sort=title`.
Sort choices are `newest`, `oldest` and `title`. Reset clears the filters.
JavaScript adds a keyboard-operable card/table view switch; the default card view
works without it. No query or view preference is saved by the application.
Search terms appear in the URL and may remain in browser history; use fictional
queries only. Content is rendered as escaped plain text, including CSV.
There is no artificial loading delay or asynchronous document fetch.

Existing run commands above are unchanged. Run targeted checks:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_employee_frontend.py" -v
node --test tests/test_document_views.cjs
```

Node is optional for the dependency-free view-switch test, and is not needed to
run the preview. No npm installation is required. Python tests verify filtering,
sorting, empty states, public routes, escaped content, unknown references and
absence of classification data in rendered pages.

Manually review the employee home, library and preview at 375px, 768px and 1440px.
Check keyboard navigation, menu Escape behavior, card/table switching, horizontal
table and content scrolling, combined filters, empty results and no-JavaScript
operation. Browser visual and assistive-technology validation is still manual.
Downloads are disabled with an explicit backend-pending explanation. There is no
monitoring, alert generation or persistence; actual server-controlled document
access remains future work.

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
