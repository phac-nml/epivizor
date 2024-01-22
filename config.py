import secrets
import datetime

class ConfigDebug(object):
    TESTING = True
    DEBUG = True
    FLASK_ENV = 'development'
    SECRET_KEY=secrets.token_urlsafe(16)
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = datetime.timedelta(hours = 24)

class ProductionConfig(object):
    DEVELOPMENT = False
    DEBUG = False
    SECRET_KEY=secrets.token_urlsafe(16)
    SESSION_PERMANENT = False
    