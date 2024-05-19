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
            cursor.execute("SELECT id, name, description FROM benchmark_template")
            for row in cursor:
                print(format_str.format(row["id"], row["name"], row["description"]))

        print(separator)

    def create_template(self, template_name, template_description):
        print(f"Creating template {template_name} ({template_description})")
        db = get_db_connection()
        with db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO benchmark_template (name, description) VALUES (%s, %s)",
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
                "SELECT COUNT(*) FROM benchmark_template_parameter WHERE benchmark_template_id = %s",
                (template_id,),
            )
            count = cursor.fetchone()[0]
            if count > 0:
                logging.error(
                    f"Template {template_id} has {count} parameters and cannot be deleted"
                )
                raise ValueError(
                    f"Template {template_id} has {count} parameters and cannot be deleted"
                )

            # check if the template has any runs
            cursor.execute(
                "SELECT COUNT(*) FROM benchmark_run WHERE benchmark_template_id = %s",
                (template_id,),
            )
            count = cursor.fetchone()[0]
            if count > 0:
                logging.error(f"Template {template_id} has {count} runs and cannot be deleted")
                raise ValueError(f"Template {template_id} has {count} runs and cannot be deleted")

            # delete the template
            cursor.execute("DELETE FROM benchmark_template WHERE id = %s", (template_id,))
            db.commit()

    def show_template(self, template_id):
        print(f"Showing template {template_id}")
        db = get_db_connection()
        with db.cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT name, description FROM benchmark_template WHERE id = %s", (template_id,)
            )
            row = cursor.fetchone()
            if row:
                print(f"Template Name: {row['name']}")
                print(f"Description: {row['description']}")

                # Fetch parameters
                cursor.execute(
                    "SELECT parameter, type, value FROM benchmark_template_parameter WHERE benchmark_template_id = %s",
                    (template_id,),
                )
                parameters = cursor.fetchall()
                if parameters:
                    print("Parameters:")
                    for parameter in parameters:
                        print(
                            f"  {parameter['parameter']} ({parameter['type']}) = {parameter['value']}"
                        )
                else:
                    print("No parameters defined")
            else:
                logging.error(f"Template {template_id} not found")

    def list_parameters(self, template_id):
        print(f"Listing parameters for template {template_id}")
        db = get_db_connection()
        with db.cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT parameter, type, value FROM benchmark_template_parameter WHERE benchmark_template_id = %s",
                (template_id,),
            )
            parameters = cursor.fetchall()
            if parameters:
                # Define the headers and format string
                headers = ("Parameter", "Type", "Value")
                format_str = "| {:<15} | {:<10} | {:<30} |"
                separator = "|-" + "-" * 15 + "-+-" + "-" * 10 + "-+-" + "-" * 30 + "-|"

                # Print headers and separator
                print(separator)
                print(format_str.format(*headers))
                print(separator)

                # Print parameters
                for parameter in parameters:
                    print(
                        format_str.format(
                            parameter["parameter"], parameter["type"], parameter["value"]
                        )
                    )

                print(separator)
            else:
                print("No parameters defined")

    def add_parameter(self, template_id, parameter_name, parameter_type, parameter_value):
        print(f"Adding parameter {parameter_name} to template {template_id}")
        db = get_db_connection()
        with db.cursor() as cursor:
            # check if the template exists
            cursor.execute("SELECT id FROM benchmark_template WHERE id = %s", (template_id,))
            if cursor.fetchone() is None:
                logging.error(f"Template {template_id} not found")
                raise ValueError(f"Template {template_id} not found")
            # check if the parameter already exists
            cursor.execute(
                "SELECT COUNT(*) FROM benchmark_template_parameter WHERE benchmark_template_id = %s AND parameter = %s",
                (template_id, parameter_name),
            )
            if cursor.fetchone()[0] > 0:
                logging.error(
                    f"Parameter {parameter_name} already exists for template {template_id}"
                )
                raise ValueError(
                    f"Parameter {parameter_name} already exists for template {template_id}"
                )
            cursor.execute(
                "INSERT INTO benchmark_template_parameter (benchmark_template_id, parameter, type, value) VALUES (%s, %s, %s, %s)",
                (template_id, parameter_name, parameter_type, parameter_value),
            )
            db.commit()

    def delete_parameter(self, template_id, parameter_name):
        print(f"Deleting parameter {parameter_name} from template {template_id}")
        db = get_db_connection()
        with db.cursor() as cursor:
            cursor.execute(
                "DELETE FROM benchmark_template_parameter WHERE benchmark_template_id = %s AND parameter = %s",
                (template_id, parameter_name),
            )
            db.commit()
