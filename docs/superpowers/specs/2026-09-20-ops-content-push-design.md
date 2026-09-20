# TullOps Content Push

**Date:** 2026-09-20
**Status:** Approved design
**Scope:** TullOps pushes tasks, checklists and notices to employees through TullSite; employees act on them at `/ops`; TullOps polls the results back.

---

## Context

TullOps runs on the LAN and cannot be reached from the internet. TullSite (tullhydro.com) is the internet-facing delivery channel. The March 2026 auth overhaul built the accounts and the `/ops` page for this, but the page still renders placeholder content hardcoded in the template, and no API exists for TullOps to push anything.

Principle carried over from that design: **TullOps is the authority, TullSite is the delivery channel.** TullSite never generates operational content; it stores what TullOps pushes, shows it to the right person, and records what they did with it.

Decisions taken during design:

- **Two-way.** Employees mark items done, tick checklist steps and acknowledge notices. TullSite stores that state and TullOps polls it back.
- **Per-employee targeting with broadcast.** An item names one employee or is for everyone. Admins can see every employee's items.
- **One item model with an event log.** Tasks, checklists and notices share one table; employee actions append to an event table that doubles as the polling feed.

## Data model

Two tables in `xissite/models.py`, created by `db.create_all()` at startup like every other table. No column migrations are needed because both tables are new.

### `ops_item`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | Used by employee endpoints |
| `ref` | string(200), unique, not null | TullOps's own identifier. The upsert key. |
| `kind` | string(20) | `task`, `checklist`, `notice` |
| `title` | string(200), not null | |
| `body` | text | Plain text. Rendered escaped; no markup. Max 4000 chars. |
| `steps` | text (JSON) | Checklist only. List of `{"key": str, "label": str}`. Keys unique within the item. Max 50. |
| `assignee_id` | int FK user, nullable | Null means broadcast to everyone. |
| `priority` | string(10) | `low`, `normal`, `high`, `critical`. Default `normal`. |
| `due_at` | datetime, nullable | ISO 8601 in and out. Naive UTC in SQLite; normalised with `timeutil.as_utc()` on read. |
| `status` | string(10) | `open`, `done`, `archived`. Default `open`. |
| `state` | text (JSON) | Derived from events, kept for rendering: `{"done_by", "done_at", "steps": {key: {"by", "at"}}, "acks": {username: at}}` |
| `pushed_at` | datetime | Last upsert from TullOps |
| `created_at`, `updated_at` | datetime | |

`to_dict()` includes `assignee` (username or null), parsed `steps` and `state`, and ISO timestamps.

### `ops_event`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | Monotonic. The polling cursor. |
| `item_id` | int FK ops_item | |
| `item_ref` | string(200) | Denormalised so events survive an archive and TullOps needs no lookup |
| `user_id` | int FK user | |
| `username` | string(150) | Denormalised for the same reason |
| `action` | string(20) | `complete`, `reopen`, `tick`, `untick`, `ack` |
| `step_key` | string(100), nullable | For `tick` / `untick` |
| `note` | string(500), nullable | Optional short text from the employee |
| `created_at` | datetime | |

Actions per kind:

| kind | allowed actions | effect on `state` / `status` |
|---|---|---|
| task | complete, reopen | `status` becomes `done` / `open`; `done_by`, `done_at` set / cleared |
| checklist | tick, untick, complete, reopen | `state.steps[key]` set / removed; `complete` marks `status=done` and is allowed only when every step is ticked |
| notice | ack | `state.acks[username] = at`; status unchanged |

## Admin API

Blueprint prefix `/api/admin/ops`, decorated with the existing `require_api_key` (Bearer key or admin session with `X-CSRFToken`). Lives in a new module `xissite/ops_api.py` registered from the app factory; `admin_api.py` is already 1300 lines.

### `PUT /api/admin/ops/items/<ref>`

Body:

```json
{
  "kind": "checklist",
  "title": "Morning startup, Tower 7",
  "body": "Do these before 09:00.",
  "steps": [{"key": "power", "label": "Power on pumps"}, {"key": "ec", "label": "Log EC reading"}],
  "assignee": "patrick",
  "priority": "high",
  "due_at": "2026-09-21T13:00:00Z",
  "reset_state": false
}
```

- Creates the item if `ref` is new (201), otherwise updates it (200). Response is the item's `to_dict()`.
- `kind` and `title` are required on create; on update any field may be omitted and keeps its value.
- `assignee` is a username. Must exist and have `status == 'active'`; otherwise 404. `null` means broadcast.
- Updating `steps` keeps ticks whose keys still exist and drops the rest.
- `status` may be set to `open` or `done` by TullOps. Setting `archived` is done through DELETE.
- `reset_state: true` clears `state` and sets `status` to `open`. Without it, a re-push never wipes what an employee has done.
- Validation failures are 400 via the existing `BadRequest` handler: unknown kind, priority or action; missing title; steps not a list, duplicate keys, more than 50; body over 4000 chars; unparsable `due_at`.
- Audited as `ops.push` with `{ref, kind, assignee}`.

### `GET /api/admin/ops/items`

Query: `assignee` (username), `kind`, `status` (default: everything except `archived`; `status=all` includes archived), `limit` (default 200, max 500). Returns `{"items": [...], "total": n}`, newest `pushed_at` first.

### `DELETE /api/admin/ops/items/<ref>`

Sets `status = 'archived'`. Employees no longer see it; events remain. 404 if unknown. Audited as `ops.archive`. Returns `{"ok": true}`.

### `GET /api/admin/ops/events`

Query: `after` (event id, default 0), `limit` (default 200, max 500).

Returns:

```json
{"events": [ {id, item_id, item_ref, username, action, step_key, note, created_at}, ... ],
 "next_after": 1234,
 "reset": false}
```

- Events with `id > after`, ascending.
- If `after` is greater than the newest event id (or there are no events but `after > 0`), the database has been reset since TullOps last polled. The response returns events from id 0 and sets `"reset": true`. TullOps then re-pushes all open items and resets its cursor to `next_after`.

## Employee API

Blueprint prefix `/api/ops`, in the same `ops_api.py`. Guard: logged-in session with `user_type` in `('employee', 'admin')`, plus `X-CSRFToken` on POST, mirroring the admin session path. No Bearer access: these endpoints act as a person.

### `GET /api/ops/me`

Items where `assignee_id` is the caller or null, and `status != 'archived'`. Ordered: open before done, then priority (critical first), then due date, then newest. Returns `{"items": [...]}`.

### `POST /api/ops/items/<id>/events`

Body: `{"action": "tick", "step_key": "ec", "note": "reading 1.8"}`.

- 404 if the item is archived or not visible to the caller (do not reveal existence).
- 400 if the action is not allowed for the item's kind, `step_key` is missing or unknown for tick/untick, `complete` on a checklist with unticked steps, or note over 500 chars.
- Appends an `ops_event`, updates the item's `state` / `status`, commits both in one transaction.
- Returns the updated item.

Admins may call these endpoints too, so an admin can test the page with their own account.

## The `/ops` page

`employee_ops.html` loses its hardcoded tasks, checklists and notifications. It keeps the header, the welcome line and the three section shells with `id`s. A new `xissite/static/js/ops.js` fetches `/api/ops/me` on load and every 60 seconds and renders:

- **Tasks**: title, body, priority badge, due date (relative, with the full date as a tooltip), done state. Buttons: Mark done / Reopen.
- **Checklists**: each step as a checkbox bound to tick/untick, a progress line ("2 / 6 complete"), and Mark done when all steps are ticked.
- **Notices**: title, body, priority styling, Acknowledge button; acknowledged notices move to the bottom and show when.

Rules carried over from the dashboards: quote-safe `esc()` for every value, every POST checks the response and reports the server's error in a toast, empty states say "Nothing assigned to you yet" rather than "Loading" forever, the CSRF token comes from the meta tag the page already renders for the dashboard.

The admin dashboard (`admin_dashboard.html` + `admin_dashboard.js`) gains an **Ops** section: a table of items from `GET /api/admin/ops/items?status=all` with ref, kind, title, assignee, status, progress, last activity, and an Archive button. Read-mostly; pushing stays TullOps's job.

## TullOps side (contract only)

Documented in `docs/ops-content-push.md` for whoever wires TullOps:

1. When a kanban task is assigned to a site username, `PUT /api/admin/ops/items/<task id>` with the fields above. Assign is idempotent; re-push on every change.
2. Poll `GET /api/admin/ops/events?after=<cursor>` every minute or so, apply events to the board, persist `next_after` as the cursor.
3. On `"reset": true`, re-push every open item and reset the cursor.
4. Re-push all open items on a schedule anyway (hourly is fine): the site's database is ephemeral until Cloud SQL, and a re-push is a no-op when nothing changed.

The site refuses nothing that follows this contract; the audit log records every push and archive.

## Errors, limits, security

- All validation is 400 through the existing `BadRequest` handler; nothing here can produce a 500 from user input.
- Employees never learn about items they cannot see: invisible and archived items are 404, not 403.
- Body, note, title lengths are enforced server-side; the page also truncates display.
- Events per poll are capped at 500 so a burst cannot produce an unbounded response.
- Datetimes follow the `timeutil.as_utc()` rule for every comparison.
- No new secrets, no new auth paths. TullOps uses the Bearer key it already has; employees use their session.

## Tests

`tests/test_ops_push.py`:

- Upsert creates then updates; re-push preserves ticks; `reset_state` clears them; steps update drops ticks for removed keys.
- Unknown or suspended assignee is 404; bad kind / priority / steps are 400.
- Two employees: each sees own items plus broadcast, never the other's; archived items disappear; an employee acting on an invisible item gets 404.
- Action rules per kind, including `complete` refused on a checklist with unticked steps.
- Events: ordering, cursor, `next_after`, cap, and the `reset` signal when `after` is past the newest id.
- Admin session path works with the CSRF header; Bearer path works; employee cannot call `/api/admin/ops/*`; anonymous cannot call `/api/ops/*`.
- `/ops` renders with no placeholder text and includes the script; `/admin` renders the Ops section.

`tests/test_panel_contract.py` gains `ops.js` and the Ops part of `admin_dashboard.js` as templates with `item`, `step`, `ev` variables mapped to `/api/ops/me` and `/api/admin/ops/events` shapes, seeded in the fixture.

## Out of scope

- Photo or file attachments (needs durable storage first).
- A page for it in the local admin panel (the site's `/admin` section covers admins for now).
- The TullOps implementation; this spec fixes the contract it codes against.
- Push notifications or email to employees when something is assigned.
