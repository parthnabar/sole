from flask_sqlalchemy import SQLAlchemy
from flask_apscheduler import APScheduler
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager

db = SQLAlchemy()
scheduler = APScheduler()
csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
