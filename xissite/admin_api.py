"""
TullSite Admin API
==================
Secure REST API for remote administration via TullOps.
All endpoints (except /health) require Bearer token authentication
via the ADMIN_API_KEY environment variable.

Endpoints cover: user CRUD, login attempt monitoring, customer/purchase/
feedback management, visitor analytics, security alerts, and CSV export.
"""

import os
import csv
import io
import functools
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, Response
from sqlalchemy.sql import func
from sqlalchemy import desc
from werkzeug.security import generate_password_hash

from . import db
from .models import (User, Customer, Purchase_info, FeedBack, LoginAttempt,
                     SiteVisit, BannedIP, GeoIPCache, AdminAuditLog)
from .email_templates import feedback_reply_html


admin_api = Blueprint('admin_api', __name__, url_prefix='/api/admin')


# ============================================================================
# AUDIT LOGGING HELPER
# ============================================================================

def _audit(action, target_type=None, target_id=None, details=None):
    """Record an admin API action in the audit log."""
    try:
        import json as _json
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()
        entry = AdminAuditLog(
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id else None,
            details=_json.dumps(details) if details else None,
            admin_ip=client_ip,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()


# ============================================================================
# AUTH DECORATOR
# ============================================================================

def require_api_key(f):
    """Verify Bearer token matches ADMIN_API_KEY env var."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        api_key = os.environ.get('ADMIN_API_KEY')
        if not api_key:
            return jsonify(error='Admin API not configured'), 503
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer ') or auth_header[7:] != api_key:
            return jsonify(error='Unauthorized'), 401
        return f(*args, **kwargs)
    return decorated


# ============================================================================
# HEALTH
# ============================================================================

@admin_api.route('/health')
def health():
    """Public health check -- no auth required."""
    return jsonify(status='ok', timestamp=datetime.now(timezone.utc).isoformat())


# ============================================================================
# DASHBOARD STATS
# ============================================================================

@admin_api.route('/stats')
@require_api_key
def stats():
    """Aggregated dashboard summary."""
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)

    user_counts = {
        'total': User.query.filter(User.status != 'deleted').count(),
        'active': User.query.filter_by(status='active').count(),
        'suspended': User.query.filter_by(status='suspended').count(),
    }

    customer_count = Customer.query.count()
    purchase_count = Purchase_info.query.count()
    paid_count = Purchase_info.query.filter_by(pay_status='paid').count()

    feedback_total = FeedBack.query.count()
    feedback_unresolved = FeedBack.query.filter(
        (FeedBack.resolved == False) | (FeedBack.resolved == None)
    ).count()

    login_24h_total = LoginAttempt.query.filter(LoginAttempt.timestamp >= day_ago).count()
    login_24h_failed = LoginAttempt.query.filter(
        LoginAttempt.timestamp >= day_ago, LoginAttempt.success == False
    ).count()

    visitor_24h = SiteVisit.query.filter(SiteVisit.timestamp >= day_ago).count()
    visitor_24h_unique = db.session.query(
        func.count(func.distinct(SiteVisit.ip_address))
    ).filter(SiteVisit.timestamp >= day_ago).scalar() or 0

    recent_failed = LoginAttempt.query.filter_by(success=False).order_by(
        desc(LoginAttempt.timestamp)
    ).limit(5).all()

    return jsonify(
        user_counts=user_counts,
        customer_count=customer_count,
        purchase_count=purchase_count,
        paid_count=paid_count,
        feedback_total=feedback_total,
        feedback_unresolved=feedback_unresolved,
        login_24h={'total': login_24h_total, 'failed': login_24h_failed,
                   'successful': login_24h_total - login_24h_failed},
        visitor_24h={'total': visitor_24h, 'unique': visitor_24h_unique},
        recent_failed_logins=[a.to_dict() for a in recent_failed],
    )


# ============================================================================
# USER MANAGEMENT
# ============================================================================

@admin_api.route('/users')
@require_api_key
def list_users():
    q = User.query
    status = request.args.get('status')
    user_type = request.args.get('user_type')
    if status:
        q = q.filter_by(status=status)
    if user_type:
        q = q.filter_by(user_type=user_type)
    users = q.order_by(User.id).all()
    return jsonify([u.to_dict() for u in users])


@admin_api.route('/users', methods=['POST'])
@require_api_key
def create_user():
    data = request.get_json() or {}
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    user_type = data.get('user_type', 'admin')
    notes = data.get('notes', '')

    if not email or not password:
        return jsonify(error='Email and password are required'), 400
    if user_type not in ('admin', 'employee'):
        return jsonify(error='user_type must be admin or employee'), 400

    existing = User.query.filter_by(email=email).first()
    if existing:
        return jsonify(error='A user with that email already exists'), 409

    user = User(
        email=email,
        password=generate_password_hash(password),
        user_type=user_type,
        status='active',
        notes=notes or None,
    )
    db.session.add(user)
    db.session.commit()
    _audit('user.create', 'user', user.id, {'user_type': user_type})
    return jsonify(user.to_dict()), 201


@admin_api.route('/users/<int:uid>', methods=['PUT'])
@require_api_key
def update_user(uid):
    user = User.query.get_or_404(uid)
    data = request.get_json() or {}

    if 'status' in data and data['status'] in ('active', 'suspended', 'deleted'):
        user.status = data['status']
    if 'user_type' in data and data['user_type'] in ('admin', 'employee'):
        user.user_type = data['user_type']
    if 'notes' in data:
        user.notes = data['notes'] or None
    if 'password' in data and data['password']:
        user.password = generate_password_hash(data['password'])

    db.session.commit()
    _audit('user.update', 'user', uid, {k: v for k, v in data.items() if k != 'password'})
    return jsonify(user.to_dict())


@admin_api.route('/users/<int:uid>', methods=['DELETE'])
@require_api_key
def delete_user(uid):
    user = User.query.get_or_404(uid)
    # Protect primary env-var admin from deletion
    admin_hash = os.environ.get('ADMIN_USERNAME_HASH')
    if admin_hash and user.email == admin_hash and user.user_type == 'admin':
        return jsonify(error='Cannot delete the primary admin account'), 403
    user.status = 'deleted'
    db.session.commit()
    _audit('user.delete', 'user', uid)
    return jsonify(ok=True)


@admin_api.route('/users/<int:uid>/suspend', methods=['POST'])
@require_api_key
def suspend_user(uid):
    user = User.query.get_or_404(uid)
    user.status = 'suspended'
    db.session.commit()
    _audit('user.suspend', 'user', uid)
    return jsonify(user.to_dict())


@admin_api.route('/users/<int:uid>/activate', methods=['POST'])
@require_api_key
def activate_user(uid):
    user = User.query.get_or_404(uid)
    user.status = 'active'
    db.session.commit()
    _audit('user.activate', 'user', uid)
    return jsonify(user.to_dict())


# ============================================================================
# LOGIN ATTEMPTS
# ============================================================================

@admin_api.route('/login-attempts')
@require_api_key
def list_login_attempts():
    q = LoginAttempt.query

    success = request.args.get('success')
    if success is not None:
        q = q.filter_by(success=success.lower() == 'true')

    ip = request.args.get('ip')
    if ip:
        q = q.filter(LoginAttempt.ip_address.contains(ip))

    from_date = request.args.get('from')
    if from_date:
        try:
            q = q.filter(LoginAttempt.timestamp >= datetime.fromisoformat(from_date))
        except ValueError:
            pass

    to_date = request.args.get('to')
    if to_date:
        try:
            q = q.filter(LoginAttempt.timestamp <= datetime.fromisoformat(to_date))
        except ValueError:
            pass

    limit = min(int(request.args.get('limit', 100)), 500)
    attempts = q.order_by(desc(LoginAttempt.timestamp)).limit(limit).all()
    return jsonify([a.to_dict() for a in attempts])


# ============================================================================
# CUSTOMERS
# ============================================================================

@admin_api.route('/customers')
@require_api_key
def list_customers():
    q = Customer.query
    search = request.args.get('search', '').strip()
    if search:
        q = q.filter(
            Customer.email.contains(search) | Customer.name.contains(search)
        )
    limit = min(int(request.args.get('limit', 50)), 200)
    offset = int(request.args.get('offset', 0))
    total = q.count()
    customers = q.order_by(desc(Customer.id)).offset(offset).limit(limit).all()
    return jsonify(customers=[c.to_dict() for c in customers], total=total)


@admin_api.route('/customers/<int:cid>')
@require_api_key
def get_customer(cid):
    customer = Customer.query.get_or_404(cid)
    return jsonify(customer.to_dict(include_purchases=True))


@admin_api.route('/customers/<int:cid>', methods=['DELETE'])
@require_api_key
def delete_customer(cid):
    customer = Customer.query.get_or_404(cid)
    Purchase_info.query.filter_by(customer_id=cid).delete()
    db.session.delete(customer)
    db.session.commit()
    _audit('customer.delete', 'customer', cid)
    return jsonify(ok=True)


# ============================================================================
# PURCHASES
# ============================================================================

@admin_api.route('/purchases')
@require_api_key
def list_purchases():
    q = Purchase_info.query

    status = request.args.get('status')
    if status:
        q = q.filter_by(pay_status=status)

    customer_id = request.args.get('customer_id')
    if customer_id:
        q = q.filter_by(customer_id=int(customer_id))

    from_date = request.args.get('from')
    if from_date:
        try:
            q = q.filter(Purchase_info.purchase_date >= datetime.fromisoformat(from_date))
        except ValueError:
            pass

    to_date = request.args.get('to')
    if to_date:
        try:
            q = q.filter(Purchase_info.purchase_date <= datetime.fromisoformat(to_date))
        except ValueError:
            pass

    limit = min(int(request.args.get('limit', 50)), 200)
    purchases = q.order_by(desc(Purchase_info.id)).limit(limit).all()

    result = []
    for p in purchases:
        d = p.to_dict()
        cust = Customer.query.get(p.customer_id) if p.customer_id else None
        d['customer_email'] = cust.email if cust else None
        d['customer_name'] = cust.name if cust else None
        result.append(d)

    return jsonify(result)


# ============================================================================
# FEEDBACK
# ============================================================================

@admin_api.route('/feedback')
@require_api_key
def list_feedback():
    q = FeedBack.query

    fb_type = request.args.get('type')
    if fb_type:
        q = q.filter_by(feedbacktype=fb_type)

    resolved = request.args.get('resolved')
    if resolved is not None:
        if resolved.lower() == 'true':
            q = q.filter_by(resolved=True)
        else:
            q = q.filter((FeedBack.resolved == False) | (FeedBack.resolved == None))

    feedback = q.order_by(desc(FeedBack.id)).all()
    return jsonify([f.to_dict() for f in feedback])


@admin_api.route('/feedback/<int:fid>', methods=['PUT'])
@require_api_key
def update_feedback(fid):
    fb = FeedBack.query.get_or_404(fid)
    data = request.get_json() or {}

    if 'admin_notes' in data:
        fb.admin_notes = data['admin_notes']
        if data['admin_notes'] and not fb.first_response_date:
            fb.first_response_date = datetime.now(timezone.utc)

    if 'resolved' in data:
        fb.resolved = bool(data['resolved'])
        if fb.resolved:
            fb.resolved_date = datetime.now(timezone.utc)
            if fb.date:
                delta = fb.resolved_date - fb.date
                fb.resolution_time_hours = max(1, int(delta.total_seconds() / 3600))
        else:
            fb.resolved_date = None
            fb.resolution_time_hours = None

    db.session.commit()
    _audit('feedback.update', 'feedback', fid, data)
    return jsonify(fb.to_dict())


@admin_api.route('/feedback/<int:fid>', methods=['DELETE'])
@require_api_key
def delete_feedback(fid):
    fb = FeedBack.query.get_or_404(fid)
    db.session.delete(fb)
    db.session.commit()
    _audit('feedback.delete', 'feedback', fid)
    return jsonify(ok=True)


# ============================================================================
# VISITORS
# ============================================================================

@admin_api.route('/visitors')
@require_api_key
def visitor_stats():
    """Aggregated visitor analytics."""
    days = int(request.args.get('days', 7))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Daily page views
    daily = db.session.query(
        func.date(SiteVisit.timestamp).label('day'),
        func.count(SiteVisit.id).label('views'),
        func.count(func.distinct(SiteVisit.ip_address)).label('unique_ips'),
    ).filter(SiteVisit.timestamp >= since).group_by(
        func.date(SiteVisit.timestamp)
    ).order_by(func.date(SiteVisit.timestamp)).all()

    # Top pages
    top_pages = db.session.query(
        SiteVisit.path,
        func.count(SiteVisit.id).label('hits'),
        func.count(func.distinct(SiteVisit.ip_address)).label('unique_ips'),
    ).filter(SiteVisit.timestamp >= since).group_by(
        SiteVisit.path
    ).order_by(desc('hits')).limit(20).all()

    # Top referrers
    top_referrers = db.session.query(
        SiteVisit.referrer,
        func.count(SiteVisit.id).label('hits'),
    ).filter(
        SiteVisit.timestamp >= since,
        SiteVisit.referrer != None,
        SiteVisit.referrer != '',
    ).group_by(SiteVisit.referrer).order_by(desc('hits')).limit(10).all()

    total_views = sum(d.views for d in daily)
    total_unique = db.session.query(
        func.count(func.distinct(SiteVisit.ip_address))
    ).filter(SiteVisit.timestamp >= since).scalar() or 0

    return jsonify(
        days=days,
        total_views=total_views,
        total_unique=total_unique,
        avg_daily=round(total_views / max(days, 1), 1),
        daily=[{'day': str(d.day), 'views': d.views, 'unique_ips': d.unique_ips} for d in daily],
        top_pages=[{'path': p.path, 'hits': p.hits, 'unique_ips': p.unique_ips} for p in top_pages],
        top_referrers=[{'referrer': r.referrer, 'hits': r.hits} for r in top_referrers],
    )


@admin_api.route('/visitors/recent')
@require_api_key
def recent_visitors():
    limit = min(int(request.args.get('limit', 100)), 500)
    visits = SiteVisit.query.order_by(desc(SiteVisit.timestamp)).limit(limit).all()
    return jsonify([v.to_dict() for v in visits])


# ============================================================================
# SECURITY ALERTS
# ============================================================================

@admin_api.route('/security/alerts')
@require_api_key
def security_alerts():
    """Detect brute force and suspicious login patterns."""
    hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    day_ago = datetime.now(timezone.utc) - timedelta(hours=24)

    bf_threshold = int(os.environ.get('BRUTE_FORCE_THRESHOLD', '5'))
    sus_threshold = int(os.environ.get('SUSPICIOUS_THRESHOLD', '3'))

    # IPs with N+ failed attempts in the last hour
    brute_force = db.session.query(
        LoginAttempt.ip_address,
        func.count(LoginAttempt.id).label('attempts'),
        func.max(LoginAttempt.timestamp).label('latest'),
    ).filter(
        LoginAttempt.timestamp >= hour_ago,
        LoginAttempt.success == False,
    ).group_by(LoginAttempt.ip_address).having(
        func.count(LoginAttempt.id) >= bf_threshold
    ).all()

    # IPs with N+ failed attempts in the last 24 hours (lower threshold)
    suspicious = db.session.query(
        LoginAttempt.ip_address,
        func.count(LoginAttempt.id).label('attempts'),
        func.max(LoginAttempt.timestamp).label('latest'),
        func.max(LoginAttempt.user_agent).label('user_agent'),
    ).filter(
        LoginAttempt.timestamp >= day_ago,
        LoginAttempt.success == False,
    ).group_by(LoginAttempt.ip_address).having(
        func.count(LoginAttempt.id) >= sus_threshold
    ).all()

    # Unique failed usernames attempted in last 24h
    failed_usernames = db.session.query(
        LoginAttempt.username_attempted,
        func.count(LoginAttempt.id).label('attempts'),
    ).filter(
        LoginAttempt.timestamp >= day_ago,
        LoginAttempt.success == False,
    ).group_by(LoginAttempt.username_attempted).order_by(
        desc('attempts')
    ).limit(20).all()

    return jsonify(
        brute_force=[{
            'ip': b.ip_address, 'attempts': b.attempts,
            'latest': b.latest.isoformat() if b.latest else None,
            'severity': 'critical',
        } for b in brute_force],
        suspicious_ips=[{
            'ip': s.ip_address, 'attempts': s.attempts,
            'latest': s.latest.isoformat() if s.latest else None,
            'user_agent': s.user_agent,
            'severity': 'warning',
        } for s in suspicious],
        failed_usernames=[{
            'username': u.username_attempted, 'attempts': u.attempts,
        } for u in failed_usernames],
    )


# ============================================================================
# CSV EXPORT
# ============================================================================

@admin_api.route('/export/<table>')
@require_api_key
def export_csv(table):
    """Export table data as CSV."""
    output = io.StringIO()
    writer = csv.writer(output)

    if table == 'customers':
        writer.writerow(['ID', 'Email', 'Name', 'Created', 'Purchase Count'])
        for c in Customer.query.order_by(Customer.id).all():
            writer.writerow([c.id, c.email, c.name,
                c.creation_date.isoformat() if c.creation_date else '',
                len(c.buys) if c.buys else 0])

    elif table == 'purchases':
        writer.writerow(['ID', 'Product', 'Customer Email', 'City', 'State',
                         'Country', 'Postal Code', 'Pay Status', 'Date'])
        for p in Purchase_info.query.order_by(Purchase_info.id).all():
            cust = Customer.query.get(p.customer_id) if p.customer_id else None
            writer.writerow([p.id, p.product_name, cust.email if cust else '',
                p.city, p.state, p.country, p.postal_code, p.pay_status,
                p.purchase_date.isoformat() if p.purchase_date else ''])

    elif table == 'feedback':
        writer.writerow(['ID', 'Email', 'Type', 'Order ID', 'Serial #',
                         'Message', 'Date', 'Resolved', 'Admin Notes'])
        for f in FeedBack.query.order_by(FeedBack.id).all():
            writer.writerow([f.id, f.feedbackmail, f.feedbacktype,
                f.feedbackorderid or '', f.serial_number or '',
                f.feedbackfullfield, f.date.isoformat() if f.date else '',
                'Yes' if f.resolved else 'No', f.admin_notes or ''])

    elif table == 'logins':
        writer.writerow(['ID', 'IP', 'User Agent', 'Username', 'Success',
                         'Failure Reason', 'Matched Type', 'Timestamp'])
        for a in LoginAttempt.query.order_by(desc(LoginAttempt.id)).limit(1000).all():
            writer.writerow([a.id, a.ip_address, a.user_agent,
                a.username_attempted, 'Yes' if a.success else 'No',
                a.failure_reason or '', a.user_type_matched or '',
                a.timestamp.isoformat() if a.timestamp else ''])
    else:
        return jsonify(error=f'Unknown table: {table}'), 400

    csv_content = output.getvalue()
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=tullsite_{table}.csv'}
    )


# ============================================================================
# BANNED IPS
# ============================================================================

@admin_api.route('/banned-ips')
@require_api_key
def list_banned_ips():
    """List banned IPs. Filter by ?active=true|false."""
    q = BannedIP.query
    active = request.args.get('active')
    if active is not None:
        q = q.filter_by(active=active.lower() == 'true')
    bans = q.order_by(desc(BannedIP.created_date)).all()
    return jsonify([b.to_dict() for b in bans])


@admin_api.route('/banned-ips', methods=['POST'])
@require_api_key
def ban_ip():
    """Ban an IP address."""
    data = request.get_json() or {}
    ip_address = data.get('ip_address', '').strip()
    if not ip_address:
        return jsonify(error='ip_address is required'), 400

    # Prevent banning own IP
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip and ',' in client_ip:
        client_ip = client_ip.split(',')[0].strip()
    if ip_address == client_ip:
        return jsonify(error='Cannot ban your own IP address'), 400

    existing = BannedIP.query.filter_by(ip_address=ip_address, active=True).first()
    if existing:
        return jsonify(error='IP is already banned'), 409

    expires_hours = data.get('expires_hours')
    expires_at = None
    if expires_hours:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=int(expires_hours))

    ban = BannedIP(
        ip_address=ip_address,
        reason=data.get('reason', 'Manually banned'),
        banned_by='admin',
        expires_at=expires_at,
    )
    db.session.add(ban)
    db.session.commit()
    _audit('ip.ban', 'banned_ip', ban.id, {'ip': ip_address, 'reason': ban.reason})
    return jsonify(ban.to_dict()), 201


@admin_api.route('/banned-ips/<int:ban_id>', methods=['DELETE'])
@require_api_key
def unban_ip(ban_id):
    """Unban an IP (sets active=False)."""
    ban = BannedIP.query.get_or_404(ban_id)
    ban.active = False
    db.session.commit()
    _audit('ip.unban', 'banned_ip', ban_id, {'ip': ban.ip_address})
    return jsonify(ok=True)


# ============================================================================
# SECURITY: LOGIN HEATMAP
# ============================================================================

@admin_api.route('/security/login-heatmap')
@require_api_key
def login_heatmap():
    """Login attempt distribution by hour of day."""
    days = int(request.args.get('days', 7))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    rows = db.session.query(
        func.strftime('%H', LoginAttempt.timestamp).label('hour'),
        func.count(LoginAttempt.id).label('total'),
        func.sum(db.case((LoginAttempt.success == False, 1), else_=0)).label('failed'),
    ).filter(LoginAttempt.timestamp >= since).group_by('hour').all()

    hours = [{'total': 0, 'failed': 0} for _ in range(24)]
    for row in rows:
        h = int(row.hour)
        hours[h] = {'total': row.total, 'failed': int(row.failed or 0)}
    max_total = max(h['total'] for h in hours) if hours else 0
    return jsonify(hours=hours, max=max_total)


# ============================================================================
# SECURITY: GEO-IP RESOLUTION
# ============================================================================

@admin_api.route('/security/resolve-geo', methods=['POST'])
@require_api_key
def resolve_geo():
    """Resolve geo-location for a batch of IPs. Uses cache + ip-api.com."""
    import requests as ext_requests

    data = request.get_json() or {}
    ips = data.get('ips', [])[:20]
    results = {}

    for ip in ips:
        cached = GeoIPCache.query.filter_by(ip_address=ip).first()
        if cached:
            results[ip] = cached.to_dict()
            continue
        try:
            r = ext_requests.get(
                f'http://ip-api.com/json/{ip}',
                params={'fields': 'country,regionName,city,isp,status'},
                timeout=3,
            )
            if r.ok:
                geo = r.json()
                if geo.get('status') == 'success':
                    entry = GeoIPCache(
                        ip_address=ip,
                        country=geo.get('country'),
                        region=geo.get('regionName'),
                        city=geo.get('city'),
                        isp=geo.get('isp'),
                    )
                    db.session.add(entry)
                    db.session.commit()
                    results[ip] = entry.to_dict()
                else:
                    results[ip] = {'ip_address': ip, 'country': 'Unknown',
                                   'region': None, 'city': None, 'isp': None}
        except Exception:
            results[ip] = {'ip_address': ip, 'country': 'Lookup failed',
                           'region': None, 'city': None, 'isp': None}

    return jsonify(results)


# ============================================================================
# SECURITY: AUDIT LOG
# ============================================================================

@admin_api.route('/security/audit-log')
@require_api_key
def audit_log():
    """Return recent admin API audit log entries."""
    limit = min(int(request.args.get('limit', 50)), 200)
    logs = AdminAuditLog.query.order_by(desc(AdminAuditLog.timestamp)).limit(limit).all()
    return jsonify([entry.to_dict() for entry in logs])


# ============================================================================
# VISITOR ANALYTICS: DEVICES
# ============================================================================

@admin_api.route('/visitors/devices')
@require_api_key
def visitor_devices():
    """Device/browser/OS breakdown from user-agent parsing."""
    try:
        from user_agents import parse as parse_ua
    except ImportError:
        return jsonify(error='user-agents package not installed'), 500

    days = int(request.args.get('days', 7))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    ua_counts = db.session.query(
        SiteVisit.user_agent, func.count(SiteVisit.id)
    ).filter(SiteVisit.timestamp >= since).group_by(SiteVisit.user_agent).all()

    browsers, oses, devices = {}, {}, {}
    for ua_str, count in ua_counts:
        if not ua_str:
            continue
        ua = parse_ua(ua_str)
        b = ua.browser.family or 'Unknown'
        o = ua.os.family or 'Unknown'
        d = 'Mobile' if ua.is_mobile else ('Tablet' if ua.is_tablet else 'Desktop')
        browsers[b] = browsers.get(b, 0) + count
        oses[o] = oses.get(o, 0) + count
        devices[d] = devices.get(d, 0) + count

    def sorted_list(d):
        return sorted([{'name': k, 'count': v} for k, v in d.items()],
                       key=lambda x: x['count'], reverse=True)

    return jsonify(browsers=sorted_list(browsers), os=sorted_list(oses),
                   devices=sorted_list(devices))


# ============================================================================
# VISITOR ANALYTICS: REFERRERS
# ============================================================================

@admin_api.route('/visitors/referrers')
@require_api_key
def visitor_referrers():
    """Referrer source analysis grouped by domain."""
    from urllib.parse import urlparse

    days = int(request.args.get('days', 7))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    site_domain = os.environ.get('MAIN_DOMAIN', 'tullhydro.com').replace('https://', '').replace('http://', '').strip('/')

    refs = db.session.query(
        SiteVisit.referrer, func.count(SiteVisit.id).label('hits')
    ).filter(SiteVisit.timestamp >= since).group_by(SiteVisit.referrer).all()

    domains = {}
    internal_hits = 0
    external_hits = 0
    direct_hits = 0

    for ref, hits in refs:
        if not ref:
            direct_hits += hits
            continue
        try:
            domain = urlparse(ref).netloc.lower()
        except Exception:
            domain = ref
        if not domain:
            direct_hits += hits
            continue
        if site_domain in domain:
            internal_hits += hits
        else:
            external_hits += hits
            domains[domain] = domains.get(domain, 0) + hits

    sources = sorted([{'domain': k, 'hits': v, 'type': 'external'} for k, v in domains.items()],
                     key=lambda x: x['hits'], reverse=True)[:20]

    return jsonify(sources=sources, internal_hits=internal_hits,
                   external_hits=external_hits, direct_hits=direct_hits)


# ============================================================================
# VISITOR ANALYTICS: HEATMAP
# ============================================================================

@admin_api.route('/visitors/heatmap')
@require_api_key
def visitor_heatmap():
    """Visitor traffic distribution by hour of day."""
    days = int(request.args.get('days', 7))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    rows = db.session.query(
        func.strftime('%H', SiteVisit.timestamp).label('hour'),
        func.count(SiteVisit.id).label('count'),
    ).filter(SiteVisit.timestamp >= since).group_by('hour').all()

    hours = [0] * 24
    for row in rows:
        h = int(row.hour)
        hours[h] = row.count
    return jsonify(hours=hours, max=max(hours) if hours else 0)


# ============================================================================
# VISITOR ANALYTICS: PAGE FLOW
# ============================================================================

@admin_api.route('/visitors/pageflow')
@require_api_key
def visitor_pageflow():
    """Page flow patterns: entry pages, bounce rate, top sequences."""
    days = int(request.args.get('days', 7))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    visits = SiteVisit.query.filter(
        SiteVisit.timestamp >= since,
    ).order_by(SiteVisit.ip_address, SiteVisit.timestamp).all()

    # Group into sessions (same IP, <30min gap)
    sessions = []
    current_session = []
    prev_ip = None
    prev_time = None
    session_gap = timedelta(minutes=30)

    for v in visits:
        if v.ip_address != prev_ip or (prev_time and v.timestamp - prev_time > session_gap):
            if current_session:
                sessions.append(current_session)
            current_session = []
        current_session.append(v)
        prev_ip = v.ip_address
        prev_time = v.timestamp
    if current_session:
        sessions.append(current_session)

    entry_pages = {}
    sequences = {}
    single_page = 0

    for s in sessions:
        entry = s[0].path
        entry_pages[entry] = entry_pages.get(entry, 0) + 1
        if len(s) == 1:
            single_page += 1
        for i in range(len(s) - 1):
            pair = (s[i].path, s[i + 1].path)
            if pair[0] != pair[1]:
                sequences[pair] = sequences.get(pair, 0) + 1

    total_sessions = len(sessions)
    bounce_rate = round((single_page / total_sessions * 100), 1) if total_sessions else 0

    top_entry = sorted([{'path': k, 'count': v} for k, v in entry_pages.items()],
                       key=lambda x: x['count'], reverse=True)[:10]
    top_seq = sorted([{'from': k[0], 'to': k[1], 'count': v} for k, v in sequences.items()],
                     key=lambda x: x['count'], reverse=True)[:10]

    return jsonify(
        entry_pages=top_entry,
        bounce_rate=bounce_rate,
        sessions_total=total_sessions,
        sessions_single_page=single_page,
        top_sequences=top_seq,
    )


# ============================================================================
# FEEDBACK INTELLIGENCE (Feature 2)
# ============================================================================

@admin_api.route('/feedback/stats')
@require_api_key
def feedback_stats():
    """Feedback analytics: type distribution, resolution metrics, aging."""
    now = datetime.now(timezone.utc)

    type_rows = db.session.query(
        FeedBack.feedbacktype, func.count(FeedBack.id)
    ).group_by(FeedBack.feedbacktype).all()
    type_dist = [{'type': t or 'Unknown', 'count': c} for t, c in type_rows]

    resolved = FeedBack.query.filter_by(resolved=True).filter(
        FeedBack.resolution_time_hours != None
    ).all()
    hours_list = [f.resolution_time_hours for f in resolved if f.resolution_time_hours]
    resolution_metrics = {
        'avg_hours': round(sum(hours_list) / len(hours_list), 1) if hours_list else None,
        'min_hours': min(hours_list) if hours_list else None,
        'max_hours': max(hours_list) if hours_list else None,
        'total_resolved': len(resolved),
    }

    unresolved = FeedBack.query.filter(
        (FeedBack.resolved == False) | (FeedBack.resolved == None)
    ).all()
    buckets = {'under_3d': 0, '3_to_7d': 0, '7_to_14d': 0, 'over_14d': 0}
    for fb in unresolved:
        if fb.date:
            age_days = (now - fb.date).total_seconds() / 86400
            if age_days < 3:
                buckets['under_3d'] += 1
            elif age_days < 7:
                buckets['3_to_7d'] += 1
            elif age_days < 14:
                buckets['7_to_14d'] += 1
            else:
                buckets['over_14d'] += 1
    buckets['total_unresolved'] = len(unresolved)

    return jsonify(
        type_distribution=type_dist,
        resolution_metrics=resolution_metrics,
        aging_buckets=buckets,
    )


@admin_api.route('/feedback/<int:fid>/reply', methods=['POST'])
@require_api_key
def reply_feedback(fid):
    """Send email reply to feedback submitter via Postmark."""
    import requests as ext_requests

    fb = FeedBack.query.get_or_404(fid)
    data = request.get_json() or {}
    message = data.get('message', '').strip()
    if not message:
        return jsonify(error='message is required'), 400

    server_token = os.environ.get('POSTMARK_SERVER_TOKEN')
    sender_email = os.environ.get('POSTMARK_SENDER_EMAIL')
    if not server_token:
        return jsonify(error='Postmark not configured'), 503

    ref = f'TULL-{str(fb.id).zfill(4)}'

    try:
        r = ext_requests.post(
            'https://api.postmarkapp.com/email',
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-Postmark-Server-Token': server_token,
            },
            json={
                'From': sender_email,
                'To': fb.feedbackmail,
                'Subject': f'Re: {ref} - Tull Hydroponics',
                'TextBody': f'Hi,\n\n{message}\n\n- Tull Hydroponics Team\n\nRef: {ref}',
                'HtmlBody': feedback_reply_html(message, ref, fb.feedbacktype),
                'MessageStream': 'outbound',
            },
            timeout=10,
        )
        email_ok = r.status_code == 200
    except Exception:
        email_ok = False

    timestamp_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
    note_entry = f'[Reply {timestamp_str}] {message}'
    if fb.admin_notes:
        fb.admin_notes = fb.admin_notes + '\n' + note_entry
    else:
        fb.admin_notes = note_entry

    if not fb.first_response_date:
        fb.first_response_date = datetime.now(timezone.utc)

    if data.get('resolve'):
        fb.resolved = True
        fb.resolved_date = datetime.now(timezone.utc)
        if fb.date:
            delta = fb.resolved_date - fb.date
            fb.resolution_time_hours = max(1, int(delta.total_seconds() / 3600))

    db.session.commit()
    _audit('feedback.reply', 'feedback', fid, {'email_sent': email_ok, 'resolve': data.get('resolve', False)})
    return jsonify(ok=True, email_sent=email_ok, feedback=fb.to_dict())


# ============================================================================
# CUSTOMER INSIGHTS (Feature 3)
# ============================================================================

@admin_api.route('/customers/stats')
@require_api_key
def customer_stats():
    """Customer analytics: geography, repeat rates, acquisition trend."""
    state_rows = db.session.query(
        Purchase_info.state, func.count(Purchase_info.id)
    ).filter(Purchase_info.state != None, Purchase_info.state != '').group_by(
        Purchase_info.state
    ).order_by(desc(func.count(Purchase_info.id))).limit(10).all()

    country_rows = db.session.query(
        Purchase_info.country, func.count(Purchase_info.id)
    ).filter(Purchase_info.country != None, Purchase_info.country != '').group_by(
        Purchase_info.country
    ).order_by(desc(func.count(Purchase_info.id))).limit(10).all()

    repeat_q = db.session.query(
        Customer.id
    ).join(Purchase_info).group_by(Customer.id).having(
        func.count(Purchase_info.id) >= 2
    ).count()
    total_customers = Customer.query.count()

    week_rows = db.session.query(
        func.strftime('%Y-W%W', Customer.creation_date).label('period'),
        func.count(Customer.id).label('count'),
    ).filter(Customer.creation_date != None).group_by('period').order_by('period').all()

    return jsonify(
        geographic={
            'top_states': [{'state': s, 'count': c} for s, c in state_rows],
            'top_countries': [{'country': co, 'count': c} for co, c in country_rows],
        },
        repeat_customers={
            'count': repeat_q,
            'total': total_customers,
            'percentage': round(repeat_q / total_customers * 100, 1) if total_customers else 0,
        },
        acquisition_trend=[{'period': str(p), 'count': c} for p, c in week_rows[-12:]],
    )


@admin_api.route('/customers/<int:cid>', methods=['PUT'])
@require_api_key
def update_customer(cid):
    """Update customer tags and admin notes."""
    customer = Customer.query.get_or_404(cid)
    data = request.get_json() or {}

    if 'tags' in data:
        customer.tags = data['tags'] or None
    if 'admin_notes' in data:
        customer.admin_notes = data['admin_notes'] or None

    db.session.commit()
    _audit('customer.update', 'customer', cid, data)
    return jsonify(customer.to_dict())


@admin_api.route('/customers/geo')
@require_api_key
def customer_geo():
    """Customer geography aggregation."""
    state_rows = db.session.query(
        Purchase_info.state, func.count(func.distinct(Purchase_info.customer_id))
    ).filter(Purchase_info.state != None, Purchase_info.state != '').group_by(
        Purchase_info.state
    ).order_by(desc(func.count(func.distinct(Purchase_info.customer_id)))).limit(15).all()

    return jsonify(
        states=[{'state': s, 'count': c} for s, c in state_rows],
    )


# ============================================================================
# PURCHASE & REVENUE ANALYTICS (Feature 5)
# ============================================================================

@admin_api.route('/purchases/stats')
@require_api_key
def purchase_stats():
    """Purchase analytics: orders over time, revenue, status breakdown."""
    days = int(request.args.get('days', 30))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    daily = db.session.query(
        func.date(Purchase_info.purchase_date).label('day'),
        func.count(Purchase_info.id).label('count'),
        func.sum(db.case((Purchase_info.pay_status == 'paid', 1), else_=0)).label('paid'),
    ).filter(Purchase_info.purchase_date >= since).group_by(
        func.date(Purchase_info.purchase_date)
    ).order_by(func.date(Purchase_info.purchase_date)).all()

    rev = db.session.query(
        func.sum(Purchase_info.amount_cents),
        func.avg(Purchase_info.amount_cents),
        func.count(Purchase_info.id),
    ).filter(Purchase_info.amount_cents != None).first()
    total_cents = int(rev[0] or 0)
    avg_cents = int(rev[1] or 0) if rev[1] else 0
    orders_with_amount = rev[2] or 0

    status_rows = db.session.query(
        Purchase_info.pay_status, func.count(Purchase_info.id)
    ).group_by(Purchase_info.pay_status).all()

    period_total = sum(d.count for d in daily)

    return jsonify(
        orders_over_time=[{
            'period': str(d.day),
            'count': d.count,
            'paid': int(d.paid or 0),
            'pending': d.count - int(d.paid or 0),
        } for d in daily],
        revenue={
            'total_cents': total_cents,
            'currency': 'usd',
            'avg_order_cents': avg_cents,
            'orders_with_amount': orders_with_amount,
        },
        status_breakdown=[{'status': s or 'unknown', 'count': c} for s, c in status_rows],
        period_total=period_total,
    )


@admin_api.route('/purchases/geo')
@require_api_key
def purchase_geo():
    """Shipping geography by order count."""
    state_rows = db.session.query(
        Purchase_info.state, func.count(Purchase_info.id)
    ).filter(Purchase_info.state != None, Purchase_info.state != '').group_by(
        Purchase_info.state
    ).order_by(desc(func.count(Purchase_info.id))).limit(15).all()

    country_rows = db.session.query(
        Purchase_info.country, func.count(Purchase_info.id)
    ).filter(Purchase_info.country != None, Purchase_info.country != '').group_by(
        Purchase_info.country
    ).order_by(desc(func.count(Purchase_info.id))).limit(10).all()

    return jsonify(
        states=[{'state': s, 'count': c} for s, c in state_rows],
        countries=[{'country': co, 'count': c} for co, c in country_rows],
    )


@admin_api.route('/purchases/funnel')
@require_api_key
def purchase_funnel():
    """Conversion funnel: unique visitors -> sell page views -> purchases."""
    days = int(request.args.get('days', 30))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    unique_visitors = db.session.query(
        func.count(func.distinct(SiteVisit.ip_address))
    ).filter(SiteVisit.timestamp >= since).scalar() or 0

    sell_views = db.session.query(
        func.count(func.distinct(SiteVisit.ip_address))
    ).filter(
        SiteVisit.timestamp >= since,
        SiteVisit.path == '/sell',
    ).scalar() or 0

    purchases = Purchase_info.query.filter(
        Purchase_info.purchase_date >= since,
    ).count()

    return jsonify(
        days=days,
        unique_visitors=unique_visitors,
        sell_page_views=sell_views,
        completed_purchases=purchases,
    )
