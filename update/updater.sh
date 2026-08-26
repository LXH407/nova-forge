#!/bin/sh
NEW="$1"
TARGET="$2"
sleep 3
pkill -f NovaForge 2>/dev/null
sleep 1
mv -f "$NEW" "$TARGET" 2>/dev/null || cp -f "$NEW" "$TARGET"
chmod +x "$TARGET"
( "$TARGET" & )
rm -f "$0"
exit 0
