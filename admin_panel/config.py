"""Configuration for the standalone TullSite admin panel.

Read from admin_panel.env (gitignored) via python-dotenv. See
admin_panel.env.example for the template.
"""

import os
from dataclasses import dataclass

DEFAULT_API_URL = "https://xissite-355821.ue.r.appspot.com"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5002


@dataclass(frozen=True)
class Config:
    api_url: str
    api_key: str
    host: str
    port: int

    @classmethod
    def from_env(cls):
        """Build config from the environment.

        Raises RuntimeError when ADMIN_API_KEY is missing. This is deliberate:
        the fleet-server version of this panel failed silently for months
        because its API key was never configured, so every page rendered fine
        and every request 401'd. Refusing to start is the louder, better
        failure.
        """
        api_key = os.environ.get("ADMIN_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "ADMIN_API_KEY is not set. The admin panel cannot reach the "
                "TullSite admin API without it. Copy the value from TullSite's "
                "app.yaml into admin_panel.env."
            )
        return cls(
            api_url=os.environ.get("TULLSITE_API_URL", DEFAULT_API_URL).rstrip("/"),
            api_key=api_key,
            host=os.environ.get("ADMIN_PANEL_HOST", DEFAULT_HOST),
            port=int(os.environ.get("ADMIN_PANEL_PORT", DEFAULT_PORT)),
        )
