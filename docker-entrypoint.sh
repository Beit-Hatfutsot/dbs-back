#!/bin/sh

# wait for dependencies
sleep 2

if [ "${1}" == "" ]; then
    python scripts/runserver.py
else
    /bin/sh -c "$*"
fi
