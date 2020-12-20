#!/usr/bin/env bash

# simple script used to force a git pull in the home assistant container

kubectl exec -it $(kubectl get po -l app.kubernetes.io/name=home-assistant -o name -A) -c home-assistant -- git pull --ff -X theirs
