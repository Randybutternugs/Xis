"""
Tull Hydroponics Website - Main Entry Point
============================================

This is the main entry point for running the Flask application.

Local Development:
    python main.py
    or
    flask run

Google Cloud App Engine:
    The app is automatically started using this file as the entry point.
    Deploy with: gcloud app deploy

Environment Variables:
    See app.yaml for required environment variables.
    For local development, create a vars.env file with the same variables.
"""

from xissite import create_app

# Create the Flask application instance
app = create_app()

if __name__ == '__main__':
    # Run in debug mode for local development only
    # In production (Google Cloud), debug is automatically disabled
    import os
    
    debug_mode = os.environ.get('FLASK_ENV', 'development') == 'development'
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 60)
    print("TULL HYDROPONICS - Development Server")
    print("=" * 60)
    print(f"Running on: http://localhost:{port}")
    print(f"Debug mode: {debug_mode}")
    print("=" * 60)
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug_mode
    )
