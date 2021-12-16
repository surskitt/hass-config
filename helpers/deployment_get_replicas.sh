#!/usr/bin/env bash

if [[ "${#}" -lt 4 ]]; then
    echo "Error: missing arguments" >&2
    echo "Usage: ${0} NAMESPACE DEPLOYMENT TOKEN_FN CA_CERT_FN"
    exit 1
fi

NAMESPACE="${1}"
DEPLOYMENT="${2}"
TOKEN_FN="${3}"
CA_CERT_FN="${4}"

curl \
    -s \
    -k \
    -XGET \
    -H "Accept: application/json" \
    -H "Authorization: Bearer $(< "${TOKEN_FN}" )" \
    --cacert "${CA_CERT_FN}" \
    "https://192.168.2.5:6443/apis/apps/v1/namespaces/${NAMESPACE}/deployments/${DEPLOYMENT}" \
    | jq '.spec.replicas'
