#!/usr/bin/env bash

if [[ "${#}" -lt 1 ]]; then
    echo "Error: a file/uri argument must be pased" >&2
    exit 1
fi

FILE_URI="${1}"

current_position="$(curl -s -X GET "http://forked-daapd.media.svc.cluster.local:3689/api/queue?id=now_playing"|jq -r '.items[0].position')"
next_position="$(( current_position + 1))"

curl -s -X POST "http://forked-daapd.media.svc.cluster.local:3689/api/queue/items/add?uris=${FILE_URI}&position=${next_position}&playback=start&playback_from_position=${next_position}" >/dev/null
