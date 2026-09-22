import os

class Config:
    """Base config"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'workai-dev-secret-change-in-production')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'workai-jwt-secret-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = 60 * 60 * 24 * 7  # 7 days

    # Database
    # Render က DATABASE_URL ကို auto set လုပ်တယ်
    # Local အတွက် SQLite
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///workai.db'
    )
    # Render က postgres:// ပေးတယ် — SQLAlchemy က postgresql:// လိုတယ်
    if SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            'postgres://', 'postgresql://', 1
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # CORS
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')

    # App
    APP_NAME = 'WorkAI'
    APP_VERSION = '4.0.0'
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
