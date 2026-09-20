"""Startup migrations add missing columns to an older database.

The product_name migration checked a table called purchase__info (two
underscores), which never existed, so it tried to ALTER a missing table on
every boot and was swallowed by the bare except.
"""

import os
import sqlite3


def test_product_name_column_is_added_to_old_purchase_table(tmp_path, monkeypatch):
    db_file = tmp_path / 'old.db'
    conn = sqlite3.connect(db_file)
    conn.execute('CREATE TABLE purchase_info (id INTEGER PRIMARY KEY, customer_id INTEGER)')
    conn.execute('CREATE TABLE user (id INTEGER PRIMARY KEY, email VARCHAR(150), password VARCHAR(256))')
    conn.commit()
    conn.close()

    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{db_file.as_posix()}')
    from xissite import create_app
    create_app()

    conn = sqlite3.connect(db_file)
    cols = {row[1] for row in conn.execute("PRAGMA table_info('purchase_info')")}
    conn.close()
    assert 'product_name' in cols
