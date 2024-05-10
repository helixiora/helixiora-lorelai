class BenchmarkManager:
    def __init__(self, config_path):
        self.config_path = config_path

    def run(self, template_name, description, dry_run):
        print(f"Running benchmark with template {template_name} and description {description}")

    def view_results(self, benchmark_id):
        print(f"Viewing results for benchmark {benchmark_id}")

    def delete_results(self, benchmark_id):
        print(f"Deleting results for benchmark {benchmark_id}")
