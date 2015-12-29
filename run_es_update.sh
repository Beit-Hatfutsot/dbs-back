#!/bin/bash -e

branch=dev
base=`dirname $0`

echo "Running mongo --> ES dump"
cd $base
git pull && \
git checkout $branch && \
source ~/venv/bin/activate && \
pip install -q --upgrade "setuptools>=18.7" && \
pip install -q --upgrade -r requirements.txt && \
./dump_mongo_to_es.py
