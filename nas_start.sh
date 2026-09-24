#!/bin/sh
# NAS에서 앱을 켭니다. 한 번만 실행하면 되고, 창을 닫아도 계속 켜져 있습니다.
#   Docker가 있으면 Docker로, 없으면 Python으로 실행합니다.
#   다시 실행하면 최신 파일로 새로 켭니다.
cd "$(dirname "$0")" || exit 1
mkdir -p output saved_layouts

PORT=8501
LOG=app.log
PID_FILE=app.pid

# NAS 아이피를 찾아 접속 주소를 알려준다.
show_address() {
  ip_addr=$(hostname -I 2>/dev/null | awk '{print $1}')
  [ -z "$ip_addr" ] && ip_addr="NAS아이피"
  echo ""
  echo "켜졌습니다. 다른 PC 브라우저에서 접속하세요:"
  echo "  http://$ip_addr:$PORT"
}

# 1) Docker 방식
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  echo "Docker로 실행합니다. 처음에는 몇 분 걸립니다..."
  if docker compose version >/dev/null 2>&1; then
    docker compose up -d --build || exit 1
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose up -d --build || exit 1
  else
    echo "[오류] docker compose 를 찾을 수 없습니다."
    exit 1
  fi
  show_address
  exit 0
fi

# 2) Python 방식
PY=""
for cand in python3.12 python3.11 python3.10 python3; do
  if command -v "$cand" >/dev/null 2>&1 \
    && "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    PY="$cand"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "[오류] Docker도 없고 Python 3.10 이상도 없습니다."
  echo "NAS 패키지 센터에서 Container Manager(Docker) 또는 Python 3를 설치하세요."
  exit 1
fi

# 이전에 켜 둔 앱이 있으면 끈다.
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  kill "$(cat "$PID_FILE")" 2>/dev/null
  sleep 2
fi

if [ ! -x "venv/bin/python" ]; then
  echo "처음 실행이라 필요한 프로그램을 설치합니다. 몇 분 걸립니다..."
  "$PY" -m venv venv || { echo "[오류] venv 를 만들 수 없습니다."; exit 1; }
fi

# requirements.txt 가 바뀌었을 때만 다시 설치한다.
if ! cmp -s requirements.txt venv/.installed_requirements 2>/dev/null; then
  ./venv/bin/python -m pip install --upgrade pip >/dev/null
  ./venv/bin/python -m pip install -r requirements.txt || { echo "[오류] 설치 실패. 인터넷 연결을 확인하세요."; exit 1; }
  cp requirements.txt venv/.installed_requirements
fi

export WORKSHEET_SERVER=1
export TZ=Asia/Seoul
nohup ./venv/bin/python -m streamlit run app.py >"$LOG" 2>&1 &
echo $! >"$PID_FILE"

sleep 5
if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  show_address
  echo "(기록: $LOG / 끄기: ./nas_stop.sh)"
else
  echo "[오류] 앱이 바로 꺼졌습니다. $LOG 내용을 확인하세요:"
  tail -n 20 "$LOG"
  exit 1
fi
