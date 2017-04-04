#!/usr/bin/env bash

pip install -r requirements.all.txt
jdk_switcher home oraclejdk8
jdk_switcher use oraclejdk8
scripts/setup_ci_environment.sh
