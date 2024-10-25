"""Configuration for the Flask app."""

from lorelai.utils import get_embedding_dimension

import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration class."""

    # Secret key for signing cookies
    SECRET_KEY = os.environ.get("SECRET_KEY") or "you-will-never-guess"

    # SQLAlchemy settings
    SQLALCHEMY_DATABASE_URI = os.environ.get("SQLALCHEMY_DATABASE_URI")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Flask-JWT-Extended settings
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or "super-secret"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_COOKIE_SECURE = True
    JWT_COOKIE_SAMESITE = "Strict"
    JWT_COOKIE_HTTPONLY = True
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_COOKIE_CSRF_PROTECT = False
    JWT_CSRF_CHECK_FORM = False
    JWT_ACCESS_CSRF_COOKIE_NAME = "csrf_token"
    JWT_REFRESH_CSRF_COOKIE_NAME = "csrf_token"
    JWT_COOKIE_DOMAIN = None
    JWT_COOKIE_PATH = "/"

    # Application settings
    APP_NAME = "Lorelai"
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")

    # Logging
    LOG_TO_STDOUT = os.environ.get("LOG_TO_STDOUT", "false").lower() in ["true", "on", "1"]
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

    # Sentry settings
    SENTRY_DSN = os.environ.get("SENTRY_DSN")
    SENTRY_ENVIRONMENT = os.environ.get("SENTRY_ENVIRONMENT", "production")

    # Google settings
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_PROJECT_ID = os.environ.get("GOOGLE_PROJECT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

    # Pinecone settings
    PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
    PINECONE_REGION = os.environ.get("PINECONE_REGION")
    PINECONE_METRIC = os.environ.get("PINECONE_METRIC", "cosine")
    PINECONE_DIMENSION = int(os.environ.get("PINECONE_DIMENSION", 1536))

    # OpenAI settings
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    # Redis settings
    REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")

    # Lorelai settings
    LORELAI_ENVIRONMENT = os.environ.get("LORELAI_ENVIRONMENT", "dev")
    LORELAI_ENVIRONMENT_SLUG = os.environ.get("LORELAI_ENVIRONMENT_SLUG")
    LORELAI_REDIRECT_URI = os.environ.get("LORELAI_REDIRECT_URI")
    LORELAI_MODEL_TYPE = os.environ.get("LORELAI_MODEL_TYPE", "OpenAILlm")
    LORELAI_CHAT_TASK_TIMEOUT = int(os.environ.get("LORELAI_CHAT_TASK_TIMEOUT", 600))
    LORELAI_SUPPORT_PORTAL = os.environ.get(
        "LORELAI_SUPPORT_PORTAL", "https://support.helixiora.com/support/solutions/201000092447"
    )
    LORELAI_SUPPORT_EMAIL = os.environ.get("LORELAI_SUPPORT_EMAIL", "support@helixiora.com")
    LORELAI_RERANKER = os.environ.get("LORELAI_RERANKER", "ms-marco-TinyBERT-L-2-v2")

    # Embeddings settings
    EMBEDDINGS_MODEL = os.environ.get("EMBEDDINGS_MODEL", "text-embedding-3-small")
    EMBEDDINGS_DIMENSION = get_embedding_dimension(EMBEDDINGS_MODEL)
    # EMBEDDINGS_DIMENSION = os.environ.get("EMBEDDINGS_DIMENSION", 1536)
    EMBEDDINGS_CHUNK_SIZE = int(os.environ.get("EMBEDDINGS_CHUNK_SIZE", 4000))
    EMBEDDINGS_DIMENSION = int(os.environ.get("EMBEDDINGS_DIMENSION", 1536))

    # SendGrid settings
    SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
    SENDGRID_INVITE_TEMPLATE_ID = os.environ.get("SENDGRID_INVITE_TEMPLATE_ID")

    # Database settings
    DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.environ.get("DB_PORT", 3306))
    DB_USER = os.environ.get("DB_USER", "root")
    DB_NAME = os.environ.get("DB_NAME", "lorelai_test")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "root")

    # Feature flags
    FEATURE_SLACK = os.environ.get("FEATURE_SLACK", "1") == "1"
    FEATURE_GOOGLE_DRIVE = os.environ.get("FEATURE_GOOGLE_DRIVE", "1") == "1"

    # Slack settings
    SLACK_CLIENT_ID = os.environ.get("SLACK_CLIENT_ID")
    SLACK_CLIENT_SECRET = os.environ.get("SLACK_CLIENT_SECRET")
    SLACK_REDIRECT_URI = os.environ.get("SLACK_REDIRECT_URI")
    SLACK_AUTHORIZATION_URL = os.environ.get(
        "SLACK_AUTHORIZATION_URL", "https://slack.com/oauth/v2/authorize"
    )
    SLACK_TOKEN_URL = os.environ.get("SLACK_TOKEN_URL", "https://slack.com/api/oauth.v2.access")
    SLACK_SCOPES = os.environ.get(
        "SLACK_SCOPES",
        "channels:history,channels:read,users:read,users:read.email",
    )

    @classmethod
    def init_app(cls, app):
        """Initialize the configuration for the Flask app."""
        pass


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True


class TestingConfig(Config):
    """Testing configuration."""

    TESTING = True
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    """Production configuration."""

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")

    @classmethod
    def init_app(cls, app):
        """Initialize the configuration for the Flask app."""
        Config.init_app(app)

        # Log to stderr
        import logging
        from logging import StreamHandler

        file_handler = StreamHandler()
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)


# Dictionary to easily access different configurations
config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
