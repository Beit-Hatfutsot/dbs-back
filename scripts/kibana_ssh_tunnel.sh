#!/usr/bin/env bash

gcloud compute ssh mongo1-dev -- -L 25601:localhost:5601
