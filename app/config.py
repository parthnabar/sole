import os

basedir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(os.path.dirname(basedir), 'instance')


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(instance_dir, 'assistant.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
    CLAUDE_MODEL = os.environ.get('CLAUDE_MODEL', 'claude-sonnet-4-5-20250929')

    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')

    UPLOAD_FOLDER = os.path.join(os.path.dirname(basedir), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'pdf', 'txt', 'docx'}
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    SCHEDULER_API_ENABLED = False

    APP_USERNAME = os.environ.get('APP_USERNAME', 'admin')
    APP_PASSWORD = os.environ.get('APP_PASSWORD', 'admin')


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
