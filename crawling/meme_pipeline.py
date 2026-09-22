#!/usr/bin/env python3
"""meme_pipeline.py — 밈 크롤링 한 사이클을 명령 하나로 돌린다.

    # 저장소 루트에서, backend 가상환경으로
    python crawling/meme_pipeline.py                  # 기본: backend/app.db 에 반영
    python crawling/meme_pipeline.py --db test.db     # 다른 DB(사본)에 먼저 리허설
    python crawling/meme_pipeline.py --debug          # 사이트별로 읽은 원문 토큰을 logs/pages/ 에 저장

한 사이클 (팀 결정 순서)
  1. 목록 긁기     세 사이트 목록에서 후보를 모은다
  2. 아는 밈 건너뛰기  DB에 이미 있는 밈(주소·이름)은 상세 페이지를 열지 않는다
  3. 새 밈 파싱     이름·유래·활용 예시·대표 이미지·등록일
  4. 중복 묶기     사이트끼리 겹치는 같은 밈을 유래 유사도(TF-IDF)로 묶는다 — 새 밈끼리, 새 밈↔DB 둘 다
  5. DB 저장       누적 방식(import_memes.upsert_memes). 기존 밈의 내용은 덮어쓰지 않는다
  6. 상황 분류     새 밈만 (classify_memes_situation.py, 지연님)
  7. 유행 날짜     DB의 밈 전체를 네이버 검색어트렌드로 다시 잰다 (naver_trend.py)

실패해도 멈추지 않게
  · 사이트 하나가 실패해도 나머지 사이트는 계속 간다(사이트별 try)
  · 글 하나 파싱이 깨져도 그 글만 빼고 계속 간다(글별 try)
  · 4~5단계에서 저장이 끝난 뒤의 6·7단계가 실패해도 저장된 밈은 남는다
  · 다시 돌려도 안전하다 — 이미 있는 밈은 건너뛰고, 저장은 누적이라 중복이 안 생긴다
  · 끝나면 단계별 결과를 logs/run_날짜.json 에 남기고 요약을 출력한다
  · 동시에 두 번 돌지 않게 잠금 파일(logs/pipeline.lock)을 쓴다
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BACKEND = ROOT / "backend"
LOGS = HERE / "logs"
IMAGES = HERE / "images"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

LIMIT = {"maily_trendaword": 10, "gogumafarm": 2, "wepick_memepedia": 10}  # 고구마팜은 모음집 글 수(글당 밈 5개 안팎)
LABEL = {"maily_trendaword": "Trend A Word", "gogumafarm": "고구마팜", "wepick_memepedia": "위픽레터 밈피디아"}


class Run:
    def __init__(self):
        self.started = dt.datetime.now()
        self.log = {"started_at": self.started.isoformat(timespec="seconds"), "steps": {}, "errors": []}

    def step(self, name, **kw):
        self.log["steps"].setdefault(name, {}).update(kw)

    def err(self, where, e):
        msg = f"{where}: {type(e).__name__}: {e}"
        print(f"  [!] {msg}")
        self.log["errors"].append({"where": where, "error": msg, "trace": traceback.format_exc()[-1500:]})

    def save(self):
        LOGS.mkdir(parents=True, exist_ok=True)
        self.log["finished_at"] = dt.datetime.now().isoformat(timespec="seconds")
        p = LOGS / f"run_{self.started:%Y%m%d_%H%M%S}.json"
        p.write_text(json.dumps(self.log, ensure_ascii=False, indent=1), encoding="utf-8")
        return p


def setup_db(db_arg: str | None) -> Path:
    db = Path(db_arg).resolve() if db_arg else BACKEND / "app.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db.as_posix()}"
    sys.path.insert(0, str(BACKEND))
    sys.path.insert(0, str(HERE))
    return db


def id_for(rec: dict, idx: int) -> str:
    src, url = rec["source"], rec["url"]
    tail = urlparse(url).path.rstrip("/").split("/")[-1]
    if src == "maily_trendaword":
        return f"maily_{tail}"
    if src == "wepick_memepedia":
        return f"wepick_{tail}" if tail.isdigit() and tail != "23942" else f"wepick_c23942_{idx:02d}"
    ym = re.sub(r"\D", "", rec.get("published_date") or dt.date.today().isoformat())[:6]
    return f"gogumafarm_{ym}_{idx:02d}"


def main() -> int:
    ap = argparse.ArgumentParser(description="밈 크롤링 한 사이클")
    ap.add_argument("--db", help="반영할 DB 경로 (기본 backend/app.db)")
    ap.add_argument("--sites", default="maily_trendaword,gogumafarm,wepick_memepedia")
    ap.add_argument("--skip-classify", action="store_true")
    ap.add_argument("--skip-naver", action="store_true")
    ap.add_argument("--debug", action="store_true", help="읽은 페이지 토큰을 logs/pages/ 에 저장")
    args = ap.parse_args()

    db_path = setup_db(args.db)
    LOGS.mkdir(parents=True, exist_ok=True)
    lock = LOGS / "pipeline.lock"
    if lock.exists() and (dt.datetime.now().timestamp() - lock.stat().st_mtime) < 3 * 3600:
        print("이미 실행 중이에요(logs/pipeline.lock). 3시간 넘게 남아 있으면 지난 실행이 비정상 종료된 것 — 지우고 다시 실행하세요.")
        return 2
    lock.write_text(str(os.getpid()))

    run = Run()
    run.log["db"] = str(db_path)
    try:
        return _cycle(run, args, db_path)
    finally:
        p = run.save()
        lock.unlink(missing_ok=True)
        print(f"\n실행 기록: {p.relative_to(ROOT)}")


def _cycle(run: Run, args, db_path: Path) -> int:
    import pipeline_sources as S
    import pipeline_dedupe as D
    from app import models
    from app.core.database import SessionLocal, init_db
    from import_memes import upsert_memes

    if args.debug:
        S.DEBUG_DIR = LOGS / "pages"
    print(f"== 밈 파이프라인 시작 {run.started:%Y-%m-%d %H:%M}  (DB: {db_path})")
    if not db_path.exists():
        print("  DB 파일이 없어서 새로 만듭니다.")
    init_db()

    # ---- 0. DB에 이미 있는 밈
    db = SessionLocal()
    try:
        rows = db.query(models.Meme).all()
        existing = [{"_db_id": r.id, "source": r.source, "name": r.meme_name, "origin": r.origin or "",
                     "urls": {r.url} | {m.get("url") for m in (r.merged_from or [])},
                     "keys": {S.norm_key(r.meme_name)} | {S.norm_key(m.get("name")) for m in (r.merged_from or [])}}
                    for r in rows]
    finally:
        db.close()
    known_urls = {u for e in existing for u in e["urls"] if u}
    known_keys = {k for e in existing for k in e["keys"] if k}
    print(f"-- DB에 있는 밈 {len(existing)}개")

    # ---- 1~3. 사이트별 수집 (한 곳이 실패해도 계속)
    new_recs: list[dict] = []
    sites = [s.strip() for s in args.sites.split(",") if s.strip()]
    for site in sites:
        stat = {"found": 0, "known": 0, "new": 0, "failed_items": 0}
        try:
            print(f"-- [{LABEL.get(site, site)}]")
            recs = []
            if site == "maily_trendaword":
                for c in S.maily_discover(LIMIT[site]):
                    if stat["found"] >= LIMIT[site]:
                        break
                    if c["url"] in known_urls:
                        stat["found"] += 1; stat["known"] += 1
                        continue
                    try:
                        r = S.maily_parse(c["url"])
                    except Exception as e:
                        stat["failed_items"] += 1; run.err(f"{site} {c['url']}", e)
                        continue
                    if r is None:  # 휴재 공지 등 밈 구조가 없는 글
                        continue
                    stat["found"] += 1
                    recs.append(r)
            elif site == "gogumafarm":
                got = 0
                for c in S.gogumafarm_discover(LIMIT[site]):
                    if got >= LIMIT[site]:
                        break
                    try:
                        items = S.gogumafarm_parse(c["url"])
                    except Exception as e:
                        stat["failed_items"] += 1; run.err(f"{site} {c['url']}", e)
                        continue
                    if not items:
                        continue  # 모음집이 아닌 글
                    got += 1
                    for n, r in enumerate(items, 1):
                        r["_idx"] = n
                        stat["found"] += 1
                        if S.norm_key(r["name"]) in known_keys:
                            stat["known"] += 1
                        else:
                            recs.append(r)
            elif site == "wepick_memepedia":
                for n, r in enumerate(S.wepick_parse_collection(LIMIT[site]), 1):
                    r["_idx"] = n
                    stat["found"] += 1
                    if r["url"] in known_urls or S.norm_key(r["name"]) in known_keys:
                        stat["known"] += 1
                        continue
                    try:
                        r["published_date"] = S.wepick_published_date(r["url"])
                    except Exception as e:
                        run.err(f"{site} 등록일 {r['url']}", e)
                    recs.append(r)
            else:
                raise ValueError(f"모르는 사이트: {site}")
            if stat["found"] == 0:
                raise RuntimeError("밈을 하나도 못 찾음 — 사이트 구조가 바뀌었을 수 있음 (--debug 로 확인)")
            recs = [r for r in recs if r.get("name") and (r.get("origin") or r.get("usage_example"))]
            stat["new"] = len(recs)
            new_recs += recs
            stat["ok"] = True
            print(f"   찾음 {stat['found']} · 이미 있음 {stat['known']} · 새 밈 {stat['new']}"
                  + (f" · 실패 {stat['failed_items']}" if stat["failed_items"] else ""))
        except Exception as e:
            stat["ok"] = False
            run.err(site, e)
        run.step("collect", **{site: stat})

    ok_sites = [s for s in sites if run.log["steps"].get("collect", {}).get(s, {}).get("ok")]
    if not ok_sites:
        print("\n세 사이트 모두 실패 — 저장할 게 없어서 여기서 멈춥니다.")
        return 1

    # ---- 4. 중복 묶기 (새 밈끼리 + 새 밈↔DB)
    items: list[dict] = []
    renames: dict[str, str] = {}
    try:
        pool = new_recs + existing
        groups = D.group(pool)
        n_new, n_db_match, n_merged = 0, 0, 0
        for g in groups:
            news = [i for i in g if i < len(new_recs)]
            if not news:
                continue
            dbs = [pool[i] for i in g if i >= len(new_recs)]
            recs = [new_recs[i] for i in news]
            if dbs:  # DB에 이미 있는 밈과 같은 밈 → 그 행에 출처만 덧붙인다
                for r in recs:
                    r["_match_id"] = dbs[0]["_db_id"]
                    n_db_match += 1
                rep_list = recs
                # 기존 이름에 빈칸 표기(OO)가 있고 새 이름엔 없으면 새 이름으로 바꾼다(저장 뒤에 적용)
                better = D.pick_name([dbs[0]["name"]] + [r["name"] for r in recs])
                if better != dbs[0]["name"]:
                    renames[dbs[0]["_db_id"]] = better
            else:
                cand = [r for r in recs if len(r.get("origin") or "") >= 30] or recs
                rep = min(cand, key=lambda r: len(r.get("origin") or ""))
                rest = [r for r in recs if r is not rep]
                # 내용은 유래가 짧은 쪽, 이름은 빈칸 표기(OO) 없는 쪽. 원래 이름은 별칭으로 남긴다.
                name = D.pick_name([rep["name"]] + [r["name"] for r in rest])
                if name != rep["name"]:
                    rep["_alias"] = rep["name"]
                    rep["name"] = name
                rep_list = [rep]
                n_new += 1
                n_merged += len(rest)
            for r in rep_list:
                r["_rest"] = [] if dbs else rest
                items.append(r)
        run.step("dedupe", new_memes=n_new, merged_into_new=n_merged, matched_existing=n_db_match)
        print(f"-- 중복 묶기: 새 밈 {n_new}개 (사이트끼리 합친 것 {n_merged}건), 기존 밈과 같은 것 {n_db_match}건")
    except Exception as e:
        run.err("dedupe", e)
        items = [dict(r, _rest=[]) for r in new_recs]  # 묶기에 실패하면 이름 기준 중복 방지(upsert)에만 맡긴다

    # ---- 이미지 + 저장용 모양으로
    IMAGES.mkdir(exist_ok=True)
    out, img_fail = [], 0
    for r in items:
        mid = id_for(r, r.get("_idx", 0))
        img_file = ""
        if r.get("image_url"):
            ext = Path(urlparse(r["image_url"]).path).suffix.lower()
            ext = ext if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp") else ".jpg"
            try:
                S.download_image(r["image_url"], IMAGES / f"{mid}{ext}")
                img_file = f"images/{mid}{ext}"
            except Exception as e:
                img_fail += 1
                run.err(f"이미지 {mid}", e)
        rest = r.get("_rest") or []
        item = {
            "id": mid, "name": r["name"], "source": r["source"], "source_label": r["source_label"],
            "url": r["url"], "origin": r.get("origin", ""), "usage_example": r.get("usage_example", ""),
            "published_date": r.get("published_date", ""), "image": {"file": img_file, "source_url": r.get("image_url")},
            "links": [{"title": "원문 기사에서 보기", "kind": "origin_article", "href": r["url"]}]
                     + [{"title": f"{x['source_label']}에서 보기", "kind": "same_meme", "href": x["url"]} for x in rest],
            "merged_from": [{"id": id_for(x, x.get("_idx", 0)), "source": x["source"], "source_label": x["source_label"],
                             "name": x["name"], "url": x["url"]} for x in rest]
                           + ([{"id": mid, "source": r["source"], "source_label": r["source_label"], "name": r["_alias"],
                                "url": r["url"], "alias": True}] if r.get("_alias") else []),
            "search_terms": [], "trend": {},
        }
        if r.get("_match_id"):
            item["_match_id"] = r["_match_id"]
        out.append(item)
    (LOGS / f"run_{run.started:%Y%m%d_%H%M%S}_items.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 5. DB 저장 (여기까지 오면 새 밈은 남는다)
    try:
        res = upsert_memes(out, dt.date.today().isoformat()) if out else {"inserted": 0, "updated": 0}
        run.step("save", **res, image_failed=img_fail)
        print(f"-- 저장: 새로 추가 {res.get('inserted', 0)} · 기존 밈에 출처 추가 {res.get('updated', 0)}"
              + (f" · 이미지 실패 {img_fail}" if img_fail else ""))
    except Exception as e:
        run.err("save", e)
        return 1
    new_ids = [i["id"] for i in out if not i.get("_match_id")]
    if renames:
        try:
            apply_renames(renames, run)
        except Exception as e:
            run.err("rename", e)

    # ---- 6. 상황 분류 (새 밈만 반영)
    if args.skip_classify or not new_ids:
        run.step("classify", skipped=True)
    else:
        try:
            n = classify_new(db_path, new_ids, run)
            run.step("classify", applied=n)
            print(f"-- 상황 분류: 새 밈 {n}개에 반영")
        except Exception as e:
            run.err("classify", e)

    # ---- 7. 유행 날짜 (DB 전체)
    if args.skip_naver:
        run.step("naver", skipped=True)
    else:
        try:
            r = naver_all(run)
            run.step("naver", **r)
            print(f"-- 유행 날짜: 급등 측정 {r['spike']} · 측정 불가 {r['none']} · 조회 실패 {r['error']}")
        except Exception as e:
            run.err("naver", e)

    print(f"\n== 끝 ({(dt.datetime.now() - run.started).seconds}초). 오류 {len(run.log['errors'])}건"
          + (" — 실행 기록의 errors 를 보세요" if run.log["errors"] else ""))
    return 0


def apply_renames(renames: dict[str, str], run: Run) -> None:
    """기존 밈 이름에 빈칸 표기(OO)가 있고, 같은 밈이 빈칸 없는 이름으로 새로 들어왔으면 그 이름으로 바꾼다.
    옛 이름은 merged_from에 별칭으로 남겨서 다음 크롤링에서도 같은 밈으로 잡히게 한다.
    옛 이름에 사람이 정해 둔 네이버 검색어(naver_trend.MANUAL)가 있으면 search_terms로 옮겨서 측정이 안 끊기게 한다."""
    import naver_trend as N
    from app import models
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        for mid, new_name in renames.items():
            row = db.get(models.Meme, mid)
            if not row or row.meme_name == new_name:
                continue
            old = row.meme_name
            row.merged_from = list(row.merged_from or []) + [
                {"id": row.id, "source": row.source, "source_label": row.source_label, "name": old, "url": row.url, "alias": True}]
            if old in N.MANUAL:  # 사람이 정한 검색어를 맨 앞에(naver_all은 첫 번째 검색어를 쓴다)
                row.search_terms = list(N.MANUAL[old]) + [t for t in (row.search_terms or []) if t not in N.MANUAL[old]]
            row.meme_name = new_name
            print(f"-- 이름 변경: '{old}' → '{new_name}' (옛 이름은 별칭으로 보관)")
            run.log.setdefault("renamed", []).append({"id": mid, "from": old, "to": new_name})
        db.commit()
    finally:
        db.close()


def classify_new(db_path: Path, new_ids: list[str], run: Run) -> int:
    """지연님 분류 스크립트를 그대로 돌리고, 결과 중 새 밈 것만 DB에 넣는다(기존 밈 분류는 안 건드림)."""
    import sqlite3
    env = dict(os.environ, MEME_CLASSIFY_DB=str(db_path))
    try:
        from dotenv import dotenv_values
        env.update({k: v for k, v in dotenv_values(BACKEND / ".env").items() if k == "OPENAI_API_KEY" and v})
    except Exception:
        pass
    work = LOGS / f"classify_{run.started:%Y%m%d_%H%M%S}"
    work.mkdir(parents=True, exist_ok=True)
    p = subprocess.run([sys.executable, str(HERE / "classify_memes_situation.py")], cwd=work, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    (work / "stdout.txt").write_text((p.stdout or "") + "\n" + (p.stderr or ""), encoding="utf-8")
    if p.returncode != 0:
        raise RuntimeError(f"분류 스크립트 실패(코드 {p.returncode}) — {work.name}/stdout.txt 참고")
    results = json.loads((work / "memes_classified.json").read_text(encoding="utf-8"))
    wanted = set(new_ids)
    con = sqlite3.connect(db_path)
    n = 0
    try:
        for it in results:
            mid = it.get("id") or it.get("unique_id")
            if mid in wanted:
                con.execute("UPDATE memes SET situation=?, situation_score=?, ad_safe=? WHERE id=?",
                            (it.get("situation") or "", it.get("situation_score"), it.get("ad_safe"), mid))
                n += 1
        con.commit()
    finally:
        con.close()
    return n


def naver_all(run: Run) -> dict:
    """DB의 밈 전체 유행 날짜를 다시 잰다. 급등이 잡힐 때만 덮어쓴다 — 못 쟀다고 예전 값을 지우지 않는다."""
    import naver_trend as N
    from app import models
    from app.core.database import SessionLocal

    N.reset_calls()
    db = SessionLocal()
    cnt = {"spike": 0, "none": 0, "error": 0}
    streak = 0
    try:
        rows = db.query(models.Meme).all()
        for row in rows:
            for t in (row.search_terms or []):  # 사람이 적어 둔 검색어가 있으면 우선
                N.MANUAL.setdefault(row.meme_name, [t])
            try:
                res = N.resolve(row.meme_name)
            except N.ApiError as e:  # 키 없음·호출 상한 등 — 더 돌아도 의미 없음
                run.err("naver", e)
                cnt["error"] += 1
                break
            m = res.get("method")
            if m == "spike":
                t = res["trend"]
                row.period_start, row.period_end, row.peak_date = t["start"], t["end"], t["peak"]
                row.trend_method, row.pre_existing = "spike", t.get("pre_existing")
                row.blog_total = (res.get("blog") or {}).get("total")
                cnt["spike"] += 1
                streak = 0
            elif m == "error":
                cnt["error"] += 1
                streak += 1
                if streak >= N.FAIL_FAST:
                    run.err("naver", RuntimeError(f"{N.FAIL_FAST}개 연속 조회 실패 — API 응답 없음으로 보고 중단"))
                    break
            else:
                cnt["none"] += 1
                streak = 0
                if not row.trend_method:
                    row.trend_method = "none"
            db.commit()  # 하나 잴 때마다 저장 — 중간에 멈춰도 잰 만큼은 남는다
    finally:
        db.close()
    return cnt


if __name__ == "__main__":
    sys.exit(main())
