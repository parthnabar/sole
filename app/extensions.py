from flask_sqlalchemy import SQLAlchemy
from flask_apscheduler import APScheduler
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
scheduler = APScheduler()
csrf = CSRFProtect()
