#!/usr/bin/env python3
"""
Tull Hydroponics - Database Management CLI
==========================================

Runs on the app's SQLAlchemy models, so it follows the real schema and
whatever database the app is configured for (DATABASE_URL, or the local
SQLite file). Run from the repository root:

    python -m xissite.manage_db <command>

Commands:
    status      Row counts for every table
    customers   List customers with purchase counts
    purchases   List purchases with customer email
    feedback    List feedback submissions
    users       List accounts (never passwords)
    export      Write customers.csv, purchases.csv, feedback.csv  [--out DIR]
    backup      Copy the SQLite file (SQLite file databases only)
    reset       Back up, then delete the SQLite file (SQLite file databases only)

Backup and reset refuse anything that is not a SQLite file: an in-memory
database has nothing to copy and Cloud SQL has its own tooling.
"""

import argparse
import csv
import os
import shutil
import sqlite3
import sys
from datetime import datetime


# ============================================================================
# HELPERS
# ============================================================================

def _sqlite_file(app):
    """Path of the SQLite file the app uses, or None for anything else."""
    uri = app.config['SQLALCHEMY_DATABASE_URI']
    prefix = 'sqlite:///'
    if not uri.startswith(prefix):
        return None
    path = uri[len(prefix):]
    if path in ('', ':memory:'):
        return None
    return path


def _fmt_dt(value):
    return value.strftime('%Y-%m-%d %H:%M') if value else '--'


def _rows_to_csv(path, columns, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)


# ============================================================================
# COMMANDS  (each takes the parsed args; an app context is already active)
# ============================================================================

def cmd_status(args):
    from . import db
    from .models import (Customer, Purchase_info, FeedBack, User, LoginAttempt,
                         BannedIP, SiteVisit, GeoIPCache, AdminAuditLog)
    print('DATABASE STATUS')
    print(f"  uri: {db.engine.url}")
    for model in (Customer, Purchase_info, FeedBack, User, LoginAttempt,
                  BannedIP, SiteVisit, GeoIPCache, AdminAuditLog):
        print(f"  {model.__tablename__}: {model.query.count()}")
    return 0


def cmd_customers(args):
    from . import db
    from .models import Customer, Purchase_info
    from sqlalchemy import func
    counts = dict(db.session.query(Purchase_info.customer_id, func.count(Purchase_info.id))
                  .group_by(Purchase_info.customer_id).all())
    rows = Customer.query.order_by(Customer.id).all()
    if not rows:
        print('No customers.')
        return 0
    print(f"{'ID':<5} {'Email':<32} {'Name':<24} {'Created':<17} {'Orders':>6}")
    for c in rows:
        print(f"{c.id:<5} {c.email:<32} {(c.name or '--'):<24} {_fmt_dt(c.creation_date):<17} {counts.get(c.id, 0):>6}")
    return 0


def cmd_purchases(args):
    from .models import Purchase_info, Customer
    rows = Purchase_info.query.order_by(Purchase_info.id).all()
    if not rows:
        print('No purchases.')
        return 0
    print(f"{'ID':<6} {'Customer':<32} {'Product':<18} {'Status':<8} {'City':<16} {'Date':<17}")
    for p in rows:
        email = p.customer.email if p.customer else '--'
        print(f"{p.id:<6} {email:<32} {(p.product_name or '--'):<18} {(p.pay_status or '--'):<8} "
              f"{(p.city or '--'):<16} {_fmt_dt(p.purchase_date):<17}")
    return 0


def cmd_feedback(args):
    from .models import FeedBack
    rows = FeedBack.query.order_by(FeedBack.id.desc()).all()
    if not rows:
        print('No feedback.')
        return 0
    for f in rows:
        print(f"TULL-{f.id:05d}  {f.feedbacktype or '--'}  {'resolved' if f.resolved else 'open'}  "
              f"{f.feedbackmail}  {_fmt_dt(f.date)}")
        if f.feedbackorderid:
            print(f"  order: {f.feedbackorderid}")
        if f.serial_number:
            print(f"  serial: {f.serial_number}")
        msg = f.feedbackfullfield or ''
        print(f"  {msg[:100]}{'...' if len(msg) > 100 else ''}")
    return 0


def cmd_users(args):
    from .models import User
    rows = User.query.order_by(User.id).all()
    if not rows:
        print('No users.')
        return 0
    print(f"{'ID':<5} {'Username':<24} {'Type':<10} {'Status':<10} {'Last login':<17} {'Display name'}")
    for u in rows:
        print(f"{u.id:<5} {u.email:<24} {u.user_type:<10} {u.status:<10} {_fmt_dt(u.last_login):<17} {u.display_name or ''}")
    print('\nPasswords are scrypt hashes in the database. Change them through the admin API or panel.')
    return 0


def cmd_export(args):
    from .models import Customer, Purchase_info, FeedBack
    out = args.out or f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(out, exist_ok=True)

    customers = Customer.query.order_by(Customer.id).all()
    _rows_to_csv(os.path.join(out, 'customers.csv'),
                 ['id', 'email', 'name', 'creation_date', 'purchase_count'],
                 [[c.id, c.email, c.name, c.creation_date, len(c.buys)] for c in customers])

    purchases = Purchase_info.query.order_by(Purchase_info.id).all()
    _rows_to_csv(os.path.join(out, 'purchases.csv'),
                 ['id', 'customer_id', 'customer_email', 'product_name', 'city', 'state',
                  'country', 'line1', 'line2', 'postal_code', 'pay_status', 'purchase_date'],
                 [[p.id, p.customer_id, p.customer.email if p.customer else '', p.product_name,
                   p.city, p.state, p.country, p.line1, p.line2, p.postal_code, p.pay_status,
                   p.purchase_date] for p in purchases])

    feedback = FeedBack.query.order_by(FeedBack.id).all()
    _rows_to_csv(os.path.join(out, 'feedback.csv'),
                 ['id', 'feedbackmail', 'feedbacktype', 'feedbackorderid', 'serial_number',
                  'feedbackfullfield', 'date', 'submitter_ip', 'resolved', 'admin_notes',
                  'first_response_date', 'resolved_date', 'resolution_time_hours'],
                 [[f.id, f.feedbackmail, f.feedbacktype, f.feedbackorderid, f.serial_number,
                   f.feedbackfullfield, f.date, f.submitter_ip, f.resolved, f.admin_notes,
                   f.first_response_date, f.resolved_date, f.resolution_time_hours]
                  for f in feedback])

    print(f"Exported {len(customers)} customers, {len(purchases)} purchases, {len(feedback)} feedback rows to {out}/")
    return 0


def _backup(path):
    dest = f"{os.path.splitext(path)[0]}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    src = sqlite3.connect(path)
    dst = sqlite3.connect(dest)
    src.backup(dst)
    dst.close()
    src.close()
    print(f"Backup created: {dest} ({os.path.getsize(dest) / 1024:.1f} KB)")
    return dest


def cmd_backup(args):
    path = _sqlite_file(args.app)
    if not path:
        print('backup only applies to a SQLite file database; this app is not using one.')
        return 2
    _backup(path)
    return 0


def cmd_reset(args):
    path = _sqlite_file(args.app)
    if not path:
        print('reset only applies to a SQLite file database; this app is not using one.')
        return 2
    print(f"This deletes all data in {path} (a backup is taken first).")
    if not args.yes:
        if input("Type 'RESET' to confirm: ") != 'RESET':
            print('Reset cancelled.')
            return 1
    _backup(path)
    from . import db
    db.session.remove()
    db.engine.dispose()
    os.remove(path)
    print(f"Deleted {path}. Start the app to create a fresh database.")
    return 0


COMMANDS = {
    'status': cmd_status, 'customers': cmd_customers, 'purchases': cmd_purchases,
    'feedback': cmd_feedback, 'users': cmd_users, 'export': cmd_export,
    'backup': cmd_backup, 'reset': cmd_reset,
}


# ============================================================================
# ENTRY POINT
# ============================================================================

def run(argv=None, app=None):
    """Parse argv and run one command inside an app context. Returns an exit code."""
    parser = argparse.ArgumentParser(prog='python -m xissite.manage_db',
                                     description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=sorted(COMMANDS))
    parser.add_argument('--out', help='export: directory to write CSV files into')
    parser.add_argument('--yes', action='store_true', help='reset: skip the confirmation prompt')
    args = parser.parse_args(argv)

    if app is None:
        os.environ.setdefault('FLASK_ENV', 'development')
        from . import create_app
        app = create_app()
    args.app = app
    with app.app_context():
        return COMMANDS[args.command](args)


if __name__ == '__main__':
    sys.exit(run())
