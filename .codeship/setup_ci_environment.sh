#!/usr/bin/env bash

pip install -r requirements.txt
pip install -r requirements.migrate.txt
pip install pymssql==2.1.3
jdk_switcher home oraclejdk8
jdk_switcher use oraclejdk8
scripts/setup_ci_environment.sh
