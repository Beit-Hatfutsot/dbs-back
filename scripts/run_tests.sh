#!/usr/bin/env bash

py.test tests/ bhs_api/ --cov=bhs_api --cov=scripts --cov=migration --cov-report=term --cov-report=html
echo "you can inspect the coverage report in your browser:"
echo "  google-chrome ./htmlcov/index.html"
