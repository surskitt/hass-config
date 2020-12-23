#!/usr/bin/env bash

if [[ "${#@}" -eq 0 ]]; then
    echo "Usage: ${0} FILE"
    exit 1
fi

F="${1}"

POD=$(kubectl -n home-assistant get po -l app.kubernetes.io/name=home-assistant -o jsonpath="{.items[0].metadata.name}" -A)

kubectl -n home-assistant cp "${F}" "${POD}:${F}" -c home-assistant
