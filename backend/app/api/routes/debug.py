"""뜯어보기 — 단계별 기록(trace)을 목록·JSON·계단 화면으로 내준다. 개발용."""
from __future__ import annotations

import html
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.services.trace import Tracer, list_runs

router = APIRouter(prefix="/api/debug", tags=["debug"])


@router.get("/traces")
def traces(limit: int = 30):
    return list_runs(limit)


@router.get("/trace/{run_id}")
def trace_json(run_id: str):
    tr = Tracer.resume("latest" if False else run_id) if run_id != "latest" else _latest()
    if tr is None:
        raise HTTPException(404, "기록이 없어요")
    return {"run_id": tr.run_id, "steps": tr.rows()}


def _latest() -> Tracer | None:
    runs = list_runs(1)
    return Tracer.resume(runs[0]["run_id"]) if runs else None


_CSS = """
*{box-sizing:border-box}body{margin:0;background:#FBFAF6;color:#1D1E1B;font-family:"Noto Sans KR",system-ui,sans-serif;font-size:14px;line-height:1.7}
main{max-width:1000px;margin:0 auto;padding:28px 16px 80px}h1{font-size:22px;margin:0 0 4px}.meta{color:#8A8E85;font-size:12px;margin:0 0 18px;font-family:ui-monospace,monospace}
.step{border:1px solid #E3E1D7;border-radius:12px;margin:10px 0;overflow:hidden}
.step>summary{list-style:none;cursor:pointer;display:flex;gap:10px;align-items:center;padding:10px 14px;background:#F3F1E9}
.step>summary::-webkit-details-marker{display:none}.n{width:26px;height:26px;border-radius:999px;background:#2F5D8A;color:#fff;display:grid;place-items:center;font-weight:900;font-size:12px;flex:none}
.name{font-weight:900;flex:1}.who{font-size:11px;border-radius:999px;padding:2px 8px;background:#E4ECF4;color:#2F5D8A}.who.gpt{background:#F7E7DB;color:#B8561F}.who.comfy{background:#E3F1E9;color:#2B7A52}
.sec{color:#8A8E85;font-size:12px;font-family:ui-monospace,monospace}.body{padding:10px 14px;display:grid;gap:8px}
.k{font-size:11px;color:#8A8E85;letter-spacing:.04em;margin:6px 0 2px}pre{margin:0;background:#fff;border:1px solid #E3E1D7;border-radius:8px;padding:8px 10px;font-size:12px;white-space:pre-wrap;word-break:break-word;max-height:420px;overflow:auto}
img{max-width:220px;border-radius:8px;border:1px solid #E3E1D7}.chip{display:inline-block;font-family:ui-monospace,monospace;font-size:11.5px;padding:1px 7px;border-radius:6px;background:#EDEFEF;margin:2px}
.chip.ok{background:#E3F1E9;color:#1B5C3B}.chip.no{background:#F8E3E0;color:#93261C}a{color:#2F5D8A}
"""


def _val(v) -> str:
    if isinstance(v, (dict, list)):
        return f"<pre>{html.escape(json.dumps(v, ensure_ascii=False, indent=1))}</pre>"
    s = str(v)
    if s.startswith("/api/media/") and s.endswith(".png"):
        return f'<a href="{s}" target="_blank"><img src="{s}" alt=""></a>'
    if "\n" in s or len(s) > 120:
        return f"<pre>{html.escape(s)}</pre>"
    return html.escape(s)


def _render(tr: Tracer) -> str:
    rows = tr.rows()
    parts = []
    for r in rows:
        who = str(r.get("who", "code"))
        cls = "gpt" if who.startswith("gpt") else ("comfy" if who == "comfyui" else "")
        fields = {k: v for k, v in r.items() if k not in ("i", "t", "name", "who", "sec")}
        body = ""
        # 사전 판정은 칩으로
        if "verified" in fields or "rejected" in fields:
            body += '<div class="k">사전 판정</div><div>'
            body += "".join(f'<span class="chip ok">{html.escape(str(t))}</span>' for t in fields.pop("verified", []))
            body += "".join(f'<span class="chip no">{html.escape(str(t))} · {html.escape(str(w))}</span>' for t, w in (fields.pop("rejected", {}) or {}).items())
            body += "</div>"
        for k, v in fields.items():
            body += f'<div class="k">{html.escape(k)}</div><div>{_val(v)}</div>'
        sec = f'<span class="sec">{r["sec"]}초</span>' if "sec" in r else ""
        parts.append(f'<details class="step" {"open" if r["i"] <= 2 else ""}><summary><span class="n">{r["i"]}</span>'
                     f'<span class="name">{html.escape(str(r["name"]))}</span><span class="who {cls}">{html.escape(who)}</span>{sec}</summary>'
                     f'<div class="body">{body}</div></details>')
    runs = list_runs(15)
    nav = " · ".join(f'<a href="/api/debug/trace/{x["run_id"]}/view">{x["run_id"]}</a>' for x in runs)
    return (f"<!doctype html><meta charset='utf-8'><title>뜯어보기 {tr.run_id}</title><style>{_CSS}</style><main>"
            f"<h1>뜯어보기 · {tr.run_id}</h1><p class='meta'>{len(rows)}단계 · 단계를 누르면 들어간 것·나온 것 원문이 펼쳐진다 · GPT=주황 · ComfyUI=초록 · 코드=파랑</p>"
            f"{''.join(parts)}<p class='meta' style='margin-top:24px'>다른 기록: {nav}</p></main>")


@router.get("/trace/{run_id}/view", response_class=HTMLResponse)
def trace_view(run_id: str):
    tr = _latest() if run_id == "latest" else Tracer.resume(run_id)
    if tr is None:
        raise HTTPException(404, "기록이 없어요")
    return _render(tr)
