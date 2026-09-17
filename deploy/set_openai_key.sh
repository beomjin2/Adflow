#!/usr/bin/env bash
# OpenAI 키를 배포 서버의 설정 파일에 넣는다. VM 안에서 사람이 직접 실행한다.
#
#   gcloud compute ssh team3-vm --zone=us-east1-b
#   bash /home/sprint05/part4_3team/.src/deploy/set_openai_key.sh
#
# 키를 인자로 받지 않는다 — 인자로 주면 셸 히스토리와 ps 목록에 그대로 남는다.
# 화면에도 찍지 않는다. 붙여넣어도 아무것도 안 보이는 게 정상이다.
#
# 키 하나를 두 군데서 쓴다:
#   - sheet_llm      캐릭터 시트 대화에서 한 문장을 여러 칸으로 나눠 읽는다
#   - danbooru_tags  외형 묘사를 실존 Danbooru 태그로 바꾼다
# 둘 다 키가 없으면 각자 규칙 기반으로 폴백하므로, 이걸 안 해도 서비스는 돈다.
# 키를 넣으면 두 기능의 품질이 같이 올라간다.
set -euo pipefail

CONF="/home/sprint05/part4_3team/backend/.env"

if [ ! -f "$CONF" ]; then
  echo "설정 파일이 없다: $CONF" >&2
  echo "배포가 끝난 서버에서 실행해야 한다." >&2
  exit 1
fi

printf '새 OpenAI 키를 붙여넣고 엔터 (화면에 안 보인다): '
IFS= read -rs KEY
printf '\n'

if [ -z "${KEY}" ]; then
  echo "아무것도 안 들어왔다. 그만둔다." >&2
  exit 1
fi
case "$KEY" in
  sk-*) ;;
  *) echo "sk- 로 시작하지 않는다. 잘못 붙여넣은 것 같아 그만둔다." >&2; exit 1 ;;
esac

# 되돌릴 자리를 먼저 만든다. 이 파일에는 DB 경로·ComfyUI 주소도 같이 들어 있어서
# 잘못 건드리면 서비스가 통째로 안 뜬다.
BACKUP="${CONF}.bak-$(date +%Y%m%d-%H%M%S)"
cp "$CONF" "$BACKUP"
chmod 600 "$BACKUP"

# 이미 있던 줄은 지우고 새로 넣는다 — 그냥 덧붙이면 같은 키가 두 줄이 되고,
# 나중에 어느 쪽이 쓰이는지 사람이 알 수 없게 된다.
TMP="$(mktemp)"
grep -v '^[[:space:]]*OPENAI_API_KEY[[:space:]]*=' "$CONF" > "$TMP" || true
printf 'OPENAI_API_KEY=%s\n' "$KEY" >> "$TMP"
mv "$TMP" "$CONF"
chmod 600 "$CONF"
unset KEY

echo "넣었다. 백업: $BACKUP"
echo
echo "이제 재시작해야 반영된다:"
echo "   sudo systemctl restart adflow-backend"
echo
echo "반영됐는지 확인 (키 자체는 안 찍고 길이만 본다):"
echo "   cd /home/sprint05/part4_3team/backend"
echo "   .venv/bin/python -c 'from app.core.config import settings; print(\"키 길이:\", len(settings.openai_api_key))'"
