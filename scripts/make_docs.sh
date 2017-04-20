#!/usr/bin/env bash

if which aglio; then
    aglio -i docs/_sources/index.apib -o docs/_build/index.html $*
else
    echo "aglio is required to make the docs, please install it"
    echo "  npm install -g aglio"
    exit 1
fi
