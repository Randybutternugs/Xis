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

from admin_panel import create_app  # noqa: E402  (must follow load_dotenv)
from admin_panel.config import Config  # noqa: E402


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
    print("  NO AUTHENTICATION — keep this port on the LAN only.")
    print("=" * 60)
    app.run(host=cfg.host, port=cfg.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
