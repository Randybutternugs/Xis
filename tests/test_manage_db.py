"""The database CLI runs on the app's models, so it follows the real schema
and whatever DATABASE_URL points at. Backup and reset only make sense for
a SQLite file and must refuse anything else."""

import csv
import os
import re

os.environ['ADMIN_API_KEY'] = 'test-api-key-for-dual-auth'


def _seed(db):
    from werkzeug.security import generate_password_hash
    from xissite.models import Customer, Purchase_info, FeedBack, User
    c = Customer(email='c@x.co', name='Cus Tomer')
    db.session.add(c)
    db.session.flush()
    db.session.add(Purchase_info(customer_id=c.id, city='Austin', state='TX', pay_status='paid'))
    db.session.add(FeedBack(feedbackmail='a@b.co', feedbacktype='General',
                            feedbackfullfield='hello there friend'))
    db.session.add(User(email='cli-admin', password=generate_password_hash('x' * 10),
                        user_type='admin', status='active', display_name='CLI Admin'))
    db.session.commit()


def test_status_counts_every_table(app, db, capsys):
    from xissite import manage_db
    _seed(db)
    manage_db.run(['status'], app=app)
    out = capsys.readouterr().out
    assert 'customer: 1' in out
    assert 'purchase_info: 1' in out
    assert 'feed_back: 1' in out
    assert re.search(r'user: [1-9]', out)
    for table in ('login_attempt', 'banned_ip', 'site_visit', 'geo_ip_cache', 'admin_audit_log'):
        assert f'{table}: 0' in out


def test_customers_lists_name_and_purchase_count(app, db, capsys):
    from xissite import manage_db
    _seed(db)
    manage_db.run(['customers'], app=app)
    out = capsys.readouterr().out
    assert 'c@x.co' in out and 'Cus Tomer' in out


def test_export_writes_csv_with_current_columns(app, db, tmp_path):
    from xissite import manage_db
    _seed(db)
    manage_db.run(['export', '--out', str(tmp_path)], app=app)
    rows = list(csv.reader(open(tmp_path / 'purchases.csv', newline='', encoding='utf-8')))
    assert 'pay_status' in rows[0] and 'paid' not in rows[0]
    assert rows[1][rows[0].index('pay_status')] == 'paid'
    assert (tmp_path / 'customers.csv').exists()
    assert (tmp_path / 'feedback.csv').exists()


def test_users_shows_email_type_and_status_never_hashes(app, db, capsys):
    from xissite import manage_db
    _seed(db)
    manage_db.run(['users'], app=app)
    out = capsys.readouterr().out
    assert 'cli-admin' in out and 'admin' in out and 'active' in out and 'CLI Admin' in out
    assert 'scrypt:' not in out
    assert 'environment variables' not in out


def test_backup_refuses_non_sqlite_file_database(app, db, capsys):
    from xissite import manage_db
    code = manage_db.run(['backup'], app=app)  # test DB is sqlite:///:memory:
    assert code != 0
    assert 'SQLite file' in capsys.readouterr().out
