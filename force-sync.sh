#!/usr/bin/env bash

# simple script used to force a git pull in the home assistant container

kubectl exec -it $(kubectl get po -l app.kubernetes.io/name=home-assistant -o name -A) -c home-assistant -- git fetch
kubectl exec -it $(kubectl get po -l app.kubernetes.io/name=home-assistant -o name -A) -c home-assistant -- git reset --hard HEAD
kubectl exec -it $(kubectl get po -l app.kubernetes.io/name=home-assistant -o name -A) -c home-assistant -- git merge '@{u}'
