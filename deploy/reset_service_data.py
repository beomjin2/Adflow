#!/usr/bin/env python3
"""서비스를 처음 쓰는 상태로 되돌린다 — 데모용으로 미리 넣어둔 데이터를 지운다.

지우는 것은 seed 코드가 만들어 넣은 값이다. 가게 주소 '서울 마포구 연남로 21',
품목 '소금빵 / 버터 크루아상 / 통밀 캄파뉴', '눈이 번쩍 챌린지' 트렌드, 캐릭터 '동글이',
AI가 먼저 걸어둔 인사말 같은 것들. 사장님이 적은 적 없는 내용인데 화면에 이미 들어차 있어,
자기가 입력한 것과 구별되지 않는다.

반드시 새 코드로 재시작한 다음에 돌려라. 옛 코드가 돌고 있으면 생산 기록이 비는 순간
다시 채워 넣어서, 지워도 되살아난다.

지우지 않는 것:
  - 테이블과 스키마 (구조는 그대로 둔다)
  - .env / 로그
  - 사장님이 올린 사진 파일 — DB에서 참조만 끊고, 파일은 uploads/_removed-<날짜>/ 로 옮긴다.
    지운 게 아니라 옮긴 것이라, 잘못 지웠으면 되돌릴 수 있다.

사용법:
    python3 reset_service_data.py            # 무엇을 지울지 보여만 준다
    python3 reset_service_data.py --apply    # 실제로 지운다
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sqlite3
import sys
from pathlib import Path

def find_backend() -> Path:
    """app.db 가 있는 곳. 스크립트 옆(VM에 복사해 둔 경우)이나 저장소의 backend/."""
    here = Path(__file__).resolve().parent
    for candidate in (here, here.parent / "backend", Path.cwd()):
        if (candidate / "app.db").exists():
            return candidate
    return here


BACKEND = find_backend()
DB = BACKEND / "app.db"
UPLOADS = BACKEND / "uploads" / "store"

# 싱글턴 행 — 지우지 않고 값만 비운다. 행 자체가 없으면 백엔드가 매 요청마다 만들어야 한다.
BLANK = {
    "store": {
        "saved": 0, "category": "", "address": "", "hours": "",
        "open_time": "", "close_time": "", "closed_days": "[]",
        "desc": "", "images": "[]",
    },
    # 캐릭터 시트 8칸 + 진행 상태. 없는 컬럼은 아래 columns()가 걸러내므로
    # 예전 스키마(hobby·views)가 남은 DB에도 그대로 돌아간다.
    "character": {
        "name": "", "age": "", "gender": "", "look": "", "outfit": "",
        "abilities": "", "keywords": "[]", "desc": "",
        "editing": "", "pending": "{}",
        "confirmed": 0, "candidates": "[]", "selected_index": -1,
        "hobby": "", "views": "[]", "messages": "[]",
    },
    "ad_settings": {"ad_type": "", "ad_concept": ""},
    "storyboard": {
        "messages": "[]", "plan": "[]", "comic_cuts": "[]",
        "prod_logged": 0, "pending": "{}",
    },
}

# 통째로 비우는 표 — 여기 든 행은 전부 seed가 만든 것이다.
EMPTY_TABLES = ["production_records", "production_items", "history"]


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def uploaded_files(conn: sqlite3.Connection) -> list[str]:
    """store.images 가 가리키는 파일 이름들."""
    row = conn.execute("SELECT images FROM store WHERE id = 1").fetchone()
    if not row or not row[0]:
        return []
    try:
        items = json.loads(row[0])
    except (TypeError, ValueError):
        return []
    names = []
    for item in items:
        url = (item or {}).get("image") or ""
        if url.startswith("/api/uploads/store/"):
            names.append(url.rsplit("/", 1)[-1])
    return names


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="실제로 지운다 (없으면 미리보기)")
    args = ap.parse_args()

    if not DB.exists():
        print(f"app.db 가 없다: {DB}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    print(f"대상: {DB}")
    print()

    # --- 무엇이 지워지는지 먼저 보여준다 ---
    for table, values in BLANK.items():
        row = conn.execute(f"SELECT * FROM {table} WHERE id = 1").fetchone()
        if not row:
            print(f"[{table}] 1번 행이 없다 — 백엔드가 시작할 때 빈 행을 만든다")
            continue
        filled = []
        for key in values:
            if key not in row.keys():
                continue
            current = row[key]
            if current in (None, "", 0, -1, "[]", "{}"):
                continue
            text = str(current)
            filled.append(f"{key}={text[:70]}{'…' if len(text) > 70 else ''}")
        print(f"[{table}] 비울 값 {len(filled)}개")
        for line in filled:
            print(f"    {line}")

    for table in EMPTY_TABLES:
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"[{table}] {n}행 삭제")

    files = uploaded_files(conn)
    print(f"[uploads] 참조 끊을 사진 {len(files)}장: {', '.join(files) or '없음'}")

    if not args.apply:
        print("\n미리보기다. 실제로 지우려면 --apply 를 붙여라.")
        return 0

    # --- 실제 반영 ---
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = DB.with_name(f"app.db.bak-{stamp}")
    shutil.copy2(DB, backup)
    print(f"\nDB를 먼저 복사해 뒀다: {backup.name}")

    with conn:
        for table, values in BLANK.items():
            have = columns(conn, table)
            usable = {k: v for k, v in values.items() if k in have}
            if not usable:
                continue
            sets = ", ".join(f"{k} = ?" for k in usable)
            conn.execute(f"UPDATE {table} SET {sets} WHERE id = 1", list(usable.values()))
        for table in EMPTY_TABLES:
            conn.execute(f"DELETE FROM {table}")
        # 지운 행의 id가 1부터 다시 시작하도록. 남겨두면 첫 기록이 4번으로 생긴다.
        has_seq = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'"
        ).fetchone()
        if has_seq:
            placeholders = ", ".join("?" for _ in EMPTY_TABLES)
            conn.execute(
                f"DELETE FROM sqlite_sequence WHERE name IN ({placeholders})",
                EMPTY_TABLES,
            )

    # 사진은 지우지 않고 옮긴다. 진짜 사장님 사진이 섞여 있으면 되돌릴 수 있어야 한다.
    if files:
        removed_dir = UPLOADS.parent / f"_removed-{stamp}"
        removed_dir.mkdir(parents=True, exist_ok=True)
        moved = 0
        for name in files:
            src = UPLOADS / name
            if src.exists():
                shutil.move(str(src), str(removed_dir / name))
                moved += 1
        print(f"사진 {moved}장을 {removed_dir} 로 옮겼다 (지운 게 아니다)")

    conn.close()
    print("\n끝. 이제 화면을 새로고침하면 아무것도 없는 상태로 시작한다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
