import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AdAPI, CharacterAPI, HistoryAPI, MemeAPI, ProductionAPI, StoreAPI, StoryboardAPI, TrendAPI,
} from '../api/client.js';

/** 그림 생성 진행을 확인하는 간격. 백엔드가 generating=false를 주면 멈춘다. */
const POLL_MS = 3000;
/** 안전장치 — 백엔드가 영영 끝났다고 말해주지 않아도 25분이면 폴링을 멈춘다. */
const POLL_MAX_TICKS = 500;

/** 트렌드 밈 하나를 스토리보드의 "밈 카드 추가(원문 붙여넣기)" 칸 모양으로 바꾼다.
 *  유래+활용예시를 합쳐 원문 자리에 넣는다 — 카드 만들기가 요약이 아니라 원문을 봐야
 *  제대로 되기 때문(meme_ai.py 참고). 트렌드 참고로 왔으면 그 밈으로 카드를 만들라는
 *  뜻이라 원문까지 채운다("밈 고르기"에서 기존 카드를 고를 때와는 다르게 취급한다 —
 *  거긴 새 카드를 만드는 자리가 아니라서 원문을 안 채운다). 유래·활용예시가 둘 다
 *  없으면 null(채울 게 없다). */
function trendMemeDraft(m) {
  const text = [m.origin, m.summary].filter(Boolean).join('\n\n').trim();
  if (!text) return null;
  return { memeTitle: m.name, memeSource: m.url || m.sourceLabel || '', memeText: text };
}

/** 오늘 날짜(YYYY-MM-DD). toISOString()은 UTC라서 한국 시간 오전 9시 전에는 어제가 나온다 —
 *  새벽에 만든 걸 기록하는 가게가 많아서 그대로 쓰면 하루씩 밀린다. */
function today() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/** 시트 8칸을 PUT /api/character 모양으로 모은다. 키워드만 쉼표 문자열 ↔ 배열로 옮긴다 —
 *  사장님은 한 칸에 쉼표로 적고, 백엔드는 목록으로 들고 있는다. */
function sheetFields(s) {
  return {
    name: s.charName, age: s.charAge, gender: s.charGender, look: s.charLook,
    outfit: s.charOutfit, abilities: s.charAbilities, desc: s.charDesc,
    keywords: (s.charKeywords || '').split(',').map((k) => k.trim()).filter(Boolean),
  };
}

/** 처음 상태는 전부 비어 있다. 화면에 보이는 값은 사장님이 입력했거나 백엔드가 준 것뿐이다.
 *  여기에 예시 값을 하나라도 넣으면 그건 사장님이 만든 적 없는 데이터가 되어
 *  히스토리·내보내기에 그대로 섞인다. */
function initialState() {
  return {
    screen: 'home',
    stack: [],
    toast: '',
    loading: true,
    loadError: '',

    storeSaved: false, storeReadOnly: false,
    storeCategory: '', storeAddress: '', storeHours: '',
    storeOpenTime: '', storeCloseTime: '', storeClosedDays: [],
    storeDesc: '', storeImages: [], storeMaxImages: 5,

    // 캐릭터 시트 8칸. 대화로 채워지고, 시트에서 직접 고칠 수도 있다.
    charName: '', charAge: '', charGender: '', charLook: '',
    charOutfit: '', charAbilities: '', charDesc: '', charKeywords: '',
    // 백엔드가 준 시트 상태 — 어느 칸이 비었는지, 그림 뽑기를 열어도 되는지.
    charSheet: [], charSheetDone: false, charMissing: [], charEditing: '', charPending: {},
    charMsgs: [], charInput: '', charThinking: false,
    charCands: [], charSelected: -1,
    charConfirmed: false, charInfoReadOnly: true,
    // 그림 생성 진행 상태 — 백엔드가 준 값이다. 화면의 "약 N초 남았어요"가 여기서 나온다.
    charGenerating: false, charQueue: 0, charEta: 0,

    adType: '', adConcept: '',
    // 홈에서 "광고 만들기"를 누르면 트렌드를 쓸지 먼저 물어보는 팝업.
    adEntryOpen: false,

    // 트렌드 확인 — /api/trend가 준 밈 목록을 그대로 두고, 필터/검색/정렬/선택은 화면에서만 쓴다.
    trendItems: [], trendSites: [],
    trendFilter: '전체', trendSearch: '', trendSort: '최신순', trendSel: '',
    // 활용 상황 안에서 GPT 추천 — note는 "오늘 알릴 내용"(선택). result는 {meme, reason} | null.
    // popupOpen은 트렌드 화면에 들어올 때마다 Trend.jsx가 true로 켠다.
    trendRecommendNote: '', trendRecommendLoading: false, trendRecommendResult: null,
    trendRecommendPopupOpen: false,

    sbMsgs: [], sbInput: '', sbThinking: false,
    plan: [], sbProdLogged: false, sbSetOpen: false, sbProdOpen: false, pending: {},
    // 네컷 그림 칸과 진행 상태 — 캐릭터 후보와 같은 규칙(status: empty|generating|done|failed)
    comicCuts: [], sbGenerating: false, sbEta: 0,
    // "보관함에 저장"을 한 번 누르면 같은 구성으로 또 눌러도 중복 저장 안 되게 잠근다.
    // 네컷을 새로 그리면(makeComic) 그건 다른 구성이니 다시 저장할 수 있게 풀어준다.
    savedThisAd: false,
    // 밈 카드 목록과 "밈으로 스토리 제안" 입력란
    memes: [], memeId: '', memeTitle: '', memeSource: '', memeText: '',
    // memeTitle/memeSource/memeText가 트렌드 밈에서 채워졌는지 — 스토리보드가 배지 표시에 쓴다.
    // memeDraftTrendId는 그 채운 내용이 "어느 트렌드 밈" 것인지 — 트렌드에서 더 보기로 다른
    // 밈을 새로 고르고 왔을 때 옛 내용인지 판단하는 데 쓴다(applyAd 참고).
    memeDraftFromTrend: false, memeDraftTrendId: '',

    myTab: 'history', history: [],

    items: [], prods: [],
    newItem: '', draftItem: '', draftQty: '', draftDate: today(), draftTime: '', draftSold: '',

    notifOpen: false, backupNote: '', backupErr: false,
  };
}

export function useAdMakerState() {
  const [state, setState] = useState(initialState);
  const toastTimer = useRef(null);
  const stateRef = useRef(state);
  stateRef.current = state;

  const update = useCallback((patch) => {
    setState((s) => ({ ...s, ...(typeof patch === 'function' ? patch(s) : patch) }));
  }, []);

  const set = useCallback((field, value) => update({ [field]: value }), [update]);

  const toast = useCallback((msg) => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    update({ toast: msg });
    toastTimer.current = setTimeout(() => update({ toast: '' }), 2600);
  }, [update]);

  const fail = useCallback((e) => toast(e.message || '요청에 실패했어요'), [toast]);

  // ---------- 캐릭터 그림 생성 폴링 ----------
  // 생성은 백그라운드로 돈다(1장 약 56초). POST는 즉시 돌아오고 칸만 'generating'으로
  // 생기므로, GET /api/character를 3초마다 불러서 그림이 채워지는지 확인한다.
  const pollRef = useRef(null);
  const tickRef = useRef(0);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    tickRef.current = 0;
  }, []);

  const startPolling = useCallback(() => {
    if (pollRef.current) return;
    tickRef.current = 0;
    pollRef.current = setInterval(async () => {
      tickRef.current += 1;
      if (tickRef.current > POLL_MAX_TICKS) {
        stopPolling();
        toast('그림 그리기가 너무 오래 걸리고 있어요. 새로고침한 뒤 다시 뽑아주세요.');
        return;
      }
      try {
        const progress = await CharacterAPI.getProgress();
        update(progress);
        // 네컷도 같은 폴링으로 본다 — 그리는 중일 때만 물어본다.
        let sbBusy = false;
        if (stateRef.current.sbGenerating) {
          const sb = await StoryboardAPI.get();
          update(sb);
          sbBusy = sb.sbGenerating;
        }
        // generating=false면 끝났다는 뜻이다. 칸 상태를 하나씩 보고 판단하면
        // 실패(failed) 칸이 섞였을 때 폴링이 안 멈춘다.
        if (!progress.charGenerating && !sbBusy) stopPolling();
      } catch {
        // 한 번 실패했다고 멈추지 않는다 — 잠깐 끊긴 것일 수 있으니 다음 차례에 다시 묻는다.
      }
    }, POLL_MS);
  }, [update, stopPolling, toast]);

  useEffect(() => () => {
    stopPolling();
    if (toastTimer.current) clearTimeout(toastTimer.current);
  }, [stopPolling]);

  /** 생성을 시작시키는 요청들의 공통 처리 — 응답을 반영하고, 그리는 중이면 폴링을 켠다. */
  const runGenerating = useCallback(async (call) => {
    try {
      const progress = await call();
      update(progress);
      if (progress.charGenerating) startPolling();
      return true;
    } catch (e) {
      fail(e);
      return false;
    }
  }, [update, startPolling, fail]);

  // ---------- 처음 불러오기 ----------
  useEffect(() => {
    (async () => {
      try {
        const [store, character, ad, storyboard, items, prods, history, memes, trend] = await Promise.all([
          StoreAPI.get(), CharacterAPI.get(), AdAPI.get(), StoryboardAPI.get(),
          ProductionAPI.listItems(), ProductionAPI.listRecords(), HistoryAPI.list(),
          // 밈 카드는 없어도 앱이 떠야 한다 — 실패하면 빈 목록.
          MemeAPI.list().catch(() => []),
          TrendAPI.list(),
        ]);
        update({
          ...store, ...character, ...ad, ...storyboard, ...trend,
          items, prods, history, memes,
          storeReadOnly: store.storeSaved,
          draftItem: items[0] || '',
          loading: false,
        });
        // 화면을 닫았다 다시 열어도 그리던 게 이어져야 한다. 생성은 서버에서 도니까
        // 폴링만 다시 걸면 된다.
        if (character.charGenerating) startPolling();
      } catch (e) {
        update({ loading: false, loadError: e.message || '백엔드에 연결할 수 없어요' });
      }
    })();
  }, [update, startPolling]);

  // ---------- 화면 이동 (전부 로컬 UI 상태) ----------
  const go = useCallback((screen) => {
    update((s) => ({ screen, stack: [...s.stack, s.screen] }));
  }, [update]);

  const back = useCallback(() => {
    update((s) => {
      const stack = [...s.stack];
      const prev = stack.pop();
      return { screen: prev || 'home', stack };
    });
  }, [update]);

  const goHome = useCallback(() => update({ screen: 'home', stack: [] }), [update]);
  const reload = useCallback(() => window.location.reload(), []);

  const charLocked = !state.storeSaved;
  const adLocked = !state.charConfirmed;

  const goStore = useCallback(() => go('store'), [go]);
  const goChar = useCallback(() => {
    if (charLocked) { toast('가게 정보를 먼저 저장해주세요'); return; }
    go('char');
  }, [charLocked, go, toast]);
  const goAd = useCallback(() => {
    if (adLocked) { toast('캐릭터를 먼저 확정해주세요'); return; }
    go('ad');
  }, [adLocked, go, toast]);
  const goMy = useCallback(() => { update({ myTab: 'history' }); go('my'); }, [go, update]);
  const openProdTab = useCallback(() => { update({ myTab: 'prod', notifOpen: false }); go('my'); }, [go, update]);
  const goData = useCallback(() => { update({ myTab: 'data', notifOpen: false }); go('my'); }, [go, update]);
  const goTrend = useCallback(() => go('trend'), [go]);

  /** 트렌드 화면에서 고른 밈을 들고 광고 만들기로 넘어간다. 고른 밈(trendSel)은 상태에 그대로
   *  남아있으니 Ad 화면이 그 id로 다시 찾아서 요약에 보여준다 — 별도 필드를 안 만든다. */
  const useTrendMeme = useCallback(() => {
    if (!stateRef.current.trendSel) { toast('먼저 밈을 골라주세요'); return; }
    goAd();
  }, [toast, goAd]);

  /** 활용 상황 카테고리 안에서 GPT 추천을 받는다. "전체"는 범위가 너무 넓어서 막는다.
   *  성공하면 추천 요청 팝업은 닫고 결과 팝업으로 넘어간다 — 실패하면 요청 팝업에 그대로
   *  남겨서 사장님이 카테고리/한줄입력을 고쳐 다시 시도할 수 있게 한다. */
  const recommendTrendMeme = useCallback(async () => {
    const s = stateRef.current;
    if (!s.trendFilter || s.trendFilter === '전체') { toast('먼저 활용 상황을 골라주세요'); return; }
    update({ trendRecommendLoading: true });
    try {
      const result = await TrendAPI.recommend(s.trendFilter, s.trendRecommendNote.trim());
      update({ trendRecommendResult: result, trendRecommendLoading: false, trendRecommendPopupOpen: false });
    } catch (e) {
      update({ trendRecommendLoading: false });
      fail(e);
    }
  }, [update, toast, fail]);

  const closeTrendRecommend = useCallback(() => update({ trendRecommendResult: null }), [update]);

  /** 추천받은 밈을 그대로 고른 걸로 치고 광고 만들기로 넘어간다. */
  const useTrendRecommendMeme = useCallback(() => {
    const s = stateRef.current;
    if (!s.trendRecommendResult) return;
    update({ trendSel: s.trendRecommendResult.meme.id, trendRecommendResult: null });
    goAd();
  }, [update, goAd]);

  /** 홈의 "광고 만들기"는 곧바로 광고 화면으로 가지 않고, 트렌드를 참고할지부터 묻는다.
   *  잠금 확인은 여기서 한 번만 하면 된다 — 팝업의 두 선택지(goTrend/goAd) 모두 이미
   *  캐릭터가 확정된 뒤에만 열리므로 다시 안 막아도 된다. */
  const openAdEntry = useCallback(() => {
    if (adLocked) { toast('캐릭터를 먼저 확정해주세요'); return; }
    update({ adEntryOpen: true });
  }, [adLocked, toast, update]);
  const closeAdEntry = useCallback(() => update({ adEntryOpen: false }), [update]);
  const pickAdEntryTrend = useCallback(() => { update({ adEntryOpen: false }); goTrend(); }, [update, goTrend]);
  /** "트렌드 없이 바로 만들기" — 이전에 트렌드에서 밈을 고른 적이 있어도(trendSel) 이번엔
   *  참고 안 하겠다는 선택이니 지운다. applyAd()가 trendSel을 보고 "밈 카드 추가" 칸을
   *  미리 채우는데, 지난번 트렌드 선택이 남아 있으면 이번에도 그 내용이 다시 채워져
   *  버린다 — memeTitle/memeSource/memeText(아직 카드로 안 만든 초안)도 같이 비워서
   *  스토리보드의 "밈으로 스토리 제안받기"가 깨끗한 상태로 시작하게 한다. 이미 만들어 둔
   *  밈 카드 목록(memes)이나 그중 고른 카드(memeId)는 트렌드와 무관한 데이터라 안 건드린다
   *  — "스토리 제안받기" 버튼은 그대로 정상 동작(카드 고르면 활성화)한다. */
  const pickAdEntryDirect = useCallback(() => {
    update({ adEntryOpen: false, trendSel: '', memeTitle: '', memeSource: '', memeText: '', memeDraftFromTrend: false, memeDraftTrendId: '' });
    goAd();
  }, [update, goAd]);

  // ---------- 가게 정보 ----------
  const editStore = useCallback(() => { update({ storeReadOnly: false }); toast('편집할 수 있어요'); }, [update, toast]);

  const saveStore = useCallback(async () => {
    const s = stateRef.current;
    try {
      await StoreAPI.update({
        category: s.storeCategory, address: s.storeAddress, desc: s.storeDesc,
        open_time: s.storeOpenTime, close_time: s.storeCloseTime, closed_days: s.storeClosedDays,
      });
      // 빈 칸이 있으면 여기서 400 + 무엇이 비었는지가 온다. 그 문장을 그대로 보여준다.
      const updated = await StoreAPI.save();
      update({ ...updated, storeReadOnly: true });
      toast('가게 정보를 저장했어요');
    } catch (e) { fail(e); }
  }, [update, toast, fail]);

  const toggleClosedDay = useCallback((day) => {
    update((s) => ({
      storeClosedDays: s.storeClosedDays.includes(day)
        ? s.storeClosedDays.filter((d) => d !== day)
        : [...s.storeClosedDays, day],
    }));
  }, [update]);

  const uploadStoreImage = useCallback(async (file) => {
    try { update(await StoreAPI.uploadImage(file)); toast('사진을 올렸어요'); } catch (e) { fail(e); }
  }, [update, toast, fail]);

  const deleteStoreImage = useCallback(async (i) => {
    try { update(await StoreAPI.deleteImage(i)); toast('사진을 지웠어요'); } catch (e) { fail(e); }
  }, [update, toast, fail]);

  // ---------- 캐릭터 ----------
  const sendChar = useCallback(async () => {
    const text = stateRef.current.charInput.trim();
    if (!text) return;
    update((s) => ({ charInput: '', charThinking: true, charMsgs: [...s.charMsgs, { role: 'me', kind: 'text', text }] }));
    await runGenerating(() => CharacterAPI.chat(text));
    update({ charThinking: false });
  }, [update, runGenerating]);

  /** 시트를 직접 고쳤을 때 저장한다. 칸에서 포커스가 빠질 때 부른다 —
   *  타이핑 한 글자마다 PUT을 날리면 폰에서 느려지고, 저장 버튼을 따로 두면
   *  사장님이 안 누르고 넘어간다. */
  const saveCharSheet = useCallback(async () => {
    try {
      update(await CharacterAPI.update(sheetFields(stateRef.current)));
    } catch (e) { fail(e); }
  }, [update, fail]);

  /** 시트에서 칸을 눌러 대화로 고치겠다고 알린다. */
  const focusCharField = useCallback(async (field) => {
    await runGenerating(() => CharacterAPI.focus(field));
  }, [runGenerating]);

  /** AI 제안(퍼스널 키워드·시트 수정)을 받아들인다. 시트 값이 바뀌므로 전체를 다시 받는다. */
  const acceptCharSuggestion = useCallback(async (pid) => {
    try {
      update(await CharacterAPI.acceptSuggestion(pid));
    } catch (e) { fail(e); }
  }, [update, fail]);

  const declineCharSuggestion = useCallback(async (pid) => {
    try {
      update(await CharacterAPI.declineSuggestion(pid));
    } catch (e) { fail(e); }
  }, [update, fail]);

  // 시트에 타이핑한 내용은 브라우저 상태에만 있다 — 생성 전에 서버로 먼저 보낸다.
  // 안 그러면 서버의 옛 값으로 그려지거나 "아직 안 채운 칸이 있어요" 400이 난다.
  // runGenerating 안에서 부르므로 PUT이 실패해도 같은 경로(fail)로 토스트가 뜬다.
  const syncCharSheet = useCallback(() => CharacterAPI.update(sheetFields(stateRef.current)), []);

  /** 후보 3장 뽑기. 시트가 덜 찼으면 백엔드가 400 + 남은 칸 이름을 돌려준다. */
  const genCandidates = useCallback(async () => {
    const s = stateRef.current;
    // 화면에서도 한 번 막는다 — 눌러놓고 에러를 보는 것보다 눌리지 않는 게 낫다.
    if (!s.charSheetDone) {
      toast(`시트를 먼저 다 채워주세요 — ${s.charMissing.join(', ')}이(가) 비었어요`);
      return;
    }
    update({ charThinking: true });
    await runGenerating(async () => { await syncCharSheet(); return CharacterAPI.genCandidates(); });
    update({ charThinking: false });
  }, [update, runGenerating, toast, syncCharSheet]);

  const selectCand = useCallback(async (i) => {
    await runGenerating(() => CharacterAPI.select(i));
  }, [runGenerating]);

  const rerollCand = useCallback(async (i) => {
    await runGenerating(async () => { await syncCharSheet(); return CharacterAPI.rerollCandidate(i); });
  }, [runGenerating, syncCharSheet]);

  const loadChar = useCallback(async () => {
    // 확정된 캐릭터가 없으면 400 — 예전처럼 없는 캐릭터를 지어내지 않는다.
    await runGenerating(() => CharacterAPI.loadPrevious());
  }, [runGenerating]);

  /** 대화가 꼬였을 때 캐릭터만 처음 상태로. 가게 정보나 생산 기록은 건드리지 않는다. */
  const resetChar = useCallback(async () => {
    try {
      stopPolling();
      const cleared = await CharacterAPI.reset();
      update({ ...cleared, charInput: '', charThinking: false, charInfoReadOnly: true });
      toast('캐릭터를 처음 상태로 되돌렸어요');
    } catch (e) { fail(e); }
  }, [update, toast, fail, stopPolling]);

  const confirmChar = useCallback(async () => {
    const s = stateRef.current;
    if (s.charSelected < 0) { toast('마음에 드는 그림을 먼저 골라주세요'); return; }
    try {
      await CharacterAPI.update(sheetFields(s));
      const updated = await CharacterAPI.confirm();
      update({ ...updated, charInfoReadOnly: true });
      toast('캐릭터를 확정했어요');
      go('charInfo');
    } catch (e) { fail(e); }
  }, [update, toast, fail, go]);

  const toggleCharEdit = useCallback(async () => {
    const s = stateRef.current;
    if (!s.charInfoReadOnly) {
      try {
        const updated = await CharacterAPI.update(sheetFields(s));
        update({ ...updated, charInfoReadOnly: true });
        toast('캐릭터 정보를 저장했어요');
      } catch (e) { fail(e); }
    } else {
      update({ charInfoReadOnly: false });
    }
  }, [update, toast, fail]);

  // ---------- 광고 설정 ----------
  // 트렌드 조사는 없앴다. 종류와 컨셉만 고르면 바로 구성 단계로 간다.
  const applyAd = useCallback(async () => {
    const s = stateRef.current;
    try {
      await AdAPI.update({ ad_type: s.adType, ad_concept: s.adConcept });
      // 앞 단계가 안 끝났으면 400 + 무엇이 남았는지가 온다.
      const res = await AdAPI.apply();
      const sb = await StoryboardAPI.get();
      // 광고 설정을 새로 확정하면 백엔드가 스토리보드를 처음 상태로 되돌린다(reset_storyboard) —
      // 이전에 만든 다른 광고를 저장한 적이 있어도 이건 새 구성이니 다시 저장할 수 있게 푼다.
      update({ ...sb, savedThisAd: false });

      // 트렌드 확인 화면에서 밈을 고르고 왔으면, 스토리보드의 "밈으로 스토리 제안받기"
      // 원문 붙여넣기 칸을 미리 채워둔다 — 크롤링 원문을 다시 복붙 안 해도 되게.
      // 카드 자체는 자동으로 안 만든다 — "카드 만들기"는 사장님이 눌러야 한다(GPT 호출이라
      // 화면 전환만으로 조용히 돌리지 않는다). 이미 직접 입력해 둔 게 있으면 안 덮어쓴다 —
      // 다만 그 내용이 "지난번 트렌드 선택"에서 자동으로 채워진 거고 이번엔 트렌드에서
      // 더 보기로 다른 밈을 새로 골라 왔으면(memeDraftTrendId가 다름), 옛 내용이라 새로
      // 채운다 — 옛 카드 선택(memeId)도 새 밈과 안 맞으니 같이 비운다.
      const trendMeme = s.trendItems.find((m) => m.id === s.trendSel);
      const staleTrendDraft = s.memeDraftFromTrend && s.memeDraftTrendId !== s.trendSel;
      const draft = trendMeme && (!s.memeTitle || staleTrendDraft) ? trendMemeDraft(trendMeme) : null;
      if (draft) update({ ...draft, memeId: '', memeDraftFromTrend: true, memeDraftTrendId: trendMeme.id });

      if (res?.message) toast(res.message);
      go('sb');
    } catch (e) { fail(e); }
  }, [update, toast, fail, go]);

  // ---------- 광고 구성(스토리보드) ----------
  const toggleSbSet = useCallback(() => update((s) => ({ sbSetOpen: !s.sbSetOpen })), [update]);
  const toggleSbProd = useCallback(() => update((s) => ({ sbProdOpen: !s.sbProdOpen })), [update]);

  const sendSb = useCallback(async () => {
    const text = stateRef.current.sbInput.trim();
    if (!text) return;
    update((st) => ({ sbInput: '', sbThinking: true, sbMsgs: [...st.sbMsgs, { role: 'me', kind: 'text', text }] }));
    try {
      const updated = await StoryboardAPI.chat(text);
      update({ ...updated, sbThinking: false });
    } catch (e) { update({ sbThinking: false }); fail(e); }
  }, [update, fail]);

  const confirmPending = useCallback(async (pid) => {
    try { update(await StoryboardAPI.confirm(pid)); toast('반영했어요'); } catch (e) { fail(e); }
  }, [update, toast, fail]);

  const declinePending = useCallback(async (pid) => {
    try { update(await StoryboardAPI.decline(pid)); } catch (e) { fail(e); }
  }, [update, fail]);

  // ---------- 네컷 그림 ----------
  const makeComic = useCallback(async () => {
    try {
      const sb = await StoryboardAPI.makeComic();
      // 새로 그린 네컷은 지금까지 저장한 것과 다른 구성이니 다시 저장할 수 있게 푼다.
      update({ ...sb, savedThisAd: false });
      if (sb.sbGenerating) startPolling();
    } catch (e) { fail(e); }
  }, [update, startPolling, fail]);

  const rerollCut = useCallback(async (n) => {
    try {
      const sb = await StoryboardAPI.rerollCut(n);
      update(sb);
      if (sb.sbGenerating) startPolling();
    } catch (e) { fail(e); }
  }, [update, startPolling, fail]);

  // ---------- 밈으로 스토리 제안 ----------
  /** "밈 고르기"에서 이미 만들어 둔 카드를 고르면, 이름·출처는 "밈 카드 직접 추가" 칸에도
   *  같이 비춰준다 — 무엇을 골랐는지 바로 보이게. 원문(memeText)까지 채우진 않는다
   *  — 그 칸은 새 카드를 만들 때 쓰는 자리라, 이미 있는 카드의 원문을 다시 채워 넣으면
   *  "카드 만들기"를 눌렀을 때 똑같은 카드가 하나 더 생기는 혼동만 만든다. 빈 값으로
   *  고르면(밈 고르기) 세 칸 다 비운다. */
  const pickMemeCard = useCallback((id) => {
    const card = stateRef.current.memes.find((m) => String(m.id) === String(id));
    update({
      memeId: id,
      memeTitle: card ? card.title : '',
      memeSource: card ? card.source : '',
      memeText: '',
      memeDraftFromTrend: false,
      memeDraftTrendId: '',
    });
  }, [update]);

  const proposeStory = useCallback(async () => {
    const id = Number(stateRef.current.memeId);
    if (!id) { toast('밈을 먼저 골라주세요'); return; }
    update({ sbThinking: true });
    try {
      const sb = await StoryboardAPI.propose(id);
      update({ ...sb, sbThinking: false });
    } catch (e) { update({ sbThinking: false }); fail(e); }
  }, [update, toast, fail]);

  const addMeme = useCallback(async () => {
    const s = stateRef.current;
    update({ sbThinking: true });
    try {
      const meme = await MemeAPI.create({ title: s.memeTitle.trim(), source: (s.memeSource || '').trim(), original: s.memeText.trim() });
      update((st) => ({ memes: [...st.memes, meme], memeId: String(meme.id), memeTitle: '', memeSource: '', memeText: '', sbThinking: false }));
      toast(`'${meme.title}' 카드를 만들었어요 (이해도 ${Math.round((meme.card.understanding || 0) * 100)}%)`);
    } catch (e) { update({ sbThinking: false }); fail(e); }
  }, [update, toast, fail]);

  // ---------- 결과 / 저장 ----------
  const openResult = useCallback(() => {
    if (!stateRef.current.plan.length) { toast('먼저 대화로 컷 구성을 만들어주세요'); return; }
    go('result');
  }, [go, toast]);
  const backToSb = useCallback(() => update((s) => ({ screen: 'sb', stack: s.stack.filter((x) => x !== 'result') })), [update]);
  const confirmResult = useCallback(() => go('save'), [go]);

  const download = useCallback(async () => {
    const s = stateRef.current;
    if (!s.plan.length) { toast('저장할 구성이 없어요'); return; }
    if (s.savedThisAd) { toast('이미 보관함에 저장했어요'); return; }
    try {
      const entry = await HistoryAPI.add({
        title: `${s.adType} · ${s.adConcept}`,
        meta: `${s.plan.length}컷 구성`,
        cuts: s.plan.map((c) => ({ n: c.n, short: c.short || '', line: c.line || '' })),
      });
      update((st) => ({ history: [entry, ...st.history], savedThisAd: true }));
      toast('구성을 보관함에 저장했어요');
    } catch (e) { fail(e); }
  }, [update, toast, fail]);

  // ---------- 마이 / 생산기록 ----------
  const myHistory = useCallback(() => update({ myTab: 'history', notifOpen: false }), [update]);
  const myStoreTab = useCallback(() => go('myStore'), [go]);
  const myChar = useCallback(() => {
    if (!stateRef.current.charConfirmed) { toast('아직 확정한 캐릭터가 없어요'); return; }
    go('charInfo');
  }, [toast, go]);
  const editStoreFromMy = useCallback(() => { update({ storeReadOnly: false }); go('store'); }, [update, go]);
  const openHistoryItem = useCallback((h) => {
    update({ plan: (h.cuts || []).map((c, i) => ({ n: c.n ?? i + 1, short: c.short || '', line: c.line || '' })) });
    go('result');
  }, [update, go]);

  const delHistoryItem = useCallback(async (id) => {
    try {
      await HistoryAPI.remove(id);
      update((s) => ({ history: s.history.filter((h) => h.id !== id) }));
    } catch (e) { fail(e); }
  }, [update, fail]);

  const addItem = useCallback(async () => {
    const name = stateRef.current.newItem.trim();
    if (!name) return;
    try {
      await ProductionAPI.addItem(name);
      update((s) => ({
        newItem: '',
        items: s.items.includes(name) ? s.items : [...s.items, name],
        draftItem: s.draftItem || name,
      }));
    } catch (e) { fail(e); }
  }, [update, fail]);

  const delItem = useCallback(async (name) => {
    try {
      await ProductionAPI.deleteItem(name);
      update((s) => ({ items: s.items.filter((n) => n !== name) }));
    } catch (e) { fail(e); }
  }, [update, fail]);

  const renameItem = useCallback(async (oldName, newName) => {
    try {
      await ProductionAPI.renameItem(oldName, newName);
      update((s) => ({
        items: s.items.map((n) => (n === oldName ? newName : n)),
        prods: s.prods.map((p) => (p.name === oldName ? { ...p, name: newName } : p)),
      }));
      return true;
    } catch (e) { fail(e); return false; }
  }, [update, fail]);

  const addProd = useCallback(async () => {
    const s = stateRef.current;
    if (!s.draftItem) { toast('품목을 먼저 골라주세요'); return; }
    try {
      const record = await ProductionAPI.addRecord({
        name: s.draftItem, qty: s.draftQty, date: s.draftDate, time: s.draftTime, sold_out: s.draftSold,
      });
      update((st) => ({ prods: [record, ...st.prods], draftQty: '', draftTime: '', draftSold: '' }));
      toast('생산 기록을 저장했습니다');
    } catch (e) { fail(e); }
  }, [update, toast, fail]);

  const patchProd = useCallback(async (id, patchBody) => {
    const apiBody = {};
    if ('name' in patchBody) apiBody.name = patchBody.name;
    if ('qty' in patchBody) apiBody.qty = patchBody.qty;
    if ('date' in patchBody) apiBody.date = patchBody.date;
    if ('time' in patchBody) apiBody.time = patchBody.time;
    if ('soldOut' in patchBody) apiBody.sold_out = patchBody.soldOut;
    try {
      const record = await ProductionAPI.patchRecord(id, apiBody);
      update((s) => ({ prods: s.prods.map((p) => (p.id === id ? record : p)) }));
    } catch (e) { fail(e); }
  }, [update, fail]);

  const setSoldOut = useCallback(async (id, value) => {
    await patchProd(id, { soldOut: value });
    if (value) toast('매진 시각을 기록했습니다');
  }, [patchProd, toast]);

  const delProd = useCallback(async (id) => {
    try {
      await ProductionAPI.deleteRecord(id);
      update((s) => ({ prods: s.prods.filter((p) => p.id !== id) }));
    } catch (e) { fail(e); }
  }, [update, fail]);

  /** 백업 내려받기 — 실제로 파일이 떨어진다. 예전엔 "준비 중"이라고만 했다. */
  const exportData = useCallback(async () => {
    try {
      const data = await HistoryAPI.exportAll();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `가게백업-${today()}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      update({ backupNote: '백업 파일을 내려받았어요.', backupErr: false });
    } catch (e) {
      update({ backupNote: e.message || '내보내기에 실패했어요', backupErr: true });
    }
  }, [update]);

  const importFile = useCallback(() => {
    update({ backupNote: '불러오기는 아직 준비 중이에요. 내보내기는 지금도 됩니다.', backupErr: true });
  }, [update]);

  return {
    state,
    charLocked, adLocked,
    actions: {
      set, toast, go, back, goHome, reload,
      goStore, goChar, goAd, goMy, openProdTab, goData, goTrend, useTrendMeme,
      recommendTrendMeme, closeTrendRecommend, useTrendRecommendMeme,
      openAdEntry, closeAdEntry, pickAdEntryTrend, pickAdEntryDirect,
      editStore, saveStore, toggleClosedDay, uploadStoreImage, deleteStoreImage,
      genCandidates, sendChar, selectCand, rerollCand, loadChar, resetChar, confirmChar, toggleCharEdit,
      saveCharSheet, focusCharField, acceptCharSuggestion, declineCharSuggestion,
      confirmPending, declinePending,
      applyAd,
      toggleSbSet, toggleSbProd, sendSb, makeComic, rerollCut, proposeStory, addMeme, pickMemeCard,
      openResult, backToSb, confirmResult, download,
      myHistory, myStoreTab, myChar, editStoreFromMy, openHistoryItem, delHistoryItem,
      addItem, delItem, renameItem, addProd, patchProd, setSoldOut, delProd,
      exportData, importFile,
    },
  };
}
