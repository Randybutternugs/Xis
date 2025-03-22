# Run this file once to initialize the database
from xissite import create_app, db

app = create_app()
with app.app_context():
    db.create_all()
    print("All tables created successfully!")