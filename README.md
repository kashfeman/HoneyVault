# HoneyVault
HoneyVault: Intelligent Fake Data to Catch Insider Threats 

HoneyVault is a university Information Security project demonstrating how synthetic
decoy documents can help identify suspicious activity by simulated employees.
The development target is 10–14 days using Python 3.12, Flask, SQLite, HTML5,
CSS3, and vanilla JavaScript.

## Current milestone

Milestone 1 provides the package structure and development documentation only.
There is no runnable application, database schema, authentication, frontend,
document generator, or detection engine yet. No dependencies are required for
this milestone.

## Planned capabilities

- Admin and simulated employee accounts with server-side role authorization.
- Synthetic salary sheets, customer lists, and internal reports in CSV and TXT,
  alongside benign demonstration documents.
- Controlled server-side document preview and download.
- UTC audit events for access requests, outcomes, and authorization denials.
- Deterministic severity rules based on document identity, action, and repeated
  activity, with explanations for alerts.
- An admin dashboard for documents, events, alerts, filters, and investigation.
- Repeatable demo reset and security evaluation scenarios.

All data will be synthetic. The project excludes spyware, macros, hidden
trackers, and external monitoring. Detection will use explainable rules rather
than a trained machine-learning model.

## Repository layout

```text
app/
  __init__.py
  auth/                # Authentication and authorization
  documents/           # Document handling and synthetic decoy generation
  audit/               # Structured security events
  detection/           # Correlation rules and alerts
  dashboard/           # Administrator views
  templates/
    layouts/           # Shared template layouts
  static/
    css/
    js/
    images/
tests/
scripts/
docs/
  ARCHITECTURE.md
.env.example
```

Python packages contain only package markers. Empty resource directories use
`.gitkeep` placeholders so Git retains the structure.

## Planned local setup

1. Use Python 3.12 and create a local environment with `python -m venv .venv`
   if one does not already exist. On PowerShell, activate it with
   `.\.venv\Scripts\Activate.ps1`.
2. Copy `.env.example` to `.env` and replace the secret placeholder with a unique
   local value before authentication is implemented. Never commit that value.
3. In a later milestone, install dependencies from the dependency manifest
   added with the application implementation, then follow its database setup,
   demo seed/reset, and startup instructions.

Environment loading and configuration validation are planned, not implemented.
There is currently no install, database initialization, or startup command.
Keep runtime databases and private document storage under ignored `instance/`;
keep generated demo artifacts under ignored `generated/`. The existing ignore
rules also exclude virtual environments, local environment files, and logs.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for module boundaries, security
assumptions, and guidance for subsequent milestones.
