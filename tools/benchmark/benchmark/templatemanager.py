class TemplateManager:
    def __init__(self, config_path):
        self.config_path = config_path

    def list_templates(self):
        print("Listing templates")

    def create_template(self, template_name):
        print(f"Creating template {template_name}")

    def delete_template(self, template_name):
        print(f"Deleting template {template_name}")

    def show_template(self, template_name):
        print(f"Showing template {template_name}")

    def handle_template(self, args):
        if args.template_verb == "list":
            self.list_templates()
        elif args.template_verb == "create":
            self.create_template(args.template_name)
        elif args.template_verb == "delete":
            self.delete_template(args.template_name)
        elif args.template_verb == "show":
            self.show_template(args.template_name)
