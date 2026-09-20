"""Entry point for the standalone TullSite admin panel.

    python admin_panel/run.py

Runs on ARCS. NOT deployed to App Engine — see .gcloudignore.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / "admin_panel.env")

from admin_panel import create_app  # noqa: E402  (admin_panel/ not importable until ROOT is on sys.path)
from admin_panel.config import Config  # noqa: E402  (admin_panel/ not importable until ROOT is on sys.path)


def main():
    try:
        cfg = Config.from_env()
    except RuntimeError as e:
        sys.exit(f"[admin-panel] {e}")

    app = create_app(cfg)
    print("=" * 60)
    print("TULL SITE ADMIN PANEL")
    print("=" * 60)
    print(f"  Upstream:  {cfg.api_url}")
    print(f"  Listening: http://{cfg.host}:{cfg.port}/site-admin")

    # Warn if not bound to loopback. ASCII only: a redirected or legacy
    # Windows console encodes stdout as cp1252 and a non-ASCII glyph here
    # raises UnicodeEncodeError before app.run() is reached.
    is_loopback = cfg.host in ("127.0.0.1", "localhost")
    if not is_loopback:
        print(f"  [WARNING] Binding to {cfg.host} - this panel is reachable")
        print("            from the network with NO AUTHENTICATION. Only use on ARCS")
        print("            behind a router. Never port-forward or expose via Tailscale.")
    else:
        print("  [OK] Loopback-only (safe). Set ADMIN_PANEL_HOST=0.0.0.0 for LAN access.")

    print("=" * 60)
    app.run(host=cfg.host, port=cfg.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
