# ============================================
# BANTU HALII - PROCFILE
# Render Deployment Configuration
# ============================================

# Web Service - Main Application
web: gunicorn app:app --worker-class eventlet --workers 1 --bind 0.0.0.0:$PORT --timeout 120 --keep-alive 5 --max-requests 1000 --max-requests-jitter 50 --log-level info --access-logfile - --error-logfile -

# Alternative using socketio with gunicorn
# web: gunicorn app:app --worker-class eventlet --workers 1 --bind 0.0.0.0:$PORT

# Alternative using direct socketio run (development)
# web: python app.py

# Background Worker for cleanup tasks (optional)
# worker: celery -A app.celery worker --loglevel=info --concurrency=2

# Beat Scheduler for periodic tasks (optional)
# beat: celery -A app.celery beat --loglevel=info

# ============================================
# NOTES FOR RENDER DEPLOYMENT:
# ============================================
# 
# 1. Build Command (set in Render dashboard):
#    pip install -r requirements.txt
#
# 2. Start Command (set in Render dashboard):
#    gunicorn app:app --worker-class eventlet --workers 1 --bind 0.0.0.0:$PORT
#
# 3. Environment Variables needed:
#    - SECRET_KEY
#    - DATABASE_URL (PostgreSQL 18)
#    - CLOUDINARY_CLOUD_NAME
#    - CLOUDINARY_API_KEY
#    - CLOUDINARY_API_SECRET
#    - FLASK_ENV=production
#    - PORT (auto-set by Render)
#
# 4. Web Service Type: Web Service
# 5. Runtime: Python 3.11+
# 6. Build Command: pip install -r requirements.txt
# 7. Health Check Path: /health
