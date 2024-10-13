"""Datasource related helper functions."""

import logging

from app.models import Datasource

# List of datasource names
DATASOURCE_GOOGLE_DRIVE = "Google Drive"
DATASOURCE_SLACK = "Slack"


def get_datasource_id_by_name(datasource_name: str):
    """Get the datasource ID by name."""
    if datasource_name not in [DATASOURCE_GOOGLE_DRIVE, DATASOURCE_SLACK]:
        raise ValueError(f"Invalid datasource name: {datasource_name}")

    datasource_name_result = Datasource.query.filter_by(datasource_name=datasource_name).first()
    if datasource_name_result:
        return datasource_name_result.datasource_id

    return None


def get_datasources_name():
    """Get the list of datasources from datasource table."""
    try:
        datasources = Datasource.query.all()
        return [datasource.datasource_name for datasource in datasources]
    except Exception:
        logging.critical("No datasources in datasources table")
        raise ValueError("No datasources in datasources table") from None
