# TullSite Admin Panel

Standalone admin UI for TullSite. Runs on ARCS, **not** on App Engine —
`.gcloudignore` excludes it so `gcloud app deploy` ships `xissite/` only.

It was extracted from the TULL fleet server, where it lived as a `/site-admin`
tab that shared nothing with fleet operations. Design:
`TullOps/docs/specs/2026-09-18-site-admin-extraction-design.md`.

## Run

    pip install -r admin_panel/requirements.txt
    cp admin_panel.env.example admin_panel.env   # then fill in ADMIN_API_KEY
    python admin_panel/run.py

Then open http://localhost:5002/site-admin

## Security

The panel has **no authentication**, matching how it behaved inside the fleet
server. Its only protection is network position. Never port-forward 5002 or
expose it through Tailscale funnel.

`ADMIN_API_KEY` must match the value in TullSite's `app.yaml`. The panel
refuses to start without it.

## How it works

Page routes render templates; everything else is a single passthrough that
forwards `/api/site-admin/<path>` to `<TULLSITE_API_URL>/api/admin/<path>`
with a Bearer header. The key stays server-side.

## Known limitation

TullSite's App Engine deployment uses SQLite in `/tmp`, which resets on every
deploy and instance restart. The visitors, security and login-attempt pages
therefore show only data since the last restart. Fix is a Cloud SQL migration,
tracked separately.

## Tests

    python -m pytest admin_panel/tests/ -v
