import logging
import os
import sys

sys.path.insert(1, os.path.join(os.path.dirname(__file__), "../../.."))
from lorelai.utils import load_config, get_db_connection  # noqa E402


class TemplateManager:
    def __init__(self):
        self.config = load_config("dragonfly")

    def list_templates(self):
        # Define the headers and format string
        headers = ("Template ID", "Template Name", "Description")
        format_str = "| {:<12} | {:<15} | {:<30} |"
        separator = "|-" + "-" * 12 + "-+-" + "-" * 15 + "-+-" + "-" * 30 + "-|"

        # Print headers and separator
        print(separator)
        print(format_str.format(*headers))
        print(separator)

        # Fetch data from the database
        db = get_db_connection()
        with db.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT id, templatename, description FROM benchmark_template")
            for row in cursor:
                print(format_str.format(row["id"], row["templatename"], row["description"]))

        print(separator)

    def create_template(self, template_name, template_description):
        print(f"Creating template {template_name} ({template_description})")
        db = get_db_connection()
        with db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO benchmark_template (templatename, description) VALUES (%s, %s)",
                (template_name, template_description),
            )
            db.commit()
        print(f"Template {template_name} created")

    def delete_template(self, template_id):
        print(f"Deleting template {template_id}")
        db = get_db_connection()
        with db.cursor() as cursor:
            # check if the template has any parameters
            cursor.execute(
                "SELECT COUNT(*) FROM benchmark_parameter WHERE template = %s", (template_id,)
            )
            count = cursor.fetchone()[0]
            if count > 0:
                logging.error(
                    f"Template {template_id} has {count} parameters and cannot be deleted"
                )
                return

            # check if the template has any runs
            cursor.execute("SELECT COUNT(*) FROM benchmark_run WHERE template = %s", (template_id,))
            count = cursor.fetchone()[0]
            if count > 0:
                logging.error(f"Template {template_id} has {count} runs and cannot be deleted")
                return

            # delete the template
            cursor.execute("DELETE FROM benchmark_template WHERE template = %s", (template_id,))
            db.commit()

    def show_template(self, template_id):
        print(f"Showing template {template_id}")
        db = get_db_connection()
        with db.cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT * FROM benchmark_template WHERE templatename = %s", (template_id,)
            )
            row = cursor.fetchone()
            if row:
                print(f"Template Name: {row['templatename']}")
                print(f"Description: {row['description']}")

                # Fetch parameters
                cursor.execute(
                    "SELECT * FROM benchmark_parameter WHERE templatename = %s", (template_id,)
                )
                parameters = cursor.fetchall()
                if parameters:
                    print("Parameters:")
                    for parameter in parameters:
                        print(
                            f"  {parameter['parametername']} ({parameter['parametertype']}) = {parameter['parametervalue']}"
                        )
                else:
                    print("No parameters defined")
            else:
                logging.error(f"Template {template_id} not found")

    def list_parameters(self, template_name):
        print(f"Listing parameters for template {template_name}")
        logging.error("Not implemented")
        sys.exit(1)

    def add_parameter(self, template_name, parameter_name, parameter_type, parameter_value):
        print(f"Adding parameter {parameter_name} to template {template_name}")
        logging.error("Not implemented")
        sys.exit(1)

    def delete_parameter(self, template_name, parameter_name):
        print(f"Deleting parameter {parameter_name} from template {template_name}")
        logging.error("Not implemented")
        sys.exit(1)
