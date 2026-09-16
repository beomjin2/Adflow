#!/usr/bin/env bash
# VM(team3-vm)에 백엔드 코드와 프론트 빌드를 올린다.
#
# 이 스크립트는 sudo를 쓰지 않는다. 서비스 재시작은 USER_COMMANDS.md 의 명령으로
# 사람이 직접 한다. 스크립트가 건드리는 건 아래 두 곳뿐이다:
#   backend/app/      (통째로 교체 — 지워진 파일이 실제로 사라져야 하므로)
#   frontend/         (빌드 산출물)
#
# 절대 건드리지 않는 것 — 지우면 복구할 수 없다:
#   backend/.env      사장님 API 키와 접속 정보
#   backend/app.db    실제 입력한 가게 정보·기록
#   backend/uploads/  사장님이 올린 사진
#   backend/media/    생성된 캐릭터 그림
#   backend/*.log
set -euo pipefail

VM=team3-vm
ZONE=us-east1-b
REMOTE_BASE=/home/sprint05/part4_3team
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"

say() { printf '\n== %s\n' "$*"; }

say "1/5  백엔드 app/ 묶는 중"
BACKEND_TGZ="/tmp/adflow-app-${STAMP}.tgz"
tar -C "$REPO/backend" \
    --exclude='__pycache__' --exclude='*.pyc' --exclude='.ipynb_checkpoints' \
    -czf "$BACKEND_TGZ" app
tar -C "$REPO/backend" -czf "/tmp/adflow-reqs-${STAMP}.tgz" requirements.txt
echo "   $(du -h "$BACKEND_TGZ" | cut -f1)"

say "2/5  프론트 dist/ 묶는 중"
if [ ! -f "$REPO/frontend/dist/index.html" ]; then
  echo "   dist가 없다. 먼저 'cd frontend && npm run build' 를 돌려라." >&2
  exit 1
fi
FRONT_TGZ="/tmp/adflow-dist-${STAMP}.tgz"
tar -C "$REPO/frontend/dist" -czf "$FRONT_TGZ" .
echo "   $(du -h "$FRONT_TGZ" | cut -f1)"

say "3/5  VM으로 전송"
gcloud compute scp --zone="$ZONE" "$BACKEND_TGZ" "$FRONT_TGZ" "${VM}:/tmp/"

say "4/5  백엔드 교체 (이전 app/ 은 app.bak-${STAMP} 로 남긴다)"
gcloud compute ssh "$VM" --zone="$ZONE" --command="
set -euo pipefail
cd ${REMOTE_BASE}/backend
[ -d app ] && mv app app.bak-${STAMP}
tar -xzf /tmp/$(basename "$BACKEND_TGZ")
# 생성 그림이 저장될 곳. 없으면 백엔드가 만들지만 권한을 미리 맞춰 둔다.
mkdir -p media uploads/store
echo '   배포된 라우터:' && ls app/api/routes
echo '   워크플로우:' && ls app/services/workflows
"

say "5/5  프론트 교체"
gcloud compute ssh "$VM" --zone="$ZONE" --command="
set -euo pipefail
cd ${REMOTE_BASE}
[ -d frontend ] && mv frontend frontend.bak-${STAMP}
mkdir -p frontend
tar -xzf /tmp/$(basename "$FRONT_TGZ") -C frontend
echo '   배포된 파일:' && ls frontend
"

say "끝났다. 다음은 사람이 해야 한다:"
cat <<'NEXT'
   sudo systemctl restart adflow-backend adflow-frontend

   재시작한 다음에 deploy/reset_service_data.py 를 돌려서 예전 데모 데이터를 지운다.
   (순서를 바꾸면 안 된다 — 옛 코드가 살아 있는 동안 지우면 다시 채워 넣는다.)
NEXT
