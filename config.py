"""Configuration for the Flask app."""

import os
from datetime import timedelta

from dotenv import load_dotenv

from lorelai.utils import get_embedding_dimension

load_dotenv()


class Config:
    """Base configuration class."""

    FLASK_ENV = os.environ.get("FLASK_ENV")

    # Secret key for signing cookies
    SECRET_KEY = os.environ.get("SECRET_KEY")

    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)  # Session expires after 1 day
    SESSION_COOKIE_SECURE = True  # Only send cookie over HTTPS
    SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookie
    SESSION_COOKIE_SAMESITE = "Lax"  # CSRF protection

    # SQLAlchemy settings
    SQLALCHEMY_DATABASE_URI = os.environ.get("SQLALCHEMY_DATABASE_URI")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Flask-JWT-Extended settings
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or "super-secret"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"

    # Application settings
    APP_NAME = "Lorelai"
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")

    # Logging
    LOG_TO_STDOUT = os.environ.get("LOG_TO_STDOUT", "false").lower() in ["true", "on", "1"]
    LOG_LEVEL = os.environ.get("LOG_LEVEL")

    # Sentry settings
    SENTRY_DSN = os.environ.get("SENTRY_DSN")

    # Google settings
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_PROJECT_ID = os.environ.get("GOOGLE_PROJECT_ID")
    GOOGLE_APP_ID = GOOGLE_CLIENT_ID.split("-")[0]  # app id is everything before the first dash
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

    # Pinecone settings
    PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
    PINECONE_REGION = os.environ.get("PINECONE_REGION")
    PINECONE_METRIC = os.environ.get("PINECONE_METRIC", "cosine")
    PINECONE_DIMENSION = int(os.environ.get("PINECONE_DIMENSION", 1536))

    # OpenAI settings
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL")

    # Redis settings
    REDIS_URL = os.environ.get("REDIS_URL")
    REDIS_QUEUE_INDEXER = os.environ.get("REDIS_QUEUE_INDEXER", "indexer_queue")
    REDIS_QUEUE_QUESTION = os.environ.get("REDIS_QUEUE_QUESTION", "question_queue")
    REDIS_QUEUE_DEFAULT = os.environ.get("REDIS_QUEUE_DEFAULT", "default")

    # Lorelai settings
    LORELAI_ENVIRONMENT = os.environ.get("LORELAI_ENVIRONMENT")
    LORELAI_ENVIRONMENT_SLUG = os.environ.get("LORELAI_ENVIRONMENT_SLUG")
    LORELAI_REDIRECT_URI = os.environ.get("LORELAI_REDIRECT_URI")
    LORELAI_MODEL_TYPE = os.environ.get("LORELAI_MODEL_TYPE")
    LORELAI_CHAT_TASK_TIMEOUT = int(os.environ.get("LORELAI_CHAT_TASK_TIMEOUT"))
    LORELAI_SUPPORT_PORTAL = os.environ.get("LORELAI_SUPPORT_PORTAL")
    LORELAI_SUPPORT_EMAIL = os.environ.get("LORELAI_SUPPORT_EMAIL")
    LORELAI_RERANKER = os.environ.get("LORELAI_RERANKER")

    # Embeddings settings
    EMBEDDINGS_MODEL = os.environ.get("EMBEDDINGS_MODEL")
    EMBEDDINGS_CHUNK_SIZE = int(os.environ.get("EMBEDDINGS_CHUNK_SIZE"))
    EMBEDDINGS_DIMENSION = get_embedding_dimension(EMBEDDINGS_MODEL)

    # SendGrid settings
    SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
    SENDGRID_INVITE_TEMPLATE_ID = os.environ.get("SENDGRID_INVITE_TEMPLATE_ID")

    # Database settings
    DB_HOST = os.environ.get("DB_HOST")
    DB_PORT = int(os.environ.get("DB_PORT", 3306))
    DB_USER = os.environ.get("DB_USER")
    DB_NAME = os.environ.get("DB_NAME")
    DB_PASSWORD = os.environ.get("DB_PASSWORD")

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
        "SLACK_SCOPES", "channels:history,channels:read,groups:read,users:read,users:read.email"
    )

    # LLM Sherpa configuration
    LLMSHERPA_API_URL = os.getenv(
        "LLMSHERPA_API_URL", "http://localhost:5010/api/parseDocument?renderFormat=all"
    )

    @classmethod
    def init_app(cls, app):
        """Initialize the configuration for the Flask app."""
        pass


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = False


class TestingConfig(Config):
    """Testing configuration."""

    TESTING = True


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
