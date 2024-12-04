"""
Sentry settings for RQ workers.

This module initializes Sentry for use with RQ workers.
It dynamically loads the configuration based on the `ENVIRONMENT`
environment variable or defaults to the development configuration.
run rq with "rq worker --with-scheduler -c sentrysettings_rq indexer_queue question_queue default"
"""

import os
import sentry_sdk
from config import config
from dotenv import load_dotenv

load_dotenv()
config_name = os.getenv("ENVIRONMENT", "development")
current_config = config[config_name]
sentry_sdk.init(
    dsn=current_config.SENTRY_DSN,
    environment=current_config.SENTRY_ENVIRONMENT,
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)
