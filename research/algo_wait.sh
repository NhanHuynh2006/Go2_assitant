#!/bin/bash
t=$((SECONDS+160)); until ! pgrep -f "$1" >/dev/null || [ $SECONDS -gt $t ]; do sleep 5; done; pgrep -fc "$1"; date +%T
