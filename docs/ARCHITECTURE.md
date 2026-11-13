# HoneyVault architecture

## Scope and status

Milestones 2–5 supply frontend workspaces and an isolated local Flask preview.
Milestone 6 adds the separate application factory and persistent database schema.
Milestone 7 adds authentication, CSRF and role-protected presentation routes.
Audit recording, document operations and detection remain planned.
Build a small Flask application backed by SQLite for a controlled university
demonstration within 10–14 days. Avoid distributed services, background workers,
and machine-learning infrastructure unless a demonstrated need arises.

## Module boundaries

| Location | Planned responsibility |
| --- | --- |
| `app/__init__.py` | Application factory, configuration loading, and module registration |
| `app/auth/` | Login/logout, password verification, session identity, and reusable role checks |
| `app/documents/` | Document metadata, synthetic generation, and authorized preview/download |
| `app/audit/` | Consistent event recording for requests, outcomes, and denials |
| `app/detection/` | Deterministic event correlation, severity assignment, and explained alerts |
| `app/dashboard/` | Admin-only document, event, alert, filter, and investigation views |
| `app/templates/` | Shared layouts and future server-rendered pages |
| `app/static/` | Public CSS, JavaScript, and image assets only |
| `tests/` | Authorization, document access, audit, rule, and demo scenario tests |
| `scripts/` | Explicit database setup and repeatable synthetic demo seed/reset utilities |
| `docs/` | Architecture, security assumptions, evaluation, and developer guidance |

Use Flask blueprints for feature routes when implemented. Keep security checks
and business rules out of templates. Add shared configuration or persistence
modules under `app/` only when needed; do not create empty abstractions now.

## Planned request and detection flow

1. Resolve the authenticated account and validate the requested action.
2. Enforce role and document access policy on the server for every request,
   including direct preview/download requests and administrator endpoints.
3. Record the request and its outcome, including denied or failed access.
4. Evaluate relevant audit events using deterministic rules.
5. Expose events and explained alerts to authorized administrators.

Audit records should carry an event identifier, timezone-aware UTC timestamp,
actor reference (or anonymous status), action, document reference where known,
outcome, and reason. Correlate request/outcome records so repeated-activity rules
count attempts consistently. Avoid logging passwords, session tokens, secrets,
or document contents.

Detection should use stable document identifiers and explicit decoy metadata,
action, and repeated activity within a defined time window. Each alert should
retain its rule identifier, severity, explanation, and supporting event
references. Define thresholds, severity ordering, and duplicate-alert behavior
alongside scenario tests before implementing rules; identical inputs should
produce identical decisions. Benign documents provide comparison scenarios.

## Security assumptions and storage

- Operate only in an authorized, controlled demo with synthetic accounts and data.
  Alerts demonstrate suspicious behavior; they do not establish malicious intent.
- Use password hashing, secure session configuration, CSRF protection for state
  changes, input validation, and escaped output when those features are added.
- Enforce access on the server; hidden links and client-side role checks are
  insufficient. Apply explicit policies to admins and employees.
- Resolve documents through server-controlled metadata and a private storage
  root. Reject traversal and arbitrary filesystem paths. Never put decoys or
  benign protected files under `app/static/`.
- Preview CSV/TXT as escaped text with bounded content; serve downloads with
  controlled response headers. Do not execute document content.
- Store SQLite and private documents under ignored `instance/`; generated demo
  artifacts belong under ignored `generated/`. Store local secrets in ignored
  `.env`. The tracked `.env.example` contains placeholders only.
- SQLite audit records are suitable for a local demonstration, not tamper-proof
  evidence against a database or host administrator. External monitoring,
  hidden tracking, macros, spyware, and real confidential data are out of scope.

## Development and evaluation

Add dependencies only with implemented features. Future setup should validate
required configuration and reject placeholder secrets before enabling login.
Use temporary databases and isolated storage for automated tests. Test direct
URL access, role denials, traversal attempts, safe previews, UTC audit outcomes,
rule boundaries, repeated attempts, and benign comparison activity.

Demo utilities should create predictable synthetic fixtures and reset only the
designated demo database and storage. Document reset effects and execution
commands when those utilities exist. Keep runtime artifacts out of source
control, and keep unrelated files and Git history intact.

## Decisions to review before implementation

- The account/role and document access matrix, including employee visibility.
- Event fields, request correlation, and audit-write failure behavior.
- Rule thresholds, time windows, severity levels, and alert deduplication.
- Demo reset scope and safeguards against resetting unintended data.

## Milestone 2 preview boundary

`scripts/preview_frontend.py` owns a separate preview factory with GET routes
for `/`, `/login`, and `/dashboard`. The runner binds to `127.0.0.1:5000` with
debugging disabled. Production feature packages remain reserved for later integration;
`app/__init__.py` now owns the separate Milestone 6 backend factory.

Shared templates live under `app/templates/layouts` and `components`; feature
templates live under `auth` and `dashboard`. Local CSS supplies design tokens,
responsive layouts and focus indicators. Vanilla JavaScript enhances the mobile
menu and optional password visibility. Navigation remains visible without
JavaScript. Login inputs have no names and are never submitted.

The dashboard receives fixed fictional event fixtures from the preview runner.
Metrics, chart values, dates and severities are static illustrations. There are
no sessions, database operations, downloads, role checks, audit writes, detection
rules or background requests. Page access signifies no authorization. Future
backend routes must implement security before connecting real view models.
Preview smoke tests are rendering checks, not security tests.

Exact setup, preview, test commands and manual browser checks are in README.md.

## Employee and document presentation extension

The same isolated preview runner now serves `/employee`, `/employee/documents`,
and `/employee/documents/<document_id>`, plus corresponding document routes under
`/dashboard/documents`. Employee templates use their own layout and navigation;
administrator document pages reuse the existing administrator shell. Neither
layout enforces a role. Existing login and overview routes retain their behavior.

`scripts/frontend_data.py` owns all public document presentation records. The
records intentionally have no decoy classification, sensitivity or policy fields.
No such metadata is serialized into employee HTML, attributes, JSON or scripts.
The examples are fictional guides, schedules, budgets and planning text; they
are not private files. A future security inventory must remain separate from
employee-facing view models and enforce access through production blueprints.

GET search/category/sort parameters filter these in-memory fixtures only.
Templates render cards, a table alternative and escaped CSV/TXT preview text.
The small local `documents.js` toggles views without persistence or network calls.
No loading simulation is needed for synchronous rendering. Downloads remain
disabled and explicitly pending backend integration. No monitoring or audit
events are produced. Unknown document IDs return a recoverable 404, not an access
decision. New focused tests cover rendering, filter behavior, escaping, missing
references, classification-free responses and the view switch.

## Milestone 4 administrator presentation

`scripts/admin_preview.py` adds a read-only preview Blueprint under `/dashboard`
for `manage-documents`, `alerts` and `events`, including record-detail routes.
Existing preview routes and production package markers are preserved. This
Blueprint is a public UI demonstration, not an administrator authorization layer.

`scripts/admin_demo_data.py` is the authoritative administrator fixture source.
It enriches copies of public document records with filename, classification,
sensitivity, creation date and status. Public fixtures remain unchanged; employee
templates are never passed enriched records. Administrator assets are scoped to
the administrator layout. This avoids metadata leaks through employee markup,
attributes, scripts or embedded JSON without pretending to enforce server access.

Alert and event fixtures reference stable document IDs. Each authored alert links
to supporting events; linked events point back to the same alert and rule. Each
request/response pair shares a correlation ID. UTC timestamps are deterministic.
The overview derives counts and chart bins from this same source; request and
response events are counted separately, not as unique document interactions.
There is no rule engine or audit writer. Denials are illustrative content only.

Presentation filters select in-memory records using GET parameters. UTC date/time
bounds are validated and inclusive to minute precision; invalid ranges produce
visible errors. Inventory cards replace its wide table on smaller screens; event
and alert tables retain semantic headers and labeled horizontal scroll regions.
Detail pages include chronological supporting-event timelines and recovery links.

Native dialogs demonstrate required fields, validation, cancellation and a text
confirmation without file generation or record changes. Review toggles affect only
the current DOM and reset on reload/navigation. Snapshot filters are unaffected
by temporary review changes. No browser/server persistence is used. Audit history
has no edit/delete controls. Future production work must separately implement
authentication, roles, CSRF controls, storage, secure file handling, rule evaluation
and audit integrity before connecting these views to backend services.

## Milestone 5 presentation quality

Recent dashboard events sort by timestamp, independent of fixture tuple order.
The existing shared snapshot still drives document/event/alert counts. Public
records remain free of administrator classifications and sensitivity fields.

The app-level 404 handler selects the current workspace layout and a safe home
link, without showing the requested path or internal exception details. It does
not change existing record-specific recovery routes or imply authorization.
The stale-process/occupied-port guard and local-only startup behavior are retained.

Mobile disclosure navigation manages keyboard focus; dialogs explicitly wrap
Tab/Shift+Tab and use native modal/cancel behavior. Temporary review state resets
on persisted `pageshow` as well as normal reloads. All state remains in the current
DOM; there are no browser storage or backend writes. Audit records stay read-only.

Optional `tests/browser_frontend.cjs` drives an installed headless Edge via its
loopback debugging interface using Node's built-in WebSocket/fetch APIs. It checks
responsive layout and actual native-browser interactions without third-party
packages. Temporary profiles are isolated and removed, and optional small
screenshots stay under ignored `generated/`. Unit tests remain lightweight;
assistive-technology and cross-engine validation remain manual.


## Milestone 6 implemented persistence

`create_app()` initializes the shared Flask-SQLAlchemy extension without creating
tables or seeding records. Development configuration reads `SECRET_KEY` and
`DATABASE_PATH` from the process environment; testing configuration can use
in-memory SQLite or an explicit temporary URI. Milestone 6 originally exposed JSON `/health` and CLI `init-db`. Milestone 7
adds authentication, public static styling assets and protected presentation routes.
The separate public preview remains on port 5000; `run.py` serves the backend on
127.0.0.1:5001 with debug/reload disabled. Health is process liveness only.

| Table | Fields and constraints |
| --- | --- |
| `user` | Integer PK; unique required username; required password_hash; role constrained to admin/employee (default employee); required active flag; created_at/updated_at UTC timestamps |
| `document` | UUID string PK; required filename, category, format and unique storage_reference; is_decoy flag; sensitivity constrained to public/internal/confidential/restricted; status active/archived |
| `detection_rule` | Stable string identifier PK; required name, JSON parameters, severity low/medium/high/critical and enabled flag |
| `audit_event` | UUID string PK; required occurred_at UTC timestamp, action and outcome; nullable actor_id, document_id and triggered rule_id FKs |
| `alert` | UUID string PK; required severity, rule_id FK, explanation, created_at UTC and review_state unreviewed/reviewed; nullable actor_id and document_id FKs |
| `alert_events` | Composite PK (alert_id, event_id), both required FKs; connects alerts with supporting audit events |

Users, documents and rules each have one-to-many relationships with audit events
and alerts. Alerts and audit events have a many-to-many supporting relationship.
Nullable event actors allow future anonymous attempts; nullable documents/rules
allow events without those references. Alerts require a rule but can describe
activity without a known actor/document. Reverse ORM relationships are available.
Foreign keys reject nonexistent references; no automatic delete cascades are
configured. Deletion and retention policies are future service-layer work.
No public API serializes any of these models.

Indexes cover event timestamps, alert creation/review state, all actor/document/
rule foreign keys, document category/status, and reverse supporting-event lookup.
PKs and unique fields receive SQLite's uniqueness indexes. ORM inserts supply
UUIDs and UTC defaults; user updated_at changes on ORM updates. These timestamps
are application-maintained, not database triggers or tamper-proof evidence.
`UTCDateTime` rejects naive timestamps, normalizes aware inputs to UTC for SQLite
storage, and restores timezone information on retrieval.

Werkzeug hashes passwords with its default salted scrypt algorithm through
`User.set_password`; `check_password` verifies hashes. Milestone 7 reuses these helpers for credential verification and CLI account creation. JSON parameters are stored only;
no evaluation or parameter validation engine exists. Reassign parameter dictionaries
to persist edits rather than mutating nested JSON in place.
`storage_reference` is private metadata, not a trusted filesystem path: future
file services must enforce the private root and reject traversal before use.

SQLite foreign-key enforcement is enabled for each SQLAlchemy SQLite connection
using a fixed PRAGMA. All record operations use SQLAlchemy. The default database
is under ignored `instance/`. `init-db` creates missing tables non-destructively,
is repeatable, and creates no users or business data. It is not a schema migration
system. No destructive reset command is provided. The existing `.gitignore`
already excludes local secrets, SQLite files and instance storage.

Milestone 7 supplies session authentication, CSRF and explicit employee/admin
policies for presentation routes. Future document services must add record-level
access policy before passing private records into shared templates. Public preview fixtures must remain
separate from real inventory, audit events and classifications.


## Milestone 7 authentication and account access

`app/auth/` initializes Flask-Login, Flask-WTF CSRFProtect and Flask-Limiter.
`UserMixin` adds the Flask-Login interface to the existing User model without
changing its database columns. `login_required` is provided by Flask-Login;
`role_required` wraps it and enforces exact database role equality. Inactive or
missing users fail session loading. Admins are intentionally denied employee
routes and employees are denied all administrator routes. Client parameters never
select the authenticated role or account.

The additional `auth_session` table has a 64-character SHA-256 token digest PK,
required indexed user_id FK and required indexed UTC expires_at. The random
32-byte session token is carried inside Flask's signed cookie; only the digest
is stored server-side. Login clears pre-authentication state, rotates CSRF state,
and establishes a new database-backed authentication record. Logout is POST-only,
validates CSRF, deletes the record, and clears browser state. This makes signed
cookie replay ineffective after logout. Records expire after an absolute
30-minute lifetime and are checked on every authenticated request. Opportunistic
cleanup removes expired records on successful login. No remember-me is enabled.
Concurrent browser sessions are allowed; logout revokes the current session only.

A private signing key of at least 32 characters is required for auth/workspace
requests; missing or short keys yield 503. CLI init/account creation and health
remain usable without a key. The key is never generated at application startup.
Development HTTP requires explicit HONEYVAULT_ENV=development; other values use
Secure cookies. HttpOnly, SameSite=Lax, no-store pages, frame denial, no-referrer
and nosniff headers supplement server-side checks. HSTS is sent for HTTPS requests.
The application does not automatically trust forwarded headers.

Login uses generic errors and a random dummy hash for unknown accounts. POST
attempts are limited per source IP to 10/minute and 50/hour using process-local
memory, which is a documented local-demo limitation. No persistent failed-login
or audit records are produced. Request bodies and password length are bounded.
Flask-WTF protects state-changing routes globally. Fixed role landing pages ignore
all next parameters, avoiding redirect parsing ambiguities and URL data leakage.

`create-user` is local CLI only, permits explicit employee/admin roles, prompts for
a hidden confirmed password, hashes it and rejects duplicates. No public account
registration, credential provisioning seed, account recovery, password-change UI,
MFA or persistent lockout is implemented. CLI creation requires prior init-db.

`app/workspaces.py` reuses sanitized public document fixtures and the existing
administrator preview blueprint. It wraps each administrator view in this app's
view registry without mutating the shared blueprint or public preview factory.
The frontend preview still runs independently on port 5000 with no authentication
or database requirement. Conditional template mode retains the preview markup
and disclosures while the real app supplies login, logout and accurate notices.
Employee views never receive administrator fixtures, classification or sensitivity.
No real document content, alert processing or administrator write operations are
connected. Existing browser-only simulations remain demonstrations.

Tests cover real CSRF, session replay after logout, expiry, inactive users,
password failure, fixed redirects, source-IP throttling, CLI account safety,
role changes and every administrator route group, plus prior database/frontend
contracts. Windows-compatible temporary databases live under ignored generated/
pytest-temp; pytest owns and clears that dedicated directory. See README for
exact local setup and test commands.


Implementation references: [Flask-Login](https://flask-login.readthedocs.io/en/latest/),
[Flask-WTF CSRF](https://flask-wtf.readthedocs.io/en/1.2.x/csrf/) and
[Flask-Limiter](https://flask-limiter.readthedocs.io/en/stable/).

## Milestone 8 employee document service

The port 5001 employee routes now use `app/documents/service.py` and SQLAlchemy
`Document` rows rather than `scripts/frontend_data.py`. Port 5000 and administrator
presentation routes retain those fixtures. No database columns/tables changed.

Request flow: Milestone 7 session/active account check -> exact employee role ->
shared document eligibility query -> UUID lookup -> bounded private file read ->
allowlisted presentation dictionary or attachment bytes. Employee home and library
use the same eligibility query for records, categories and counts. Search uses
bound SQLAlchemy expressions with escaped LIKE metacharacters. Sort expressions
come from a fixed allowlist with filename and ID tie breakers. No timestamp sort
is fabricated from the timestamp-free model.

Eligibility requires active status, public/internal sensitivity and CSV/TXT format.
All eligible employees share access; no per-user/team grant table exists. Decoy
status is irrelevant to permission checks. The ORM object is retained only inside
the service/route; templates receive ID, filename as title, category, format, and
escaped content for preview. No classification, paths, rules or administrator
metadata are serialized. Ineligible/missing/invalid records have generic 404s.

`instance/documents` is the default private storage root, configurable through
`DOCUMENT_STORAGE_ROOT`. It cannot overlap static storage. Only flat ASCII
storage filenames ending in the record's CSV/TXT format are accepted; document
filenames must also have matching extensions. Absolute paths, traversal, Windows
separators/drive paths/alternate streams, symlink files, nonregular files, invalid
UTF-8, NULs and files over `DOCUMENT_MAX_BYTES` (default 1 MiB) are rejected. Reads
are bounded even if a file grows. Operators must keep the root and database
trusted and private: checks are not an atomic defense against concurrent hostile
local filesystem modification, hard links or a compromised host.

Preview content is ordinary escaped Jinja text inside `pre`. Download reads the
same validated bytes and uses an in-memory attachment with a Werkzeug sanitized
filename, explicit text type, no conditional validators and no-store/nosniff.
There is no raw-path HTTP endpoint or document file beneath static. Existing
application-wide response headers and revocable authentication remain in force.

`app/documents/demo.py` registers the explicit `seed-demo-documents` CLI. Four
fictional fixtures (two decoys) use stable UUIDv5 identifiers and exclusive file
creation. Existing rows/references/files are skipped, not replaced or reset.
The command requires initialized tables and a trusted local operator. A database
failure after file creation can leave an orphan; subsequent seeds preserve that
file rather than overwrite it. There is no file repair or administration workflow.

Later audit integration belongs at the lookup/policy/read boundary for preview
and download, with actor/document/action/outcome/UTC context, including denied
attempts. It must not capture raw filesystem references, file contents, search
text, credentials or session tokens. Detection can join events with private decoy
metadata server-side. Neither audit capture nor detection/alerts is implemented.
Tests in `tests/test_documents.py` cover these contracts using temporary SQLite
and private storage, alongside the existing authentication and frontend suites.
Exact setup and verification commands are in the Milestone 8 README section;
older milestone sections describe their historical implementation boundaries.
