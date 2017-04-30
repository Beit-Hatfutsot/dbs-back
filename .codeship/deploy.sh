#!/usr/bin/env bash

if [ "${1}" == "" ]; then
    echo "usage:"
    echo ".codeship/deploy.sh <host>"
else
    fab -H "${1}" deploy
fi
