# Restore Contact Page Overhaul & Complete Feedback Spec

## Context

A previous session implemented significant changes to the contact form, email templates, spam protection, and site-wide polish that were never committed. Additionally, the feedback spec (`docs/superpowers/specs/2026-03-27-feedback-email-viewer-polish-design.md`) called for 4 feedback categories, serial number linking, a feedback viewer overhaul, and em dash removal -- all of which remain unimplemented. The user wants all of this work restored, completed, and deployed.

**What exists but is uncommitted:** `email_templates.py`, `spam_guard.py`, contact.html anti-spam fields, views.py spam validation integration.

**What was planned but never built:** 4 feedback types in form (currently only 2), serial number input field, em dash removal across all templates, favicon pointing to new SVG, feedback viewer filter bar / grouping / anchor linking, CSS category color classes.

---

## Tasks

### Task 1: Commit existing uncommitted work

Stage and commit the completed but uncommitted files. No code changes needed -- just commit what's already there.

**Files to commit:**
- `xissite/email_templates.py` (new)
- `xissite/spam_guard.py` (new)
- `xissite/views.py` (modified -- spam guard integration, honeypot/timestamp fields)
- `xissite/templates/contact.html` (modified -- honeypot + form_loaded_at fields)
- `docs/superpowers/specs/2026-03-27-feedback-email-viewer-polish-design.md` (new)

---

### Task 2: Extend contact form to 4 feedback types + serial number

**`xissite/views.py` -- ContactForm class (~line 55):**
- Change `feedbacktype` choices from 2 to 4:
  - `('general', 'General Inquiry')`
  - `('technical', 'Technical Support')`
  - `('order', 'Order Related')`
  - `('feature', 'Feature Request')`
- Add `serialno = StringField('Serial Number', validators=[Optional(), Length(max=100)])` field

**`xissite/views.py` -- contact route (~line 108):**
- Save `form.serialno.data` to `FeedBack.serial_number`

**`xissite/templates/contact.html`:**
- Add serial number input field between Order ID and Message:
  ```
  <div class="form-group">
      <label class="contact-label">// Serial Number <span class="optional">(Optional)</span></label>
      {{ form.serialno(class="contact-input", placeholder="Found on your Tull Tower unit") }}
  </div>
  ```

---

### Task 3: Remove all em dashes site-wide

Replace every `—` with an appropriate alternative (typically ` - ` or a rewrite). 13 occurrences across 4 templates:

**`about.html`** (6 occurrences):
- Line 29: `"...accessible to everyone — from home growers..."` -> reword
- Line 34: `"...light levels — all captured..."` -> reword
- Line 59: `"...PHA biomaterial — a fully biodegradable..."` -> reword
- Line 60: `"...just sustainable — it's better..."` -> reword
- Line 69: `"Tull Tower V1 — Electronics Running"` -> `"Tull Tower V1 - Electronics Running"`
- Line 75: `"...a reality — starting with systems..."` -> reword

**`contact.html`** (1 occurrence):
- Line 29: `"...provide feedback — we're here to help."` -> reword

**`sell.html`** (5 occurrences):
- Line 82: CSS `content: "—";` -> change to `content: "-";` or `content: ">";`
- Line 147: `"...we set — no shortcuts..."` -> reword
- Lines 151-154: Feature list separators `—` -> ` - ` or reword

**`home.html`** (1 occurrence):
- Line 33: `"...into your grow — without the premium..."` -> reword

---

### Task 4: Fix favicon to use new SVG

**`xissite/templates/base.html` (line 24):**
- Change: `<link rel="icon" href="{{ url_for('static', filename='icons/tullicon.ico') }}" type="image/x-icon">`
- To: `<link rel="icon" href="{{ url_for('static', filename='icons/favicon.svg') }}" type="image/svg+xml">`

The SVG favicon already exists at `xissite/static/icons/favicon.svg` (committed).

---

### Task 5: Add CSS category color classes

**`xissite/static/css/main.css`:**

Add alongside existing `.type-order` class:
```css
.type-general { background: #8B8B8B; }
.type-technical { background: #F97316; }
.type-feature { background: #6ABD45; }
```

Verify `.type-order` uses `#5bc0de`.

---

### Task 6: Feedback viewer overhaul

**`xissite/templates/feedbackview.html`:**

Per the spec, add:
1. **Data attributes** on each feedback card: `data-email`, `data-type`, `data-resolved`, `id="feedback-{{ fb.id }}"`
2. **Filter bar** above the list:
   - 4 category toggle buttons (General, Technical, Order, Feature) with colored backgrounds
   - Status toggles: Open | Resolved (default: Open)
   - Sort: Newest | Oldest (default: Newest)
3. **Email grouping**: Cards from same email address grouped with collapsible header showing count
4. **Anchor targeting**: On page load, if URL hash matches `#feedback-{id}`, scroll to it and flash-highlight

All filtering/grouping is client-side JS (data already rendered by Jinja).

**`xissite/static/css/main.css`:**
- Filter bar styles (button row, active/inactive toggle states)
- Group header styles (email + count badge + expand/collapse)
- Anchor highlight animation (green border flash)

---

### Task 7: Wire up email integration

**`xissite/views.py` -- contact route:**
- Import email template functions from `email_templates.py`
- After saving feedback to DB, send admin notification email with category badge + deep link
- Send customer confirmation email with category badge
- Pass `site_url` (from `MAIN_DOMAIN` env var) for deep link button

**`xissite/admin_api.py` -- reply_feedback endpoint (if exists):**
- Pass `feedback.feedbacktype` to `feedback_reply_html()` for category badge

---

### Task 8: Tests, commit, deploy

- Run full test suite (`python -m pytest tests/ -v`)
- Verify contact form renders all 4 types + serial number field
- Commit all changes
- Push and deploy to App Engine

---

## Key Files

| File | Action |
|------|--------|
| `xissite/views.py` | Modify: 4 feedback types, serial number field, email integration |
| `xissite/templates/contact.html` | Modify: serial number input, em dash removal |
| `xissite/templates/about.html` | Modify: em dash removal (6 places) |
| `xissite/templates/sell.html` | Modify: em dash removal (5 places) |
| `xissite/templates/home.html` | Modify: em dash removal (1 place) |
| `xissite/templates/base.html` | Modify: favicon to SVG |
| `xissite/templates/feedbackview.html` | Modify: filter bar, data attrs, grouping, anchor IDs, inline JS |
| `xissite/static/css/main.css` | Modify: category color classes, filter bar styles, anchor highlight |
| `xissite/email_templates.py` | Commit (already complete) |
| `xissite/spam_guard.py` | Commit (already complete) |

## Verification

1. `python -m pytest tests/ -v` -- all tests pass
2. Visit `/contact` -- form shows 4 feedback types, serial number field, no em dashes
3. Submit test feedback for each category -- verify DB record and emails
4. Visit `/viewdb/feedbackview` as admin -- filter bar works, categories colored, grouping works
5. Navigate to `/viewdb/feedbackview#feedback-{id}` -- scrolls and highlights
6. Check all pages (/, /about, /sell, /contact) for zero em dashes
7. Verify favicon shows green rhombus sprout in browser tab
8. Deploy: `gcloud app deploy --quiet`
