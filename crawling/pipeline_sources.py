"""pipeline_sources.py — 세 사이트에서 밈을 가져온다 (meme_pipeline.py가 import해서 쓴다).

파싱 규칙은 claude.ai 프로젝트 문서 「밈 크롤링 파싱 전략 정리」를 그대로 따른다.
헤드리스 브라우저(crawl4ai) 없이 requests + 표준 라이브러리 HTMLParser만 쓴다 —
세 사이트 모두 서버에서 완성된 HTML을 내려주는 것을 확인했다(2026-09-22). VM 크론에서
크롬을 띄울 필요가 없어서 설치·실행이 단순해진다.

각 사이트 함수는 "레코드 목록"을 돌려준다. 레코드 모양:
  {source, source_label, url, name, origin, usage_example, image_url, published_date, list_rank}
실패는 예외로 올린다 — 사이트 단위로 잡아서 다른 사이트는 계속 도는 건 meme_pipeline.py 몫이다.
"""
from __future__ import annotations

import re
import time
from html.parser import HTMLParser
from urllib.parse import quote, urljoin

import requests

UA = {"User-Agent": "Mozilla/5.0 (AdflowMemeBot; bootcamp team project)"}  # HTTP 헤더는 영문만 가능(latin-1)
SLEEP = 1.5  # 요청 사이 쉬는 시간 — 사이트에 부담 주지 않게
VOID = {"img", "br", "hr", "meta", "link", "input", "source", "area", "base", "col", "embed", "param", "track", "wbr"}
SKIP = {"script", "style", "noscript", "svg", "button", "form", "nav", "header", "footer"}
DEBUG_DIR = None  # meme_pipeline.py --debug 이면 logs/pages/ 경로가 들어온다
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF⌀-⏿☀-➿️‍⬀-⯿]")


def strip_emoji(t: str) -> str:
    return re.sub(r"\s+", " ", EMOJI_RE.sub("", t)).strip()


def norm_key(t: str) -> str:
    return re.sub(r"\s+", "", t or "").lower()


# ---------------------------------------------------------------- HTML → 토큰
class _Tokens(HTMLParser):
    """HTML을 순서대로 늘어선 토큰으로 편다: ('t', 글), ('h', 제목), ('q', 인용문), ('img', src), ('a', href).
    in_mark: 지정한 class(예: entry-content) 안에서 나온 토큰인지 함께 적는다."""

    def __init__(self, mark_class: str = ""):
        super().__init__(convert_charrefs=True)
        self.mark_class = mark_class
        self.stack: list[tuple[str, bool]] = []  # (tag, 이 태그가 mark 시작인지)
        self.skip = 0
        self.inmark = 0
        self.heading = 0
        self.quote = 0
        self.tokens: list[tuple[str, str, bool]] = []
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and a.get("property") in ("og:image", "og:title") and a.get("content"):
            self.meta[a["property"]] = a["content"]
        if tag == "img":
            src = a.get("src") or a.get("data-src") or a.get("data-lazy-src") or ""
            if src and not self.skip:
                self.tokens.append(("img", src, bool(self.inmark)))
        if tag == "a" and a.get("href") and not self.skip:
            self.tokens.append(("a", a["href"], bool(self.inmark)))
        if tag in VOID:
            return
        is_mark = bool(self.mark_class) and self.mark_class in (a.get("class") or "").split()
        self.stack.append((tag, is_mark))
        if is_mark:
            self.inmark += 1
        if tag in SKIP:
            self.skip += 1
        if tag in ("h1", "h2", "h3", "h4"):
            self.heading += 1
        if tag == "blockquote":
            self.quote += 1

    def handle_endtag(self, tag):
        if tag in VOID or not any(t == tag for t, _ in self.stack):
            return
        while self.stack:  # 짝이 안 맞는 HTML도 견디게, 같은 태그가 나올 때까지 닫는다
            t, is_mark = self.stack.pop()
            if is_mark:
                self.inmark -= 1
            if t in SKIP:
                self.skip -= 1
            if t in ("h1", "h2", "h3", "h4"):
                self.heading -= 1
            if t == "blockquote":
                self.quote -= 1
            if t == tag:
                break

    def handle_data(self, data):
        t = " ".join(data.split())
        if not t or self.skip:
            return
        kind = "h" if self.heading else "q" if self.quote else "t"
        self.tokens.append((kind, t, bool(self.inmark)))


def fetch(url: str, mark_class: str = "") -> _Tokens:
    r = requests.get(url, headers=UA, timeout=25)
    r.raise_for_status()
    r.encoding = r.encoding or "utf-8"
    p = _Tokens(mark_class)
    p.feed(r.text)
    if DEBUG_DIR is not None:  # 파싱이 이상할 때 원인을 보려고 읽은 토큰을 그대로 남긴다
        import json
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        name = re.sub(r"[^0-9A-Za-z가-힣]+", "_", url)[-80:]
        (DEBUG_DIR / f"{name}.json").write_text(json.dumps({"url": url, "meta": p.meta, "tokens": p.tokens},
                                                           ensure_ascii=False, indent=0), encoding="utf-8")
    time.sleep(SLEEP)
    return p


def _texts(tokens) -> list[str]:
    return [v for k, v, *_ in tokens if k in ("t", "h", "q")]


_DROP = ("출처", "*출처", "이미지 =", "이미지 출처", "http", "@", "(1)", "(2)", "(3)")
_GLUE = re.compile(r"^(에서|에게|으로|이라|이며|이고|에|을|를|이|가|은|는|의|로|와|과|도|만|처럼|까지|부터|라는|라고|[.,!?…~”’)」』\]])")


def _keep(lines: list[str]) -> list[str]:
    return [l for l in lines if not l.startswith(_DROP) and l not in (")", "|", "·", "<", ">")]


def _clean_lines(lines: list[str]) -> str:
    """줄 단위 그대로 이어 붙인다(메일리처럼 원문이 원래 한 줄씩 끊겨 있는 글)."""
    return "\n".join(_keep(lines)).strip()


def _join_inline(lines: list[str]) -> str:
    """링크·굵은 글씨 때문에 문장 중간에서 잘린 조각을 한 문단으로 잇는다(고구마팜·위픽).
    다음 조각이 조사나 문장부호로 시작하면 띄어쓰기 없이 붙인다: '블라인드' + '에 올라왔어요'."""
    out = ""
    for l in _keep(lines):
        out = out + l if (not out or _GLUE.match(l)) else out + " " + l
    return re.sub(r"\s+", " ", out).strip()


# ---------------------------------------------------------------- 메일리 트렌드어워드
MAILY_LISTS = ["https://maily.so/trendaword/posts?keyword=%EB%B0%88", "https://maily.so/trendaword?keyword=%EB%B0%88"]
# 유래를 자르는 기준 배너 — 에디터가 매 회차 같은 파일을 다시 쓴다(파일 주소가 회차마다 바뀌지 않음).
# 메일리 에디터로 쓴 회차와 노션으로 쓴 회차의 파일이 다르다. 2026-09-22 9개 회차 전수 확인:
#   시작 "왜 뜨는걸까?"          1675903273532631 (메일리) / 61433_1673828602 (노션)
#   끝   "디테일로 들어가보자"     1767492999666223 (메일리) / 61433_1673829512 (노션)
#   그 뒤에 나오는 배너(마무리)   1675903298787165 (메일리) / 61433_1673830591 (노션) — 끝 배너가 없을 때의 예비
# 시작 배너 다음에 처음 나오는 끝 배너(또는 예비)에서 자른다.
MAILY_BANNER_START = ("1675903273532631", "61433_1673828602")
MAILY_BANNER_END = ("1767492999666223", "61433_1673829512", "1675903298787165", "61433_1673830591")
MAILY_NAME_RE = re.compile(r"^\d{2}\.\d{2}\.\d{2}\s*\(.\)\s*'(.+)'$")
MAILY_PERSON_RE = re.compile(r"^(\S{1,2}\s?(OO|00)\s*(씨)?|씨)$")


def maily_discover(limit: int = 10) -> list[dict]:
    last_err = None
    for list_url in MAILY_LISTS:
        try:
            p = fetch(list_url)
        except Exception as e:  # 첫 주소가 바뀌었으면 두 번째 주소로
            last_err = e
            continue
        seen, out = set(), []
        for k, v, _ in p.tokens:
            if k == "a" and re.search(r"/trendaword/posts/[0-9a-z]+$", v):
                url = urljoin("https://maily.so", v)
                if url not in seen:
                    seen.add(url)
                    out.append({"url": url})
        if out:
            return out[: limit * 2]  # 휴재 공지 등이 걸러질 걸 대비해 넉넉히
    raise RuntimeError(f"메일리 목록을 못 읽음: {last_err}")


def maily_parse(url: str) -> dict | None:
    """글 1개 = 밈 1개. 부제의 '…' 안이 이름. 구조(이름·용례·활용)가 없으면 None(휴재 공지 등)."""
    p = fetch(url)
    toks = p.tokens
    texts = _texts(toks)
    name = next((m.group(1) for t in texts if (m := MAILY_NAME_RE.match(t))), None)
    if not name or "용례" not in texts or "활용" not in texts:
        return None
    date = next((t for t in texts if re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", t)), "")

    i_use, i_act = texts.index("용례"), texts.index("활용")
    usage = [t for t in texts[i_use + 1:i_act] if not MAILY_PERSON_RE.match(t)]
    usage_example = "\n".join(usage).strip()

    # 유래: '활용' 이후에서 배너① ~ 배너② 사이. 배너가 없는 회차는 '~보자' 다음 ~ '오늘은 여기까지' 앞.
    body, started, in_act = [], False, False
    for k, v, _ in toks:
        if k in ("t", "h", "q") and v == "활용":
            in_act = True
            continue
        if not in_act:
            continue
        if k == "img" and any(b in v for b in MAILY_BANNER_START):
            started, body = True, []
            continue
        if k == "img" and any(b in v for b in MAILY_BANNER_END) and started:
            break
        if k in ("t", "h", "q"):
            if v.startswith("오늘은 여기까지"):
                break
            body.append(v)
    if not started:
        cut = next((i for i, t in enumerate(body) if re.search(r"보자[.!~]*$", t)), None)
        if cut is not None:
            body = body[cut + 1:]
    # 본문에 끼어 있는 '지난 회차 링크 카드'(제목·날짜·조회수)는 유래가 아니다
    body = [t for t in body if not (t.startswith(("[Trend A Word", "조회 ", "hhttp", "·"))
                                    or re.match(r"^\d{2}\.\d{2}\.\d{2}\s*\(", t)
                                    or re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", t))]
    origin = _clean_lines(body)
    # 대표 이미지: '용례' 바로 앞의 카드 이미지(위: 제목, 아래: 설명이 한 장에 다 있는 것).
    # og:image는 이 카드의 윗부분만 잘린 썸네일이라 쓰지 않는다.
    i_tok = next(i for i, (k, v, _) in enumerate(toks) if k in ("t", "h", "q") and v == "용례")
    cards = [v for k, v, _ in toks[:i_tok] if k == "img" and "trendaword" in v]
    image = cards[-1] if cards else p.meta.get("og:image", "")
    return {"source": "maily_trendaword", "source_label": "Trend A Word", "url": url, "name": name,
            "origin": origin, "usage_example": usage_example, "image_url": image, "published_date": date}


# ---------------------------------------------------------------- 고구마팜
GOGUMA_SEARCH = "https://gogumafarm.kr/?s=" + quote("밈 모음")
LABEL_WHAT, LABEL_HOW = "어떤 밈인가요", "이렇게 활용해 보세요"


def gogumafarm_discover(articles: int = 2) -> list[dict]:
    p = fetch(GOGUMA_SEARCH)
    seen, out = set(), []
    for k, v, _ in p.tokens:
        if k != "a" or not v.startswith("https://gogumafarm.kr/"):
            continue
        tail = v[len("https://gogumafarm.kr/"):].strip("/")
        # 글 주소는 한 단계짜리 slug. 카테고리·태그·페이지·검색 링크는 제외.
        if not tail or "/" in tail or tail.startswith(("?", "category", "tag", "page", "author", "wp-")):
            continue
        if v not in seen:
            seen.add(v)
            out.append({"url": v})
    return out[:articles * 3]  # 모음집이 아닌 글이 섞일 걸 대비해 넉넉히(구조로 걸러짐)


def gogumafarm_parse(url: str) -> list[dict]:
    """모음집 1개 → 밈 여러 개. 소제목(h2/h3) ~ 다음 소제목이 한 밈. 라벨이 없는 글은 통째로 스킵."""
    p = fetch(url, mark_class="entry-content")
    toks = [(k, v) for k, v, inmark in p.tokens if inmark]
    if not any(LABEL_WHAT in strip_emoji(v) or LABEL_HOW in strip_emoji(v) for k, v in toks if k != "img"):
        return []  # 모음집 구조가 아님 — 제목이 아니라 구조로 거른다
    all_texts = _texts(p.tokens)
    date = next((t for t in all_texts if re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", t)), "")

    heads = [i for i, (k, _) in enumerate(toks) if k == "h"]
    out = []
    for n, hi in enumerate(heads):
        end = heads[n + 1] if n + 1 < len(heads) else len(toks)
        sec = toks[hi:end]
        labels = [strip_emoji(v) for k, v in sec if k != "img"]
        if not any(LABEL_WHAT in l or LABEL_HOW in l for l in labels):
            continue
        name = strip_emoji(sec[0][1])
        image = next((v for k, v in sec if k == "img"), "")
        what, how, cur = [], [], None
        for k, v in sec[1:]:
            if k == "img" or k == "a":
                continue
            s = strip_emoji(v)
            if LABEL_WHAT in s:
                cur = what
                continue
            if LABEL_HOW in s:
                cur = how
                continue
            if cur is not None:
                cur.append(v)
        is_last = end == len(toks)
        if is_last and len(how) > 1:  # 마지막 밈엔 글 마무리 문단이 딸려 온다 — 마지막 문단 제거
            how = how[:-1]
        out.append({"source": "gogumafarm", "source_label": "고구마팜", "url": url, "name": name,
                    "origin": _join_inline(what), "usage_example": _join_inline(how),
                    "image_url": image, "published_date": date})
    return out


# ---------------------------------------------------------------- 위픽레터
WEPICK_COLLECTION = "https://letter.wepick.kr/post/23942"
WEPICK_STATUS_RE = re.compile(r"^\d{1,2}$")


def wepick_parse_collection(limit: int = 10) -> list[dict]:
    """컬렉션 글 한 페이지에 밈 24개가 다 있다. 항목은 [상세 링크] [썸네일] '01' '🔥 정점' <제목> 한줄정의 '📍' '유래' …
    순서로 시작한다 — 두 자리 번호 바로 뒤(3칸 안)에 제목 태그가 오는 곳을 항목 시작으로 본다.
    (문서에 적힌 'ㅡ' 구분선은 실제 HTML에서는 글자로 나오지 않았다 — 2026-09-22 실측)"""
    p = fetch(WEPICK_COLLECTION)
    toks = [(k, v) for k, v, _ in p.tokens]
    starts = [i for i, (k, v) in enumerate(toks)
              if k == "t" and re.fullmatch(r"\d{2}", v.strip()) and any(kk == "h" for kk, _ in toks[i + 1:i + 4])]
    out = []
    for n, st in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(toks)
        pre = toks[max(0, st - 3):st]  # 번호 앞의 상세 링크·썸네일
        ch = toks[st:end]
        name = strip_emoji(next(v for k, v in ch if k == "h"))
        image = next((v for k, v in reversed(pre) if k == "img"), "")
        detail = next((urljoin("https://letter.wepick.kr", v) for k, v in pre
                       if k == "a" and re.search(r"/post/\d+$", v) and not v.endswith("/23942")), "")
        texts = [v for k, v in ch if k in ("t", "h", "q")]
        i_origin = next((i for i, t in enumerate(texts) if strip_emoji(t) == "유래"), None)
        if i_origin is None:
            continue
        origin, usage, in_quote = [], [], False
        for t in texts[i_origin + 1:]:
            if not in_quote and t.strip() in ('"', "“", "”"):
                in_quote = True  # 여기서부터 인용문 블록 = 활용 예시
                continue
            if not in_quote and t.startswith(('"', '\u201c')) and origin and origin[-1].rstrip().endswith(('.', '!', '?', '다')):
                in_quote = True  # 따옴표가 따로 떨어지지 않고 문장 앞에 붙어 나오는 항목(과자 사꾸). 문장이 끝난 뒤에 올 때만
            if not in_quote and (not strip_emoji(t) or re.match(r"^\d{4}\.\d{2}", t) or t == "중독성"):
                break  # 인용문 없이 분석 섹션으로 넘어가면 유래는 거기까지
            if in_quote and t.strip() in ('"', "\u201c", "\u201d"):
                break  # 두 번째 인용문 블록(분석 섹션 예시)은 활용 예시가 아니다
            if in_quote:
                # 인용문 블록은 이모지 소제목·타임라인(2026.08)·별점이 나오면 끝
                if not strip_emoji(t) or re.match(r"^\d{4}\.\d{2}", t) or t in ("중독성", "변주력", "확산력", "활용도"):
                    break
                usage.append(t.strip('"“” '))
            else:
                origin.append(t)
        # 인용문이 '미리보기 줄 + 전체 줄'로 겹쳐 나오는 경우 — 다른 줄에 포함되는 줄은 뺀다
        usage = [u for u in usage if u and not any(u != o and u in o for o in usage)]
        out.append({"source": "wepick_memepedia", "source_label": "위픽레터 밈피디아",
                    "url": detail or WEPICK_COLLECTION, "name": name, "origin": _join_inline(origin),
                    "usage_example": "\n".join(usage).strip(), "image_url": image, "published_date": ""})
        if len(out) >= limit:
            break
    return out


def wepick_published_date(detail_url: str) -> str:
    """컬렉션엔 밈별 날짜가 없어서, 새 밈만 상세 페이지에서 등록일을 가져온다."""
    if "/post/23942" in detail_url:
        return ""
    p = fetch(detail_url)
    return next((t for t in _texts(p.tokens) if re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", t)), "")


def download_image(url: str, dest) -> bool:
    if not url:
        return False
    r = requests.get(url, headers=UA, timeout=25)
    r.raise_for_status()
    dest.write_bytes(r.content)
    time.sleep(0.5)
    return True
