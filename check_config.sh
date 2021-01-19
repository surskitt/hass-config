#!/usr/bin/env bash

# simple script used to force a git pull in the home assistant container

kubectl -n home-assistant exec -it $(kubectl -n home-assistant get po -l app.kubernetes.io/name=home-assistant -o name -A) -c home-assistant -- hass -c . --script check_config
