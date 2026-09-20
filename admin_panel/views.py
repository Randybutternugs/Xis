"""Page routes for the admin panel.

PAGES is the single source of truth: it drives both URL registration here and
the nav in base.html, so the two cannot drift.
"""

from flask import Blueprint, render_template

bp = Blueprint("views", __name__)

PAGES = (
    ("/site-admin", "dashboard", "site_admin_dashboard.html"),
    ("/site-admin/users", "users", "site_admin_users.html"),
    ("/site-admin/logins", "logins", "site_admin_logins.html"),
    ("/site-admin/customers", "customers", "site_admin_customers.html"),
    ("/site-admin/purchases", "purchases", "site_admin_purchases.html"),
    ("/site-admin/feedback", "feedback", "site_admin_feedback.html"),
    ("/site-admin/visitors", "visitors", "site_admin_visitors.html"),
    ("/site-admin/security", "security", "site_admin_security.html"),
)

NAV = tuple((rule, endpoint, endpoint.capitalize()) for rule, endpoint, _ in PAGES)


def _make_view(endpoint, template):
    def view():
        return render_template(template, nav_active=endpoint, nav=NAV)

    view.__name__ = endpoint
    return view


for _rule, _endpoint, _template in PAGES:
    bp.add_url_rule(_rule, _endpoint, _make_view(_endpoint, _template))
