#!/bin/sh
# NAS에서 앱을 끕니다.
cd "$(dirname "$0")" || exit 1

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1 \
  && docker ps -a --format '{{.Names}}' | grep -qx work-worksheet; then
  if docker compose version >/dev/null 2>&1; then
    docker compose down
  else
    docker-compose down
  fi
  echo "껐습니다."
  exit 0
fi

if [ -f app.pid ] && kill -0 "$(cat app.pid)" 2>/dev/null; then
  kill "$(cat app.pid)"
  rm -f app.pid
  echo "껐습니다."
else
  echo "켜져 있는 앱이 없습니다."
fi
