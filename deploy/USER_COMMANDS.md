# 사람이 직접 해야 하는 명령

배포 스크립트(`deploy/deploy.sh`)는 파일만 올린다. 아래 두 가지는 권한이 필요해서
스크립트가 못 한다 — VM에 들어가 직접 실행한다.

```bash
gcloud compute ssh team3-vm --zone=us-east1-b
```

> `--tunnel-through-iap` 는 붙이지 않는다. 이 프로젝트에서는 "not authorized" 로 실패한다.

---

## 1. 서비스 재시작 (필수)

```bash
sudo systemctl restart adflow-backend adflow-frontend
systemctl is-active adflow-backend adflow-frontend      # 둘 다 active 여야 한다
```

확인:

```bash
curl -s localhost:8010/api/store | head -c 300
```

---

## 2. ComfyUI 주소를 내부 주소로 (권장 — 안 하면 재부팅할 때마다 그림이 안 나온다)

백엔드는 지금 ComfyUI를 **VM의 공인 IP**로 부른다. 이 IP는 고정이 아니라서
VM을 껐다 켜면 바뀌고, 그러면 그림 생성이 전부 실패한다. 같은 기계 안에서 부르면 된다.

`backend/.env` 에서 `COMFY_BASE_URL` 을 다음으로 바꾼다:

```
COMFY_BASE_URL=http://127.0.0.1:8188
```

편집:

```bash
nano /home/sprint05/part4_3team/backend/.env
sudo systemctl restart adflow-backend
```

> `.env` 에는 API 키가 들어 있어 이 작업은 자동화하지 않았다.

---

## 3. 데모 데이터 지우기 (재시작 **다음에**)

순서를 지켜야 한다. 옛 코드가 돌고 있는 동안 지우면 다시 채워 넣는다.

```bash
cd /home/sprint05/part4_3team/backend
python3 reset_service_data.py            # 무엇이 지워지는지 먼저 확인
python3 reset_service_data.py --apply    # 실제로 지움
```

지우기 전에 `app.db.bak-<날짜>` 로 복사본을 만들고, 올린 사진은 지우지 않고
`uploads/store/_removed-<날짜>/` 로 옮긴다.

---

## 4. (선택) nginx 응답 대기 시간 늘리기

`/api/` 경로에 `proxy_read_timeout` 설정이 없어 기본값 **60초**로 끊긴다.
지금 코드는 생성을 백그라운드로 돌리고 3초마다 확인하는 방식이라 60초로도 동작하지만,
업로드가 느린 회선에서는 사진 올리기가 끊길 수 있다.

```bash
sudo nano /etc/nginx/sites-enabled/default
```

`location /api/` 블록 안에 추가:

```nginx
    proxy_read_timeout 300s;
    client_max_body_size 20m;
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## 되돌리기

배포 스크립트는 이전 것을 지우지 않고 이름만 바꿔 남긴다.

```bash
cd /home/sprint05/part4_3team
ls -d backend/app.bak-* frontend.bak-*        # 남아 있는 것 확인

# 백엔드 되돌리기
cd backend && rm -rf app && mv app.bak-<날짜> app
sudo systemctl restart adflow-backend

# DB 되돌리기
cp app.db.bak-<날짜> app.db
sudo systemctl restart adflow-backend
```
