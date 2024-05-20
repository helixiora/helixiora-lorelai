#!/bin/bash

if [ "$1" == "--reset" ]; then
    mysql -u root -proot -e "DROP DATABASE IF EXISTS dragonfly;"
    mysql -u root -proot < ./db/create_dragonfly_schema.sql
fi

./dragonfly.py template create --template-name='test_template' --template-description='My first test template'
# a template contains at least:
# - the version of the code it's running against
# - the lorelai config file being used
# - a username/password to use
# - the questions file being used
# - the question classes being used
./dragonfly.py template add-parameter --template-id='1' --parameter-name='code_version' --parameter-type='string' --parameter-value='test_value'
./dragonfly.py template add-parameter --template-id='1' --parameter-name='lorelai_config' --parameter-type='string' --parameter-value='test_value'
./dragonfly.py template add-parameter --template-id='1' --parameter-name='user_details' --parameter-type='string' --parameter-value='test_value'
./dragonfly.py template add-parameter --template-id='1' --parameter-name='questions_file' --parameter-type='string' --parameter-value='test_value'
./dragonfly.py template add-parameter --template-id='1' --parameter-name='question_classes' --parameter-type='string' --parameter-value='test_value'

./dragonfly.py template list

./dragonfly.py template show --template-id='1'

./dragonfly.py benchmark prepare --template-id='1' --benchmark-name='test_benchmark' --benchmark-description='My first test benchmark'
