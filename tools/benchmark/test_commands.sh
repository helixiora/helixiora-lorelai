#!/bin/bash
set -e

# Define color codes
BLUE='\033[0;34m'
RED='\033[0;31m'
GREEN='\033[0;32m'
ORANGE='\033[0;33m'
GREY='\033[0;37m'
NC='\033[0m' # No Color

# Function to run a command and check its success
run_test() {
    local description=$1
    local command=$2

    echo -e "${BLUE}===> ${description}${NC}"
    echo -e "${GREY}Command: ${command}${NC}"
    eval $command

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}===> ${description} succeeded${NC}"
    else
        echo -e "${RED}===> ${description} failed${NC}"
        exit 1
    fi
}

# Function to run a command and expect failure
run_test_fail() {
    local description=$1
    local command=$2

    echo -e "${BLUE}===> ${description}${NC}"
    echo -e "${GREY}Command: ${command}${NC}"
    eval $command

    if [ $? -ne 0 ]; then
        echo -e "${GREEN}===> ${description} correctly failed${NC}"
    else
        echo -e "${RED}===> ${description} incorrectly succeeded${NC}"
        exit 1
    fi
}

# Reset the database if --reset flag is set
echo -e "${BLUE}===> 2. Resetting the database if --reset flag is set${NC}"
if [ "$1" == "--reset" ]; then
    echo -e "${ORANGE}===> 2.1 Resetting the database${NC}"
    mysql -u root -proot -e "DROP DATABASE IF EXISTS dragonfly;"
    mysql -u root -proot < ./db/create_dragonfly_schema.sql
fi

# Test the data commands
echo -e "${BLUE}==> 1. Testing data commands${NC}"
run_test "1.1 Testing data download" "./dragonfly.py data download --dry-run --path='/test/path'"
run_test "1.2 Testing data upload" "./dragonfly.py data upload --dry-run --path='/test/path'"

# Test the template commands
echo -e "${BLUE}===> 3. Testing template commands${NC}"
run_test "3.1 Testing template create" "./dragonfly.py template create --template-name='test_template' --template-description='My first test template'"
run_test "3.2 Testing template list" "./dragonfly.py template list"
run_test "3.3 Testing template show with existing ID" "./dragonfly.py template show --template-id='1'"
run_test "3.6 Testing template add-parameter" "./dragonfly.py template add-parameter --template-id='1' --parameter-name='test_param' --parameter-type='string' --parameter-value='test_value'"
# run_test_fail "3.4 Testing template delete while having parameters" "./dragonfly.py template delete --template-id='1'"
run_test "3.5 Testing template list-parameters" "./dragonfly.py template list-parameters --template-id='1'"
run_test "3.7 Testing template delete-parameter" "./dragonfly.py template delete-parameter --template-id='1' --parameter-name='test_param'"
run_test "3.4 Testing template delete" "./dragonfly.py template delete --template-id='1'"

# Test the benchmark commands
echo -e "${BLUE}===> 4. Testing benchmark commands${NC}"
run_test "4.1 Testing benchmark run" "./dragonfly.py benchmark run --dry-run --template-name='Benchmarking Run Test'"
run_test "4.2 Testing benchmark results" "./dragonfly.py benchmark results --benchmark-id='test_benchmark_id' --action='view'"

# Additional failure mode tests
echo -e "${BLUE}==> 5. Testing failure modes${NC}"
run_test_fail "5.1 Testing template create with missing parameters" "./dragonfly.py template create --template-name=''"
run_test_fail "5.2 Testing template create with wrong parameter values" "./dragonfly.py template create --template-name='test_template' --template-description=''"
run_test_fail "5.3 Testing template add-parameter with missing parameters" "./dragonfly.py template add-parameter --template-id='1' --parameter-name='' --parameter-type='string' --parameter-value='test_value'"
run_test_fail "5.4 Testing template add-parameter with wrong parameter type" "./dragonfly.py template add-parameter --template-id='1' --parameter-name='test_param' --parameter-type='unknown_type' --parameter-value='test_value'"
run_test_fail "5.5 Testing template delete-parameter with wrong parameter name" "./dragonfly.py template delete-parameter --template-id='1' --parameter-name='non_existing_param'"
run_test_fail "5.6 Testing benchmark run with wrong template name" "./dragonfly.py benchmark run --dry-run --template-name='NonExistingTemplate'"
run_test_fail "5.7 Testing benchmark results with wrong benchmark ID" "./dragonfly.py benchmark results --benchmark-id='non_existing_id' --action='view'"
run_test_fail "5.8 Testing template show with non-existing ID" "./dragonfly.py template show --template-id='0'"
