from celery import Celery
from flask import Flask\

def make_celery(app_name, broker_url, broker_backend_url):
    """
    Create and configure a Celery instance.
    """
            
    celery = Celery(app_name, broker=broker_url, backend=broker_backend_url)
    
    # Further configuration could go here if needed
    return celery

# Placeholder for the Celery instance; will be initialized properly in the application factory or main app module
celery = None

def init_celery(celery, app):
    """
    Initialize the Celery object by copying the Flask app's configuration and updating the Celery instance.
    """
    celery.conf.update(app.config)

