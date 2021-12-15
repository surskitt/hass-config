#!/usr/bin/env bash

if [[ "${#}" -lt 5 ]]; then
    echo "Error: missing arguments" >&2
    echo "Usage: ${0} NAMESPACE DEPLOYMENT REPLICAS TOKEN_FN CA_CERT_FN"
    exit 1
fi

NAMESPACE="${1}"
DEPLOYMENT="${2}"
REPLICAS="${3}"
TOKEN_FN="${4}"
CA_CERT_FN="${5}"

curl \
    -v \
    -XPATCH \
    -H "Accept: application/json, */*" \
    -H "Content-Type: application/merge-patch+json" \
    -H "Authorization: Bearer $(< "${TOKEN_FN}" )" \
    --cacert "${CA_CERT_FN}" \
    --data-binary "{\"spec\":{\"replicas\": ${REPLICAS}}}" \
    "https://192.168.2.5:6443/apis/apps/v1/namespaces/${NAMESPACE}/deployments/${DEPLOYMENT}/scale"
