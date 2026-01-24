"""
Database Initialization Script
==============================

Run this script once to initialize the database tables.

Usage:
    python init_db.py
    
    or from the project root:
    python -c "from xissite import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"

Note:
    For Google Cloud App Engine with SQLite, the database will be
    recreated on each instance restart since /tmp is ephemeral.
    For persistent data, consider using Cloud SQL.
"""

from xissite import create_app, db

def init_database():
    """Initialize all database tables."""
    app = create_app()
    with app.app_context():
        db.create_all()
        print("=" * 50)
        print("Database initialized successfully!")
        print("=" * 50)
        print("\nTables created:")
        print("  - user (admin authentication)")
        print("  - customer (customer information)")
        print("  - purchase_info (purchase records)")
        print("  - feed_back (customer feedback)")
        print("\nYou can now run the application with:")
        print("  flask run")
        print("  or")
        print("  python main.py")


if __name__ == "__main__":
    init_database()
