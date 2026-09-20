"""Every value the panel interpolates into innerHTML must go through esc().

The panel renders JSON from the site's admin API by string-building HTML
inside each template's inline script. User-Agent and IP strings in that
JSON are written verbatim from unauthenticated /login POSTs on the public
site, so an unescaped interpolation is stored XSS that anyone on the
internet can plant. These tests read the template source and fail on any
interpolation of an attacker-controlled field that is not wrapped in esc().
"""

import re
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"

# Fields whose value originates from a request header or body on the public
# site and is stored without sanitisation.
ATTACKER_CONTROLLED = ("user_agent", "ip_address", "username_attempted",
                       "referrer", "path", "feedbackfullfield", "feedbackmail")

# A "raw" interpolation: the field appears inside a string concatenation
# ('+ ... +') without esc( immediately wrapping it. truncate(...) alone does
# not escape.
RAW = re.compile(
    r"\+\s*(?:truncate\()?\s*\(?\s*[a-zA-Z_]+\.(" + "|".join(ATTACKER_CONTROLLED) + r")\b"
)
ESCAPED = re.compile(r"esc\(\s*(?:truncate\()?\s*\(?\s*[a-zA-Z_]+\.(" + "|".join(ATTACKER_CONTROLLED) + r")\b")


def _raw_interpolations(source):
    """Return (line_no, text) for lines that interpolate a controlled field raw."""
    hits = []
    for n, line in enumerate(source.splitlines(), 1):
        raw = RAW.findall(line)
        if not raw:
            continue
        escaped = ESCAPED.findall(line)
        # Any raw match not accounted for by an esc( wrapper on the same line
        if len(raw) > len(escaped):
            hits.append((n, line.strip()[:160]))
    return hits


@pytest.mark.parametrize("template", sorted(p.name for p in TEMPLATES.glob("site_admin_*.html")))
def test_attacker_controlled_fields_are_escaped(template):
    source = (TEMPLATES / template).read_text(encoding="utf-8")
    hits = _raw_interpolations(source)
    assert not hits, f"{template} interpolates attacker-controlled data without esc():\n" + \
        "\n".join(f"  line {n}: {t}" for n, t in hits)
