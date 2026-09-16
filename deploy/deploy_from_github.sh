#!/usr/bin/env bash
# VM 안에서 실행한다. GitHub의 main을 받아 백엔드 코드와 프론트 빌드를 제자리에 놓는다.
#
#   gcloud compute ssh team3-vm --zone=us-east1-b
#   bash deploy_from_github.sh
#
# sudo를 쓰지 않는다. 서비스 재시작은 이 스크립트가 끝난 뒤 사람이 한다.
#
# 절대 건드리지 않는 것 — 지우면 복구할 수 없다:
#   backend/.env  ·  backend/app.db  ·  backend/uploads/  ·  backend/media/  ·  *.log
set -euo pipefail

BASE=/home/sprint05/part4_3team
REPO=https://github.com/beomjin2/Adflow.git
BRANCH=main
STAMP="$(date +%Y%m%d-%H%M%S)"
WORK="/tmp/adflow-deploy-${STAMP}"

say() { printf '\n== %s\n' "$*"; }

say "1/4  main 받는 중"
git clone --depth 1 --branch "$BRANCH" "$REPO" "$WORK"
cd "$WORK"
echo "   $(git log --oneline -1)"

say "2/4  프론트 빌드"
cd "$WORK/frontend"
npm ci --no-audit --no-fund 2>&1 | tail -3 || npm install --no-audit --no-fund 2>&1 | tail -3
npm run build

say "3/4  백엔드 코드 교체 (이전 것은 app.bak-${STAMP} 로 남긴다)"
cd "$BASE/backend"
[ -d app ] && mv app "app.bak-${STAMP}"
cp -r "$WORK/backend/app" app
cp "$WORK/backend/requirements.txt" requirements.txt
cp "$WORK/deploy/reset_service_data.py" reset_service_data.py
mkdir -p media uploads/store
echo "   라우터: $(ls app/api/routes | tr '\n' ' ')"
echo "   워크플로우: $(ls app/services/workflows | tr '\n' ' ')"

say "4/4  프론트 교체 (이전 것은 frontend.bak-${STAMP} 로 남긴다)"
cd "$BASE"
[ -d frontend ] && mv frontend "frontend.bak-${STAMP}"
mkdir -p frontend
cp -r "$WORK/frontend/dist/." frontend/
echo "   $(ls frontend | tr '\n' ' ')"

say "파일 배치 끝. 이제 다음 두 가지를 순서대로 한다:"
cat <<NEXT

   1) 재시작
      sudo systemctl restart adflow-backend adflow-frontend
      systemctl is-active adflow-backend adflow-frontend

   2) 재시작한 뒤에 데모 데이터 지우기 (순서를 바꾸면 옛 코드가 다시 채워 넣는다)
      cd ${BASE}/backend
      python3 reset_service_data.py            # 먼저 무엇이 지워지는지 확인
      python3 reset_service_data.py --apply

   되돌리려면:
      cd ${BASE}/backend && rm -rf app && mv app.bak-${STAMP} app
      cd ${BASE} && rm -rf frontend && mv frontend.bak-${STAMP} frontend
      sudo systemctl restart adflow-backend adflow-frontend
NEXT
