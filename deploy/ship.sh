#!/usr/bin/env bash
# 올리고 배포한다 — **순서를 강제한다.**
#
#   gh 계정 확인 → 최신 main 위로 rebase → push → (성공했을 때만) 배포 → 재시작 → 확인
#
# 왜 스크립트로 묶는가. 손으로 하면 두 가지가 반복해서 어긋났다:
#
#   1. gh 활성 계정이 beomjinkim2000 으로 **자꾸 되돌아간다**(하루에 세 번 겪었다).
#      그대로 밀면 403 이다.
#   2. `git push && ./deploy.sh` 로 이어 놓으면 push 가 403 으로 죽어도 뒤가 돌아서
#      **서버에는 올라갔는데 main 에는 없는 상태**가 된다. 실제로 났고, 그때 팀원이
#      방금 올린 파일이 서버에서 되돌아가기까지 했다.
#
# 그래서 여기서는 push 가 성공해야만 배포로 넘어간다.
#
# 쓰는 법:  ./deploy/ship.sh            (커밋은 미리 해 둘 것)
#           ./deploy/ship.sh --no-deploy  (푸시만)
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
ACCOUNT=beomjin2
VM=team3-vm
ZONE=us-east1-b

say() { printf '\n== %s\n' "$*"; }
die() { printf '\n!! %s\n' "$*" >&2; exit 1; }

say "0/5  올릴 게 있는지 본다"
if [ -n "$(git status --porcelain)" ]; then
  git status --short
  die "커밋하지 않은 변경이 있다. 커밋한 뒤에 다시 돌려라."
fi

say "1/5  gh 계정을 $ACCOUNT 로 맞춘다"
current="$(gh auth status 2>&1 | grep -B1 'Active account: true' | grep -o 'account [^ ]*' | awk '{print $2}' || true)"
echo "   지금: ${current:-(모름)}"
if [ "$current" != "$ACCOUNT" ]; then
  gh auth switch --user "$ACCOUNT" || die "계정 전환 실패 — 'gh auth status' 로 확인해라"
  echo "   -> $ACCOUNT 로 바꿨다"
fi

say "2/5  최신 main 위로 올린다"
git fetch origin
# 팀원이 먼저 올린 게 있으면 그 위로 얹는다. 이걸 건너뛰고 배포하면 팀원 코드가
# 서버에서 되돌아간다 — deploy.sh 는 backend/app/ 을 통째로 바꾸기 때문이다.
git rebase origin/main || die "rebase 충돌 — 풀고 나서 다시 돌려라"
echo "   HEAD=$(git rev-parse --short HEAD)  origin/main=$(git rev-parse --short origin/main)"

say "3/5  push"
git push origin HEAD:main || die "push 실패 — 배포하지 않고 멈춘다(서버만 앞서가면 안 된다)"

if [ "${1:-}" = "--no-deploy" ]; then
  say "끝. (--no-deploy 라 배포는 건너뛴다)"
  exit 0
fi

say "4/5  배포"
[ -f frontend/dist/index.html ] || die "frontend/dist 가 없다. 'cd frontend && npm run build' 먼저."
./deploy/deploy.sh >/dev/null
echo "   파일 올림"

say "5/5  재시작하고 확인"
gcloud compute ssh "$VM" --zone="$ZONE" --command="
  sudo systemctl restart adflow-backend adflow-frontend
  sleep 3
  systemctl is-active adflow-backend adflow-frontend
"

pushed="$(git rev-parse --short HEAD)"
say "끝. main=$pushed 이 올라갔고 서버도 같은 코드다."
