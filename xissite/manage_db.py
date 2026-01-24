#!/usr/bin/env python3
"""
Tull Hydroponics - Database Management Script
==============================================

A command-line tool for managing the Tull Hydroponics database.

Usage:
    python manage_db.py [command]

Commands:
    status      Show database status and table counts
    customers   List all customers
    purchases   List all purchases
    feedback    List all feedback
    users       List all users
    export      Export all data to CSV files
    reset       Reset the database (WARNING: deletes all data)
    backup      Create a backup of the database
"""

import os
import sys
import sqlite3
import csv
from datetime import datetime

DB_NAME = "tullhydro.db"

def get_db_path():
    """Find the database file."""
    if os.path.exists(DB_NAME):
        return DB_NAME
    # Check in parent directory
    parent_path = os.path.join('..', DB_NAME)
    if os.path.exists(parent_path):
        return parent_path
    return None

def get_connection():
    """Get database connection."""
    db_path = get_db_path()
    if not db_path:
        print(f"Error: Database '{DB_NAME}' not found.")
        print("Run 'python main.py' first to create the database.")
        sys.exit(1)
    return sqlite3.connect(db_path)

def cmd_status():
    """Show database status."""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("=" * 50)
    print("DATABASE STATUS")
    print("=" * 50)
    print(f"Database: {get_db_path()}")
    print(f"Size: {os.path.getsize(get_db_path()) / 1024:.1f} KB")
    print()
    
    tables = ['customer', 'purchase__info', 'feed_back', 'user']
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count} records")
        except sqlite3.OperationalError:
            print(f"  {table}: (table not found)")
    
    conn.close()
    print()

def cmd_customers():
    """List all customers."""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("=" * 80)
    print("CUSTOMERS")
    print("=" * 80)
    
    cursor.execute("SELECT id, email, first_name, last_name, creation_date FROM customer ORDER BY id")
    rows = cursor.fetchall()
    
    if not rows:
        print("No customers found.")
    else:
        print(f"{'ID':<5} {'Email':<30} {'Name':<25} {'Created':<20}")
        print("-" * 80)
        for row in rows:
            name = f"{row[2] or ''} {row[3] or ''}".strip() or "(no name)"
            created = row[4][:10] if row[4] else "(unknown)"
            print(f"{row[0]:<5} {row[1]:<30} {name:<25} {created:<20}")
    
    conn.close()
    print()

def cmd_purchases():
    """List all purchases."""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("=" * 100)
    print("PURCHASES")
    print("=" * 100)
    
    cursor.execute("""
        SELECT p.id, c.email, p.product_name, p.purchase_date, p.paid
        FROM purchase__info p
        LEFT JOIN customer c ON p.customer_id = c.id
        ORDER BY p.id
    """)
    rows = cursor.fetchall()
    
    if not rows:
        print("No purchases found.")
    else:
        print(f"{'ID':<8} {'Customer':<30} {'Product':<20} {'Date':<15} {'Paid':<6}")
        print("-" * 100)
        for row in rows:
            date = row[3][:10] if row[3] else "(unknown)"
            paid = "Yes" if row[4] else "No"
            print(f"{row[0]:<8} {(row[1] or 'N/A'):<30} {(row[2] or 'N/A'):<20} {date:<15} {paid:<6}")
    
    conn.close()
    print()

def cmd_feedback():
    """List all feedback."""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("=" * 100)
    print("FEEDBACK")
    print("=" * 100)
    
    cursor.execute("SELECT id, feedbackmail, feedbacktype, feedbackorderid, feedbackfullfield FROM feed_back ORDER BY id DESC")
    rows = cursor.fetchall()
    
    if not rows:
        print("No feedback found.")
    else:
        for row in rows:
            print(f"\nID: {row[0]}")
            print(f"Email: {row[1]}")
            print(f"Type: {row[2]}")
            if row[3]:
                print(f"Order ID: {row[3]}")
            print(f"Message: {row[4][:100]}{'...' if len(row[4] or '') > 100 else ''}")
            print("-" * 50)
    
    conn.close()

def cmd_users():
    """List all users."""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("=" * 60)
    print("USERS")
    print("=" * 60)
    
    try:
        cursor.execute("SELECT id, user_type FROM user ORDER BY id")
        rows = cursor.fetchall()
        
        if not rows:
            print("No users found.")
        else:
            print(f"{'ID':<5} {'Type':<15}")
            print("-" * 20)
            for row in rows:
                print(f"{row[0]:<5} {row[1] or 'admin':<15}")
    except sqlite3.OperationalError as e:
        print(f"Error reading users: {e}")
    
    conn.close()
    print()
    print("Note: User credentials are stored as hashes in environment variables,")
    print("not in the database. The database only tracks login sessions.")

def cmd_export():
    """Export all data to CSV."""
    conn = get_connection()
    cursor = conn.cursor()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_dir = f"export_{timestamp}"
    os.makedirs(export_dir, exist_ok=True)
    
    exports = [
        ('customer', 'customers.csv', "SELECT * FROM customer"),
        ('purchase__info', 'purchases.csv', "SELECT * FROM purchase__info"),
        ('feed_back', 'feedback.csv', "SELECT * FROM feed_back"),
    ]
    
    for table, filename, query in exports:
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            filepath = os.path.join(export_dir, filename)
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(rows)
            print(f"Exported {len(rows)} rows to {filepath}")
        except sqlite3.OperationalError as e:
            print(f"Skipped {table}: {e}")
    
    conn.close()
    print(f"\nAll exports saved to: {export_dir}/")

def cmd_backup():
    """Create a database backup."""
    db_path = get_db_path()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"tullhydro_backup_{timestamp}.db"
    
    conn = sqlite3.connect(db_path)
    backup = sqlite3.connect(backup_path)
    conn.backup(backup)
    backup.close()
    conn.close()
    
    print(f"Backup created: {backup_path}")
    print(f"Size: {os.path.getsize(backup_path) / 1024:.1f} KB")

def cmd_reset():
    """Reset the database."""
    db_path = get_db_path()
    
    print("=" * 50)
    print("WARNING: DATABASE RESET")
    print("=" * 50)
    print(f"This will DELETE all data in: {db_path}")
    print()
    
    confirm = input("Type 'RESET' to confirm: ")
    if confirm != 'RESET':
        print("Reset cancelled.")
        return
    
    # Create backup first
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"tullhydro_backup_{timestamp}.db"
    
    conn = sqlite3.connect(db_path)
    backup = sqlite3.connect(backup_path)
    conn.backup(backup)
    backup.close()
    conn.close()
    print(f"Backup created: {backup_path}")
    
    # Delete database
    os.remove(db_path)
    print(f"Database deleted: {db_path}")
    print()
    print("Restart the application to create a fresh database.")

def cmd_help():
    """Show help."""
    print(__doc__)

def main():
    commands = {
        'status': cmd_status,
        'customers': cmd_customers,
        'purchases': cmd_purchases,
        'feedback': cmd_feedback,
        'users': cmd_users,
        'export': cmd_export,
        'backup': cmd_backup,
        'reset': cmd_reset,
        'help': cmd_help,
    }
    
    if len(sys.argv) < 2:
        cmd_status()
        print("Use 'python manage_db.py help' for more commands.")
        return
    
    command = sys.argv[1].lower()
    
    if command in commands:
        commands[command]()
    else:
        print(f"Unknown command: {command}")
        print("Use 'python manage_db.py help' for available commands.")
        sys.exit(1)

if __name__ == "__main__":
    main()
