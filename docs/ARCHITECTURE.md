# HoneyVault architecture

## Scope and status

Milestone 1 establishes structure only. All behavior described below is planned.
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

No routes, models, configuration loader, frontend pages, or engine are supplied
in this milestone.
