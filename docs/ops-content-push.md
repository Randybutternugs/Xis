# Ops content push: the contract TullOps codes against

TullSite stores tasks, checklists and notices that TullOps pushes, shows
each to the right employee at `/ops`, and records what they did. TullOps
polls those actions back. Auth is the existing `Authorization: Bearer
<ADMIN_API_KEY>`. Design: `docs/superpowers/specs/2026-09-20-ops-content-push-design.md`.

## Push (idempotent)

`PUT /api/admin/ops/items/<ref>` where `<ref>` is your own id (e.g. the
kanban task id). Create returns 201, update 200; either way the body is the
item as stored.

```json
{
  "kind": "checklist",              // task | checklist | notice   (required on create)
  "title": "Morning startup, Tower 7",   // required on create, <= 200 chars
  "body": "Do these before 09:00.",      // optional, <= 4000 chars, plain text
  "steps": [                              // checklist only, <= 50, keys unique
    {"key": "power", "label": "Power on pumps"},
    {"key": "ec", "label": "Log EC reading"}
  ],
  "assignee": "patrick",                  // site username, must be active; null = everyone
  "priority": "high",                     // low | normal | high | critical (default normal)
  "due_at": "2026-09-21T13:00:00Z",       // ISO 8601, optional
  "status": "open",                       // open | done (archive with DELETE)
  "reset_state": false                    // true wipes ticks/completion and reopens
}
```

Omitted fields keep their current values. A re-push never wipes what an
employee has done unless `reset_state` is true. Changing `steps` keeps
ticks for keys that still exist.

Errors: 400 with `{"error": "..."}` for bad input; 404 if the assignee
does not exist or is not active.

Broadcast (`assignee: null`) suits notices; for tasks and checklists a
single employee's complete finishes the item for everyone, so assign
those to a person.

## List and archive

- `GET /api/admin/ops/items?assignee=&kind=&status=` (status defaults to
  everything except archived; `status=all` includes archived; `limit` <= 500)
- `DELETE /api/admin/ops/items/<ref>` archives. Employees stop seeing it;
  events stay.

## Poll actions back

`GET /api/admin/ops/events?after=<cursor>&limit=200`

```json
{"events": [
   {"id": 12, "item_id": 3, "item_ref": "task:7", "username": "patrick",
    "action": "tick", "step_key": "ec", "note": null, "created_at": "2026-09-21T12:40:11+00:00"}
 ],
 "next_after": 12,
 "reset": false}
```

Actions: `complete`, `reopen` (tasks and checklists), `tick`, `untick`
(checklists, with `step_key`), `ack` (notices). Persist `next_after` and
send it as `after` next time. Poll every minute or so.

## When `reset` is true

The site's database was emptied since you last polled (it lives in
App Engine's per-instance temp storage until Cloud SQL). The response
starts from the beginning. Do this:

1. Re-push every open item with `PUT` (idempotent).
2. Set your cursor to `next_after`.

Also re-push all open items on a schedule (hourly is fine). It is a no-op
when nothing changed, and it means a wipe costs at most an hour of content.

Event ids restart from 1 after a reset and are not stable across one, so
apply events idempotently (an id you have already applied may appear again
with different content).

## Employee side, for reference

Employees see `/ops` after logging in. It reads `GET /api/ops/me` and
posts to `POST /api/ops/items/<id>/events` with `{"action": ..., "step_key": ..., "note": ...}`
using their session. TullOps never calls these.
