#!/usr/bin/env bash

# following lines should be added directly on codeship setup code (not sure why..)
# jdk_switcher home oraclejdk8
# jdk_switcher use oraclejdk8

pip install --upgrade pip
pip install -r requirements.all.txt
scripts/setup_ci_environment.sh
