# HoneyVault

**Intelligent Fake Data to Catch Insider Threats**

A university Information Security demonstration using synthetic decoy documents.
Stack: Python 3.12, Flask, Jinja2, HTML5, CSS3, vanilla JavaScript; SQLite and Flask-SQLAlchemy.

## Current status: Milestone 7 authentication and role access

Includes a login UI, administrator dashboard, navy/cyan design system, reusable
layouts and components, responsive navigation, activity chart, severity indicators,
and recent-events table. All identities, documents, metrics, events and dates are
fixed fictional demo content, not live information.

**The port 5000 preview is public and unprotected.** It has no authentication,
sessions, role enforcement, database connection, downloads, audit collection or
threat detection. Its optional login values are discarded; never enter account
passwords there. The separate port 5001 application now provides real
authentication and role checks with fictional workspace content.

## Milestone 7: authenticated local application

Port **5001** runs real login and role checks. Port **5000** remains the separate,
public, unsecured frontend demonstration; never enter account passwords there.
The authenticated app reuses the design but shows accurate authentication notices.
Workspace documents, metrics, alerts and events are still synthetic fixtures.
No document CRUD, monitoring, rule evaluation or persistent review is implemented.

From the repository root in PowerShell (Python 3.12):

```powershell
# Only create .venv if it does not already exist.
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:HONEYVAULT_ENV = "development"
# Generate a private session-signing key in this terminal; this prints no secret.
$env:SECRET_KEY = & .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
.\.venv\Scripts\python.exe -m flask --app app:create_app init-db
.\.venv\Scripts\python.exe -m flask --app app:create_app create-user --username demo.employee --role employee
.\.venv\Scripts\python.exe -m flask --app app:create_app create-user --username demo.admin --role admin
.\.venv\Scripts\python.exe run.py
```

The account commands prompt for hidden passwords twice. Choose unique local demo
passwords of 12-1024 characters; no password CLI option, seed credentials or public
registration exists. Usernames allow 1-80 letters, digits, dots, underscores and
hyphens. Duplicate usernames are rejected without changing existing accounts.
Use only fictional account identities. No accounts are automatically created.
`init-db` also adds the new `auth_session` table to an existing Milestone 6 database
without changing prior tables or records.

Open http://127.0.0.1:5001/login. Employees land at `/employee`; administrators
land at `/dashboard`. Anonymous workspace requests redirect to `/login` without
copying the original query into a URL. The `next` parameter is deliberately
ignored. Authenticated users with the wrong role receive a safe 403; admins do
not inherit employee workspace access. Roles and active status are reloaded from
the database on every request. No username, password or session token is added
to redirect URLs. Use fictional searches because library GET filters appear in
browser history and development access logs.

| Route | Access and behavior |
| --- | --- |
| `GET /health` | Public process liveness |
| `GET/POST /login` | Real login form; POST requires CSRF |
| `POST /logout` | Authenticated, CSRF-protected logout; GET is rejected |
| `GET /` | Redirect to login or the account's role landing page |
| `/employee`, `/employee/documents`, `/employee/documents/<id>` | Employees only; sanitized fictional data and escaped content |
| `/dashboard`, `/dashboard/documents`, `/dashboard/documents/<id>` | Administrators only; fictional data |
| `/dashboard/manage-documents[/<id>]`, `/dashboard/alerts[/<id>]`, `/dashboard/events[/<id>]` | Administrators only; existing presentation demonstrations, no backend operations |

Session cookies contain a signed user ID and opaque random authentication token,
not passwords, hashes or private profile data. A token digest and absolute expiry
are stored in SQLite. Authentication clears prior browser state and creates a new
token; logout deletes its database record and clears the cookie. Replaying the
old cookie after logout fails. Sessions expire after 30 minutes without sliding
renewal or remember-me cookies. Expired database session rows are pruned on the
next successful login. Deactivation blocks both new logins and existing sessions.
Changing the signing key invalidates existing browser cookies.

HttpOnly and SameSite=Lax are always set. Secure cookies are the default;
`HONEYVAULT_ENV=development` explicitly disables Secure for loopback HTTP on port
5001. An HTTPS deployment must omit that override or set `HONEYVAULT_ENV=production`
and supply a durable private random signing key. `.env` is not auto-loaded; do
not commit it. Missing/short keys disable auth/workspace routes with 503 while
health and CLI setup remain available. Security responses avoid internal details;
non-static responses use `Cache-Control: no-store`.

Login POST requests are limited to 10/minute and 50/hour per source IP, including
successful attempts. Invalid usernames, passwords and inactive accounts receive
the same message. Unknown usernames take a dummy password-hash verification path.
The limiter ignores untrusted forwarding headers. Its in-memory counters are
appropriate for this single-process local demonstration: restarts clear them,
multiple workers do not share counters, and distributed attack protection is not
provided. A deployment would need shared limiter storage and an explicit trusted
proxy configuration. Do not expose the Flask development server to the Internet.

Verification from the root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/test_admin_interactions.cjs tests/test_document_views.cjs tests/test_navigation.cjs
```

`pytest.ini` disables the problematic cache and places temporary databases under
ignored `generated/pytest-temp` for Windows. Pytest clears that directory between
runs: reserve it exclusively for tests and do not run simultaneous test processes
using the same base directory. Tests use isolated databases and random ephemeral
passwords and secrets. They never create demo accounts in the working database.

Milestone 7 verification on Python 3.12.10: **61 tests and 35 subtests passed**
with pytest; the standalone frontend unittest suite passed **21 tests**; Node
interaction tests passed **5 tests**. `init-db` succeeded against the existing
local database, `pip check` found no broken requirements, and `git diff --check`
passed. No working-database accounts were created. Browser visual and
assistive-technology checks were not rerun.

## Milestone 6: preserved database foundation

The backend is separate from the public preview. `GET /health` returns
`{"status": "ok"}` as process liveness, not database readiness. Milestone 7 adds
authenticated workspace routes described above; the database foundation remains.

Run these commands from the repository root in PowerShell with Python 3.12:

```powershell
# Create the environment only if it does not already exist.
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app app:create_app init-db
.\.venv\Scripts\python.exe run.py
```

Open http://127.0.0.1:5001/health. The runner binds to loopback with debugging
and reloading disabled. Run the unchanged preview in a separate terminal using
`.\.venv\Scripts\python.exe scripts/preview_frontend.py` on port 5000.
Neither service requires the other to run.

The default database is `instance/honeyvault.sqlite3`, resolved relative to the
repository root. `init-db` creates missing parent directories and tables without
dropping tables, deleting records, creating accounts or inserting demo data.
It is safe to repeat. It does not migrate existing table definitions: future
schema changes will require an explicit migration strategy. Application creation
and `/health` do not initialize or connect to the database.

Configuration is read from process environment variables on each factory call.
`.env.example` documents the contract; `.env` is ignored and **not automatically
loaded**. Optional overrides before initialization and startup:

```powershell
$env:DATABASE_PATH = "instance/local-demo.sqlite3"
# Supply SECRET_KEY as shown in the Milestone 7 setup before signing in.
```

`SECRET_KEY` defaults to unset; authentication fails closed with HTTP 503 unless
a private value of at least 32 characters is supplied. See the setup above.
Cookie defaults are Secure, HttpOnly and SameSite=Lax; local HTTP requires the
explicit development environment setting. Never commit secrets or database files.
Keep database overrides under ignored `instance/` (or outside the repository).
`create_app("testing")` uses an isolated in-memory SQLite configuration; tests
instead override the URI with temporary files to verify persistence as well.

Implemented models: `User`, `Document`, `AuditEvent`, `DetectionRule`, `Alert`,
and the `alert_events` supporting association. See the schema in
[architecture](docs/ARCHITECTURE.md). Password helpers use Werkzeug's salted
password hashing; no plaintext password field exists. SQLite foreign keys are
enabled on each connection. Timestamp inputs must be timezone-aware and are
normalized to UTC; reloaded timestamps retain UTC timezone information.

Run all Python tests (including the previous frontend unittest cases) and the
existing JavaScript interaction tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/test_admin_interactions.cjs tests/test_document_views.cjs tests/test_navigation.cjs
```

Milestone 6 verification on Python 3.12.10: the final run of
`python -m pytest -q -p no:cacheprovider` passed 45 tests and 35 subtests;
the existing unittest suite passed 21 tests; all five Node interaction tests
passed. Cache was disabled after the initial run reported a local cache-directory
permission warning. The root-level `init-db` command succeeded twice, and the
created SQLite file was confirmed ignored by Git. Browser visual checks were
not rerun for this backend-only milestone.

Milestone 7 adds login/logout, sessions, role checks and CSRF protection.
Real document storage/access operations, generation, audit recording, alert
generation and rule evaluation remain unimplemented. The public preview remains fictional and
unprotected; do not expose private records through it.

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

If new routes return 404 while tests pass, stop the old preview in its terminal
with `Ctrl+C` and run the exact command above again. Debug/reload is disabled:
an existing process retains its original Python routes even when templates have
changed. The runner prints its absolute source path, PID and registered admin
routes at startup. It refuses an occupied port instead of allowing a second
Windows preview to reuse port 5000. Use the URL in that fresh terminal; changing
the files alone does not update an already-running server.

Startup regression checks:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_preview_startup.py" -v
```

- `app/__init__.py`: separate backend application factory and `init-db` command.
- `app/config.py`, `extensions.py`, `models.py`: backend configuration and persistence.
- `run.py`: local backend runner on port 5001.
- `app/auth/`, `documents/`, `audit/`, `detection/`, `dashboard/`: existing backend
  package boundaries; auth is implemented, the remaining services are future work.
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
- `requirements.txt`: Flask, Flask-SQLAlchemy and pytest dependencies.

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
Administrator library pages use the same public fixtures. The separate Milestone 4
document-management page enriches them with administrator-only presentation labels.

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

## Milestone 4: Administrator operations preview

These additions preserve the login, overview, employee portal and public library.
All routes are public demonstrations, with no access protection:

| Route | Preview |
| --- | --- |
| `/dashboard/manage-documents` | Administrator inventory, search, category/format filters, responsive cards and create-decoy dialog |
| `/dashboard/manage-documents/doc-102` | Administrator metadata, escaped content and manage simulation |
| `/dashboard/alerts` | Severity/review summaries, search, severity/status/action and UTC time filters |
| `/dashboard/alerts/ALERT-001` | Authored explanation, temporary review and supporting event timeline |
| `/dashboard/events` | Search, actor/action/outcome and UTC time filters; immutable illustrative history |
| `/dashboard/events/DEMO-008` | Request/response timeline, correlation ID and linked alert |

Use the same runner and environment commands above. Exact launch commands from
the repository root (create `.venv` first if absent):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/preview_frontend.py
```

Open `http://127.0.0.1:5000/dashboard/manage-documents`,
`http://127.0.0.1:5000/dashboard/alerts`, or
`http://127.0.0.1:5000/dashboard/events`.

`scripts/admin_demo_data.py` is the single source for administrator label overlays,
three authored alerts and eight linked event fixtures. It references the six
public documents from `scripts/frontend_data.py`, without adding classification
fields to those public records. Admin-only assets are loaded by the administrator
layout; employee pages receive neither administrator records nor administrator
scripts. This presentation separation is not authorization: admin URLs are public.
`scripts/admin_preview.py` groups new read-only preview routes in a Blueprint.

Overview counts, severity distribution, recent events and activity bars derive
from the same fixtures. Event totals count requests and responses separately;
the chart groups them into four-hour UTC bins. All timestamps use the fixed
09 November 2026 snapshot. There is no live feed, rule evaluation or logging.
Denied/successful events illustrate outcomes; this preview does not enforce them.
Alerts do not establish malicious intent.

Document forms use native dialog keyboard/focus behavior, required fields and
name validation. Simulated creation/management shows an escaped text confirmation;
it never adds inventory rows, changes metadata or generates files. Cancel/Escape
discards choices. Mark-as-reviewed changes the current page and its reviewed
counter only. Refresh or navigation restores the authored snapshot. Filters use
the fixed snapshot status even after a temporary review. No state is stored in
cookies, local storage, sessions or a database. Queries appear in URLs/browser
history, so use fictional text only.

UTC time filters include both endpoints to minute precision. For example:
`/dashboard/events?outcome=Denied&start=2026-11-09T10:00&end=2026-11-09T15:00`.
Invalid or reversed time bounds show validation messages. Unknown record IDs
show a recovery page. Filtering and detail links work without JavaScript;
management dialogs and temporary review controls require JavaScript and otherwise
remain hidden with an explanatory notice.

Focused validation commands (no new dependencies):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_admin_frontend.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_preview_frontend.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_employee_frontend.py" -v
node --test tests/test_admin_interactions.cjs tests/test_document_views.cjs
node --check app/static/js/admin.js
```

Node is only needed for optional dependency-free interaction tests. Python checks
cover routes, filters/time bounds, escaping, IDs/count consistency, employee data
separation, recovery pages, linked pages/anchors and rejection of POST requests.
JavaScript tests check temporary review, dialog validation/confirmation and focus
handling using small test doubles; they do not replace native-browser testing.

Manual review remains: desktop/tablet/mobile layouts at 1440/768/375px, native
dialog focus trapping and Escape/cancel, native validation messages, keyboard and
screen-reader operation, horizontal history-table scrolling, filter combinations,
and reset-on-refresh behavior. There are no uploads, downloads, persistence,
real authentication, monitoring, rule evaluation or real audit records.

## Milestone 5: Frontend polish and functional QA

The shared snapshot remains six documents (four sample documents and two decoys),
three alerts (one per severity, one reviewed), eight events and three fictional
actors. The overview, administrator lists and employee library agree. Recent
events now sort by UTC timestamp instead of relying on fixture declaration order.

Keyboard navigation now moves focus into an opened mobile menu and returns it
with Escape. Resizing into the mobile layout preserves a visible focus target.
Document dialogs explicitly wrap Tab/Shift+Tab, retain native modal behavior and
restore focus after cancellation or confirmation. Review simulations also reset
when a browser restores a cached history page; no state is persisted.

Responsive polish adds a scrollable desktop sidebar, clearer two-column mobile
navigation, resilient header/card wrapping and visible table-region focus.
Breadcrumbs use labeled navigation, document detail navigation announces the
current section, and card/table toggles identify the content they control.
Unknown page URLs now show a branded 404 recovery view in the matching workspace,
without echoing exception details or the requested URL. Existing unknown-document
and administrator-record recovery pages remain unchanged.

Lightweight checks:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/test_admin_interactions.cjs tests/test_document_views.cjs tests/test_navigation.cjs
```

Optional real-browser regression checks use installed Microsoft Edge and Node
22+ only, without npm packages or browser downloads. Start the preview using the
normal command first, then run in another terminal:

```powershell
node tests/browser_frontend.cjs
```

The browser test visits eleven pages at 1440px, 768px and 375px; measures page-wide
overflow; verifies the inventory table/card fallback; checks mobile keyboard
navigation, modal focus/validation, temporary review/reset, and library view
switching; and reports uncaught browser exceptions. History restoration reset is
tested by dispatching a persisted `pageshow` event, not by assuming that the
browser enabled its back/forward cache for a particular navigation.
Use `--screenshots` to save two small images under ignored
`generated/frontend-qa/`. The temporary Edge profile is removed after the test.
Set `HONEYVAULT_EDGE` to an installed Edge executable if it is at a different path.

Milestone 5 verification: 21 Python checks and five Node interaction tests passed.
The exact preview startup command was used for live HTTP verification: 37 valid
page URLs returned 200 and three unknown-page recovery URLs returned 404.
Real-Edge responsive and interaction checks were also run; browser script output
provides the exact per-run pass count. Screen-reader testing and browser engines
other than Edge remain manual. This work adds no real backend security behavior.

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
