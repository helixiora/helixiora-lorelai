#!/bin/bash
set -e

# Test the data commands
echo "===> Testing data commands"
./dragonfly.py data download --dry-run --path="/test/path"

./dragonfly.py data upload --dry-run --path="/test/path"

echo "===> Resetting the database  if --reset flag is set"
if [ "$1" == "--reset" ]; then
    echo "===> Resetting the database"
    mysql -u root -proot -e "DROP DATABASE IF EXISTS dragonfly;"
    mysql -u root -proot < ./db/create_dragonfly_schema.sql
fi

# Test the template commands
echo "===> Testing template commands"

./dragonfly.py template create --template-name="test_template" --template-description="My first test template"

./dragonfly.py template list

./dragonfly.py template show --template-id="test_template_id"

# exit
exit 0

echo "===> Testing template commands"
./dragonfly.py template delete --template-id="test_template_id"
./dragonfly.py template list-parameters --template-id="test_template_id"
./dragonfly.py template add-parameter --template-id="test_template_id" --parameter-name="test_param" --parameter-type="string" --parameter-value="test_value"
./dragonfly.py template delete-parameter --template-id="test_template_id" --parameter-name="test_param"

# Test the benchmark commands
./dragonfly.py benchmark run --dry-run --template-name="Benchmarking Run Test"

./dragonfly.py benchmark results --benchmark-id="test_benchmark_id" --action="view"
