"""naver_trend.py — 네이버 검색어트렌드로 밈 유행 기간을 잰다 (meme_pipeline.py가 import해서 쓴다).

원본은 효섭이 로컬에서 쓰던 naver_v6.py. 판정 로직(급등 찾기·변형 검색어·이상치 30일 규칙)은
그대로 두고, 파이프라인에서 부르기 좋게 세 가지만 바꿨다:
  · 키를 import 시점이 아니라 첫 호출 때 읽는다(키가 없어도 파이프라인의 다른 단계는 돈다)
  · 호출 상한에 걸리면 프로그램을 끝내지 않고 ApiError를 던진다
  · 원래의 main()(25개 하드코딩 목록 순회)은 뺐다 — 대상 목록은 DB에서 받는다
"""
# -*- coding: utf-8 -*-
"""
naver_v5.py -- 밈 유행기간 수집. 폴백 5단계.

  1단계  밈 이름 그대로 → 검색어트렌드      (대부분 여기서 끝남)
  2단계  실패 → 변형해서 재시도             (고맙투우사, 100드립, 띠로리 …)
  3단계  전부 실패 → 측정 불가

  블로그는 폴백에서 뺐다.
    · 글에 그 말이 있다고 해서 밈으로 쓴 건지 확인할 방법이 없다.
    · 시작일을 보려면 오래된 순으로 읽어야 하는데 API가 최신순만 준다.
    · 블로그 누적 문서수(blog_total)는 참고 자료로만 남긴다.

왜 이 순서인가
  · 원형이 되면 그게 가장 정확한 검색어다. 굳이 변형을 볼 이유가 없고 호출도 아낀다.
  · 변형은 위험해 보이지만(삐에로, 장원영) 충돌 필터가 막는다.
    실측: '삐에로'는 기존어로 밀렸고 '간바레'는 급등 없음으로 탈락했다.
  · '급등 없음'은 날짜를 만들어내지 않는다.
    데이터가 없다가 어느 날부터 생기면 그날을 시작일이라 할 수 있지만,
    쭉 있던 값 중 제일 높은 날을 '밈 시작일'이라 부르는 건 아닌 걸 알면서 쓰는 것이다.
    그래서 정점 날짜는 근거로만 남기고 시작일은 비워 둔다.

신뢰도 점수는 만들지 않는다. 대신 blog_total 원자료를 그대로 저장한다.
  (점수는 우리가 정한 가중치라 기준이 바뀌면 다시 계산해야 한다.
   숫자만 남겨두면 '트렌드 260일인데 블로그 9건'을 언제든 판단할 수 있다.)
"""
import json, os, re, sys, time, statistics, datetime as dt
import urllib.request, urllib.error, urllib.parse

BASE="https://naverapihub.apigw.ntruss.com"; TREND="/search-trend/v1/search"; BLOG="/search/v1/blog"
MAX_CALLS=400; SLEEP=0.35; _calls=0
BACKOFF=2.0   # 2초 -> 4초 -> 8초. 키워드당 최대 14초로 제한한다.
FAIL_FAST=6   # 연속 6개 키워드가 실패하면 전체 중단 (API가 죽은 상태)
TODAY=dt.date.today()
HIST_FROM=TODAY-dt.timedelta(days=730)
RECENT_FROM=TODAY-dt.timedelta(days=365)
RECENT_YM=(TODAY-dt.timedelta(days=182)).strftime("%Y%m")
SPIKE_X=3.0
# 이상치 처리 — 조건 하나뿐이다.
#   정점에서 한 달 넘게 끊긴 구간은 '다른 시기'로 보고 제외한다.
#
# 값(정점의 몇 % 이상이면 살린다) 조건도 만들어봤지만 뺐다.
#   그 기준은 우리가 가진 21개 안의 두 점(15.6 과 87.5)에서 뽑은 숫자였고,
#   표본이 늘면 근거가 사라진다. 지금 데이터에만 맞춘 규칙은 쓰지 않는다.
#
# 30일로 잡은 근거 (21개 시계열 실측):
#   정상 밈의 최대 간격은 17일(띠로리). 한 달이면 정상 구간이 쪼개지지 않는다.
#   한 달 넘게 검색이 완전히 끊겼다면 그 유행은 끝난 것으로 본다.
GAP_DAYS=30

MEMES=["OO 정보","~를 무례하지 않게 말해 주세요","간바레 챌린지","거제 야호","고맙투우사 챌린지",
"과자 사진 꾸미기 (과자 사꾸)","그린그린 레드레드","나만아는100드립",
"난 파라파라나 추고 있어야겠다 오이데~","냐냐냥 밈","누가 돌아왔게","니가 좋아","디오 주간",
"띠로리 대신 띠로리리~↘","모르는개산책","삐에로 밈","셋로그 챌린지","연락없네잘살아",
"일하기전제모습이고요","장원영 OO","장투교","장항준적 사고","천연 위고비","측측측면샷",
"하겠습니다 안 하겠습니다"]

# 사람만 알 수 있는 검색어. 빈칸형은 여기 없으면 포기한다.
#   장원영 OO -> '밤티'의 반대말로 장원영을 붙여 만든 밈이라 '장원영 밤티'가 실제 검색어.
MANUAL={
 "장원영 OO":["장원영 밤티"],
 "난 파라파라나 추고 있어야겠다 오이데~":["파라파라 오이데"],
}

SUFFIX=["밈","챌린지","드립","짤"]; ENDING=["이고요","입니다","이에요","예요","해요","이구요","고요"]
NOISE="~↘↗！!?？·,，.。\"'“”‘’"
SPLIT=re.compile(r'\s*(?:대신|말고|그리고|vs|VS|/)\s*'); BLANK=re.compile(r'(OO|oo|○○|ㅇㅇ|XX|××)')

def variants(name):
    """원형을 뺀 변형 후보들."""
    out=[]
    def add(x):
        x=x.strip()
        if x and len(x)>=2 and x!=name and x not in out: out.append(x)
    base=re.sub(r'\([^)]*\)','',name).strip(); add(base)
    for t in re.findall(r'\(([^)]*)\)',name): add(t)
    clean=re.sub(r'\s+',' ',"".join(c for c in base if c not in NOISE)).strip()
    add(clean); add(clean.replace(" ",""))
    for s in SUFFIX:
        if clean.endswith(s) and len(clean)>len(s)+1: add(clean[:-len(s)].strip())
    parts=[p.strip() for p in SPLIT.split(clean) if len(p.strip())>=2]
    for pc in (parts if len(parts)>1 else [clean]):
        c=pc.replace(" ",""); add(c)
        if len(c)>=3 and c[-1]==c[-2]: add(c[:-1])
        for e in ENDING:
            if c.endswith(e) and len(c)>len(e)+1: add(c[:-len(e)])
    c=clean.replace(" ","")
    m=re.search(r'\d+.*$',c)
    if m and len(m.group())>=3: add(m.group())
    w=clean.split()
    if len(w)>=4: add(" ".join(w[-3:])); add(" ".join(w[-2:]))
    return out[:5]

# ── API
def load_key():
    """환경변수 NAVER_CLIENT_ID/SECRET → naver_key.json(crawling/, backend/, 현재 폴더) 순으로 찾는다.
    키 파일은 커밋하지 않는다(.gitignore의 crawling/* 에 걸려 있음)."""
    cid=os.environ.get("NAVER_CLIENT_ID"); sec=os.environ.get("NAVER_CLIENT_SECRET")
    if not(cid and sec):
        h=os.path.dirname(os.path.abspath(__file__))
        for p in (os.path.join(h,"naver_key.json"),os.path.join(h,"..","backend","naver_key.json"),"naver_key.json"):
            if os.path.exists(p):
                d=json.load(open(p,encoding="utf-8")); cid,sec=d.get("client_id"),d.get("client_secret"); break
    if not(cid and sec): raise ApiError("네이버 API 키 없음 — crawling/naver_key.json 또는 환경변수 NAVER_CLIENT_ID/SECRET")
    return cid,sec

H=None
def _headers():
    """키는 처음 호출할 때 읽는다 — import만 해도 키가 없다고 죽지 않게."""
    global H
    if H is None:
        cid,sec=load_key()
        H={"X-NCP-APIGW-API-KEY-ID":cid,"X-NCP-APIGW-API-KEY":sec,"Content-Type":"application/json"}
    return H
def reset_calls():
    global _calls
    _calls=0

def _g():
    global _calls
    if _calls>=MAX_CALLS: raise ApiError(f"호출 상한 {MAX_CALLS}회 도달")
    _calls+=1

class ApiError(Exception):
    """서버가 대답을 안 한 것. '검색량 0'과 절대 같이 취급하면 안 된다."""

def trend(kw, tries=3):
    """실패 시 점점 더 오래 기다렸다가 재시도. 끝까지 실패하면 예외를 던진다."""
    body={"startDate":HIST_FROM.isoformat(),"endDate":TODAY.isoformat(),"timeUnit":"date",
          "keywordGroups":[{"groupName":kw,"keywords":[kw]}]}
    last=""
    for i in range(tries):
        _g()
        try:
            with urllib.request.urlopen(urllib.request.Request(BASE+TREND,
                data=json.dumps(body).encode(),headers=_headers(),method="POST"),timeout=25) as r:
                d=json.loads(r.read().decode())
            time.sleep(SLEEP)
            res=d.get("results") or []
            return {p["period"]:float(p["ratio"]) for p in (res[0].get("data",[]) if res else [])}
        except urllib.error.HTTPError as e:
            body_txt=e.read().decode("utf-8","replace")[:120]
            last=f"HTTP {e.code} {body_txt}"
            wait=BACKOFF*(2**i)
            if i==tries-1: break
            if i < tries-1: print(f"        (재시도 {i+1}/{tries-1} — {last} / {wait:.0f}초 대기)")
            time.sleep(wait)
        except Exception as e:
            last=str(e)[:120]; time.sleep(BACKOFF*(2**i))
    raise ApiError(last)

def blog_call(kw,display=100,start=1,tries=4):
    u=f"{BASE}{BLOG}?query={urllib.parse.quote(kw)}&display={display}&start={start}&sort=date"
    last=""
    for i in range(tries):
        _g()
        try:
            with urllib.request.urlopen(urllib.request.Request(u,headers=_headers()),timeout=25) as r:
                d=json.loads(r.read().decode())
            time.sleep(SLEEP); return d
        except urllib.error.HTTPError as e:
            last=f"HTTP {e.code}"; time.sleep(BACKOFF*(2**i))
        except Exception as e:
            last=str(e)[:80]; time.sleep(BACKOFF*(2**i))
    raise ApiError(last)

# ── 분석
def spike(kw):
    """급등 구간. 없으면 사유와 함께 None."""
    pts=trend(kw)                                       # 실패하면 ApiError가 올라간다
    if not pts:     return None,"검색량 0",None          # 응답 자체가 빔 -> 4단계로
    rec={d:v for d,v in pts.items() if dt.date.fromisoformat(d)>=RECENT_FROM}
    if not rec:     return None,"최근 1년 신호 없음",pts
    base=[v for d,v in pts.items() if dt.date.fromisoformat(d)<RECENT_FROM]
    n=(RECENT_FROM-HIST_FROM).days
    vals=base+[0.0]*max(0,n-len(base))
    p90=statistics.quantiles(vals,n=10)[8] if len(vals)>10 else (max(vals) if vals else 0)
    pd_,pv=max(rec.items(),key=lambda kv:kv[1])
    thr=max(p90*SPIKE_X, pv*0.10)
    above=sorted(d for d,v in rec.items() if v>=thr)
    if not above: return None,"급등 없음(과거와 비슷한 수준)",pts

    # 정점 덩어리를 찾고, 거기서 떨어진 날 중 '값이 작은' 것만 이상치로 뺀다.
    pi=above.index(pd_); lo=hi=pi
    D=lambda x: dt.date.fromisoformat(x)
    while lo>0  and (D(above[lo])-D(above[lo-1])).days<=GAP_DAYS: lo-=1
    while hi<len(above)-1 and (D(above[hi+1])-D(above[hi])).days<=GAP_DAYS: hi+=1
    dropped=above[:lo]+above[hi+1:]      # 덩어리 밖은 전부 다른 시기로 본다
    above=above[lo:hi+1]

    s,e=above[0],above[-1]
    return {"keyword":kw,"start":s,"end":e,"dropped":dropped,
            "dropped_values":[round(rec[d],1) for d in dropped],
            "span":(dt.date.fromisoformat(e)-dt.date.fromisoformat(s)).days+1,
            "active":len(above),"peak":pd_,
            "ongoing":(TODAY-dt.date.fromisoformat(e)).days<=7,
            "pre_existing":p90>0,"base_p90":round(p90,1)},"급등",pts

def peak_date_of(pts):
    """급등이 아닐 때, 근거로 남길 '최근 구간에서 가장 높았던 날'."""
    rec={d:v for d,v in pts.items() if dt.date.fromisoformat(d)>=RECENT_FROM}
    return max(rec.items(),key=lambda kv:kv[1])[0] if rec else None

def blog_stat(kw,cap=300):
    f=blog_call(kw,display=1)
    if not f: return {"total":0,"keyword":kw}
    total=f.get("total",0)
    if not total: return {"total":0,"keyword":kw}
    dates=[]
    for st in range(1,min(cap,1000),100):
        d=blog_call(kw,display=100,start=st)
        if not d or not d.get("items"): break
        dates+=[i["postdate"] for i in d["items"] if i.get("postdate")]
        if len(d["items"])<100: break
    if not dates: return {"total":total,"keyword":kw}
    dates.sort(); ms={}
    for x in dates: ms[x[:6]]=ms.get(x[:6],0)+1
    recent=sum(c for m,c in ms.items() if m>=RECENT_YM)/len(dates)
    return {"total":total,"keyword":kw,"sampled":len(dates),"complete":total<=len(dates),
            "first":dates[0] if total<=len(dates) else None,"last":dates[-1],
            "recent_share":round(recent,2),"months":ms}

def blog_total_only(kw):
    """신뢰도 점수 대신 남기는 원자료. 1회 호출."""
    f=blog_call(kw,display=1)
    return (f or {}).get("total",0)

# ── 실행
def resolve(name):
    try:
        return _resolve(name)
    except ApiError as e:
        print(f"   [!] 조회 실패 — {e}")
        print("       '측정 불가'가 아니라 '아직 못 쟀음'이다. 다시 돌리면 이것만 재시도한다.")
        return {"method":"error","reason":str(e),"trend":None,"blog":None}

def _resolve(name):
    print("="*72); print(f"■ {name}")
    if BLANK.search(name) and name not in MANUAL:
        print("   1단계  건너뜀 — 빈칸형(OO). 문자열 자체가 검색어가 아님")
        return {"method":"none","reason":"빈칸형","trend":None,"blog":None}

    order = MANUAL.get(name, [name]) + ([] if name in MANUAL else variants(name))
    first_pts=None; hits=[]
    for i,kw in enumerate(order):
        r,why,pts=spike(kw)
        stage="1단계" if i==0 else "2단계"
        if r:
            print(f"   {stage}  '{kw}' → {'기존어' if r['pre_existing'] else '신조어'} "
                  f"급등 {r['start']}~{r['end']} ({r['span']}일/{r['active']}일) "
                  f"{'진행중' if r['ongoing'] else '종료'}")
            if r.get("dropped"):
                d0=r["dropped"]; dv=r.get("dropped_values",[])
                gap=(dt.date.fromisoformat(r["start"])-dt.date.fromisoformat(d0[-1])).days
                pairs=[f"{a}({b})" for a,b in zip(d0,dv)][:4]
                print(f"          {len(d0)}일 제외 — 본 구간에서 {gap}일 끊김: "
                      f"{', '.join(pairs)}{' …' if len(d0)>4 else ''}")
            hits.append(r)
            if i==0 and not r["pre_existing"]:
                print("          → 원형이 신조어로 잡힘. 변형 생략")
                break
        else:
            print(f"   {stage}  '{kw}' → {why}")
            if i==0: first_pts=pts

    if hits:
        best=max(hits,key=lambda r:(not r["pre_existing"], len(r["keyword"])))
        print(f"   => 채택 '{best['keyword']}'  {best['start']} ~ {best['end']}")
        return {"method":"spike","trend":best,"blog":{"total":blog_total_only(best["keyword"])}}

    pk = peak_date_of(first_pts) if first_pts else None

    b={"total":blog_total_only(name)}     # 참고용 숫자만. 폴백으로는 쓰지 않는다
    if pk:
        reason=("급등 없음 — 원래 쓰이던 말이라 밈으로 뜬 시점을 검색량만으로 분리할 수 없음")
        print(f"   3단계  측정 불가 — {reason}")
        print(f"          (근거: 최근 1년 최고치는 {pk}. 시작일로 쓰지 않는다)")
    else:
        reason="신호 없음 — 검색량 0"
        print(f"   3단계  측정 불가 — {reason}")
    return {"method":"none","reason":reason,"trend":None,"blog":b,
            "evidence":{"peak_date":pk} if pk else None}

