"""Datasource related helper functions."""

import logging

from app.helpers.database import get_db_connection, get_query_result


def get_datasource_id_by_name(datasource_name: str):
    """Get the organization name by ID."""
    datasource_name_result = get_query_result(
        "SELECT datasource_id FROM datasource WHERE datasource_name = %s",
        (datasource_name,),
        fetch_one=True,
    )
    if datasource_name_result:
        return datasource_name_result["datasource_id"]

    return None


def get_datasources_name():
    """Get the list of datasources from datasource table."""
    with get_db_connection() as db:
        try:
            cursor = db.cursor()
            query = """
                SELECT datasource.datasource_name
                FROM datasource;
            """
            cursor.execute(query)
            datasources = cursor.fetchall()
            datasources = [source[0] for source in datasources]
            return datasources

        except Exception:
            logging.critical("No datasources in datasources table")
            raise ValueError("No datasources in datasources table") from None
        finally:
            cursor.close()
            db.close()
