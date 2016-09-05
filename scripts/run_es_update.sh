#!/bin/bash -e

# For the first run:
# - populate .ssh with bhs keys
# - virtualenv ~/venv
# - sudo apt-get install -y libffi-dev libjpeg62 libjpeg62-dev zlib1g-dev libssl-dev python-dev

branch=alpha2
base=`dirname $0`

echo "Running mongo --> ES dump"
cd $base
git pull && \
git checkout $branch && \
source ~/venv/bin/activate && \
pip install -q --upgrade "setuptools>=18.7" && \
pip install -q --upgrade -r requirements.txt && \
./dump_mongo_to_es.py
