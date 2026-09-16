#!/usr/bin/env bash
# VM 안에서 실행한다. main을 받아 백엔드 코드와 프론트 빌드를 제자리에 놓는다.
#
#   gcloud compute ssh team3-vm --zone=us-east1-b
#   bash /home/sprint05/part4_3team/deploy.sh
#
# 처음 한 번만 clone하고, 그다음부터는 git pull만 한다. 체크아웃은
# /home/sprint05/part4_3team/.src 에 남는다.
#
# 왜 체크아웃을 그대로 서비스 디렉터리로 쓰지 않나:
#   서빙 중인 frontend/ 는 빌드 결과물(assets/, index.html)이고, 저장소의 frontend/ 는
#   소스다. 저장소를 그 자리에 두면 http.server가 빌드 안 된 /src/main.jsx를 내보낸다.
#   그래서 .src 에서 빌드하고 결과만 옮긴다. backend/app 은 그냥 복사해도 되지만,
#   운영 디렉터리에 .git 을 두면 .env 와 app.db 가 git 관리 대상처럼 보여서 위험하다.
#
# sudo를 쓰지 않는다. 서비스 재시작은 이 스크립트가 끝난 뒤 사람이 한다.
#
# 절대 건드리지 않는 것 — 지우면 복구할 수 없다:
#   backend/.env  ·  backend/app.db  ·  backend/uploads/  ·  backend/media/  ·  *.log
set -euo pipefail

BASE=/home/sprint05/part4_3team
SRC="$BASE/.src"
REPO=https://github.com/beomjin2/Adflow.git
BRANCH=main
STAMP="$(date +%Y%m%d-%H%M%S)"

say() { printf '\n== %s\n' "$*"; }

say "1/4  main 가져오기"
if [ -d "$SRC/.git" ]; then
  git -C "$SRC" fetch --quiet origin "$BRANCH"
  # reset --hard: VM에서 급히 고친 게 있어도 저장소 내용이 이긴다.
  # 운영에 필요한 파일은 .src 밖에 있으니 여기서 잃을 건 없다.
  git -C "$SRC" reset --hard --quiet "origin/$BRANCH"
  echo "   pull 완료"
else
  rm -rf "$SRC"
  git clone --quiet --branch "$BRANCH" "$REPO" "$SRC"
  echo "   처음이라 clone 했다 — 다음부터는 pull만 한다"
fi
echo "   $(git -C "$SRC" log --oneline -1)"

say "2/4  프론트 빌드"
cd "$SRC/frontend"
# package-lock.json이 그대로면 설치를 건너뛴다. npm ci가 이 스크립트에서 제일 느리다.
LOCK_NOW="$(sha1sum package-lock.json | cut -d' ' -f1)"
LOCK_WAS="$(cat node_modules/.lock-sha1 2>/dev/null || true)"
if [ "$LOCK_NOW" != "$LOCK_WAS" ]; then
  echo "   의존성 설치 중 (처음이거나 package-lock.json이 바뀌었다)"
  npm ci --no-audit --no-fund 2>&1 | tail -3
  echo "$LOCK_NOW" > node_modules/.lock-sha1
else
  echo "   의존성 그대로 — 설치 건너뜀"
fi
npm run build

say "3/4  백엔드 코드 교체 (이전 것은 app.bak-${STAMP} 로 남긴다)"
cd "$BASE/backend"
[ -d app ] && mv app "app.bak-${STAMP}"
cp -r "$SRC/backend/app" app
cp "$SRC/backend/requirements.txt" requirements.txt
cp "$SRC/deploy/reset_service_data.py" reset_service_data.py
mkdir -p media uploads/store
echo "   라우터: $(ls app/api/routes | tr '\n' ' ')"
echo "   워크플로우: $(ls app/services/workflows | tr '\n' ' ')"

say "4/4  프론트 교체 (이전 것은 frontend.bak-${STAMP} 로 남긴다)"
cd "$BASE"
[ -d frontend ] && mv frontend "frontend.bak-${STAMP}"
mkdir -p frontend
cp -r "$SRC/frontend/dist/." frontend/
echo "   $(ls frontend | tr '\n' ' ')"

# 다음부터 짧은 명령으로 돌릴 수 있게 스크립트를 눈에 띄는 자리에 둔다.
cp "$SRC/deploy/deploy_from_github.sh" "$BASE/deploy.sh"

say "파일 배치 끝. 이제 다음 두 가지를 순서대로 한다:"
cat <<NEXT

   1) 재시작
      sudo systemctl restart adflow-backend adflow-frontend
      systemctl is-active adflow-backend adflow-frontend

   2) 재시작한 뒤에 데모 데이터 지우기 (순서를 바꾸면 옛 코드가 다시 채워 넣는다)
      cd ${BASE}/backend
      python3 reset_service_data.py            # 먼저 무엇이 지워지는지 확인
      python3 reset_service_data.py --apply

   다음번 배포는 이 한 줄이면 된다:
      bash ${BASE}/deploy.sh

   되돌리려면:
      cd ${BASE}/backend && rm -rf app && mv app.bak-${STAMP} app
      cd ${BASE} && rm -rf frontend && mv frontend.bak-${STAMP} frontend
      sudo systemctl restart adflow-backend adflow-frontend
NEXT
