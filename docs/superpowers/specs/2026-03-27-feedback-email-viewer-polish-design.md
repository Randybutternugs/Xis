# Feedback Email + Viewer Polish

## Context

The feedback system works but lacks visual distinction between categories, has no way for admins to jump from notification emails directly to entries, and the viewer has no filtering or grouping as submission volume grows. This spec addresses those gaps as the foundation layer before building task assignment, serial linking, and order workflows on top.

## Decisions Made

- **Category colors**: Severity Spectrum - Gray (General), Orange (Technical), Blue (Order), Green (Feature)
- **Deep link**: Anchor scroll to entry on existing viewer page (no new routes)
- **Organization**: Filter bar + sort controls + email-based grouping

---

## 1. Category Color System

### Color Map

| Category   | Hex       | Rationale                |
|------------|-----------|--------------------------|
| General    | `#8B8B8B` | Neutral, fades to background |
| Technical  | `#F97316` | Demands attention        |
| Order      | `#5bc0de` | Informational (existing) |
| Feature    | `#6ABD45` | Positive, brand green    |

### Where Applied

- **Admin notification emails** (`email_templates.py`): Category badge with colored background in email body, positioned above the message details alongside the reference number
- **Customer confirmation emails** (`email_templates.py`): Same colored badge showing the category they selected
- **Feedback viewer** (`feedbackview.html` + `main.css`): Category badge on each card, filter buttons in filter bar
- **Feedback reply emails** (`email_templates.py`): Category badge in header for context

### Files to Modify

- `xissite/email_templates.py` - Add `CATEGORY_COLORS` dict, update all template functions to accept/render category with color
- `xissite/static/css/main.css` - Add `.type-general`, `.type-technical`, `.type-feature` CSS classes (`.type-order` already exists, update its color)

---

## 2. Admin Notification Email Enhancements

### Layout Changes (inside `_wrap` shell)

1. **Category badge row** between green accent bar and body content: colored badge + reference number on same line
2. **Deep link button** at bottom of body: black button labeled "View in Feedback Panel", links to `{MAIN_DOMAIN}/viewdb/feedbackview#{feedback_id}`
3. Keep existing structure: black header with logo, green accent, white body, footer

### Email Template Function Changes

- `admin_notification_html(feedback, ref_number)` - Add category badge with color, add deep link button, accept `site_url` parameter
- `contact_confirmation_html(ref_number, category)` - Add category badge with color
- `feedback_reply_html(message, ref, category)` - Add category badge for context

### Deep Link URL

Format: `{MAIN_DOMAIN}/viewdb/feedbackview#{feedback_id}`

The `MAIN_DOMAIN` env var already exists. The feedback viewer template needs `id` attributes on each card for anchor targeting.

### Files to Modify

- `xissite/email_templates.py` - All template functions
- `xissite/views.py` - Pass `site_url` to `send_admin_notification()`
- `xissite/admin_api.py` - Pass `feedback.feedbacktype` to `feedback_reply_html()` for category badge

---

## 3. Feedback Viewer Overhaul

### Filter Bar

Position: Below the stats bar, above the feedback list.

**Controls:**
- **Category filters**: 4 colored toggle buttons (General, Technical, Order, Feature). Click to filter. Active = filled color, inactive = outlined/dimmed. Multiple can be active (OR logic).
- **Status filters**: Open | Resolved toggle buttons. Default: Open selected.
- **Sort**: Newest | Oldest toggle. Default: Newest.

All filtering is client-side JavaScript (no server round-trips). The full dataset is already rendered on the page; JS shows/hides cards based on active filters.

### Email Grouping

Entries from the same email address are grouped:
- **Group header**: Email address + count badge ("3 entries") + Expand/Collapse toggle
- **Default view**: Most recent entry shown, older entries collapsed as a summary row showing ID + abbreviated category badge + date
- **Expanded view**: All entries from that email shown in chronological order
- **Single entries**: No group wrapper, displayed as normal cards

Grouping logic is client-side: Jinja renders all cards with `data-email` attributes, JS groups them on page load.

### Anchor Scroll

Each feedback card gets `id="feedback-{id}"` attribute. On page load, if `window.location.hash` matches a feedback ID, scroll to it and briefly highlight (CSS animation, subtle border flash in green).

### Card Updates

- Category badge uses new colored classes
- Each card gets `data-email`, `data-type`, `data-resolved` attributes for JS filtering
- Add `id="feedback-{id}"` for anchor targeting

### Files to Modify

- `xissite/templates/feedbackview.html` - Filter bar HTML, data attributes on cards, grouping structure, inline JS for filtering/grouping/anchor behavior
- `xissite/static/css/main.css` - Filter bar styles, group header styles, category color classes, anchor highlight animation

---

## 4. Customer Confirmation Email Update

Add category badge with appropriate color to the confirmation email so customers see what category their message was filed under. Same visual language as the admin email.

### Files to Modify

- `xissite/email_templates.py` - `contact_confirmation_html()`

---

## File Summary

| File | Changes |
|------|---------|
| `xissite/email_templates.py` | Category color map, colored badges in all templates, deep link button in admin notification |
| `xissite/views.py` | Pass `site_url` to admin notification email helper |
| `xissite/admin_api.py` | Pass category to `feedback_reply_html()` |
| `xissite/templates/feedbackview.html` | Filter bar, data attributes, anchor IDs, grouping markup, client-side JS |
| `xissite/static/css/main.css` | Category color classes, filter bar styles, group styles, anchor highlight animation |

---

## Verification

1. **Category colors in emails**: Submit a test for each of the 4 categories via the contact form. Verify each admin notification and customer confirmation email shows the correct colored badge.
2. **Deep link**: Click "View in Feedback Panel" button in admin notification email. Verify it opens the feedback viewer and scrolls to the correct entry with a highlight flash.
3. **Filter bar**: On the feedback viewer, toggle each category filter and verify cards show/hide correctly. Toggle Open/Resolved. Toggle sort order.
4. **Email grouping**: Submit 2+ entries with the same email. Verify they appear grouped with count badge, expand/collapse works.
5. **Anchor highlight**: Navigate directly to `/viewdb/feedbackview#feedback-{id}` and verify scroll + highlight animation.
6. **TullOps API**: Confirm `/api/admin/feedback` endpoint still returns correct data (no model changes in this spec).
