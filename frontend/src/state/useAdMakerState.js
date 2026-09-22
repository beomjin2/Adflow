import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AdAPI, CharacterAPI, HistoryAPI, ProductionAPI, StoreAPI, StoryboardAPI, TrendAPI,
} from '../api/client.js';

/** 그림 생성 진행을 확인하는 간격. 백엔드가 generating=false를 주면 멈춘다. */
const POLL_MS = 3000;
/** 안전장치 — 백엔드가 영영 끝났다고 말해주지 않아도 25분이면 폴링을 멈춘다. */
const POLL_MAX_TICKS = 500;

/** 새로고침해도 마지막 화면을 유지하려고 화면 위치(screen·stack)만 세션에 잠깐 적어 둔다.
 *  데이터는 전부 백엔드에 있으니 여기엔 "어디 있었는지"만 남긴다 — 탭을 닫으면 사라져도 된다. */
const SCREEN_NAV_KEY = 'adflow.nav';

function loadScreenNav() {
  try {
    const raw = sessionStorage.getItem(SCREEN_NAV_KEY);
    if (!raw) return { screen: 'home', stack: [] };
    const parsed = JSON.parse(raw);
    return {
      screen: typeof parsed.screen === 'string' ? parsed.screen : 'home',
      stack: Array.isArray(parsed.stack) ? parsed.stack : [],
    };
  } catch {
    return { screen: 'home', stack: [] };
  }
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
    ...loadScreenNav(),
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
    trendItems: [], trendSites: [], trendCollectedAt: '',
    trendFilter: '전체', trendSearch: '', trendSort: '최신순', trendSel: '',
    // 상황 카테고리(무엇에 대한 밈이냐)와는 다른 축이라 칩이 아니라 별도 토글로 둔다 —
    // "재미·밈놀이 중에 지금도 유행 중인 것"처럼 두 조건을 같이 걸 수 있어야 한다.
    trendOnlyOngoing: false,
    // 활용 상황 안에서 GPT 추천 — note는 "오늘 알릴 내용"(선택). result는 {meme, reason} | null.
    // popupOpen은 트렌드 화면에 들어올 때마다 Trend.jsx가 true로 켠다.
    trendRecommendNote: '', trendRecommendLoading: false, trendRecommendResult: null,
    trendRecommendPopupOpen: false,

    sbMsgs: [], sbInput: '', sbThinking: false,
    plan: [], sbSetOpen: false, sbProdOpen: false, pending: {},
    // 네컷 그림 칸과 진행 상태 — 캐릭터 후보와 같은 규칙(status: empty|generating|done|failed)
    comicCuts: [], sbGenerating: false, sbEta: 0,
    // "보관함에 저장"을 한 번 누르면 같은 구성으로 또 눌러도 중복 저장 안 되게 잠근다.
    // 네컷을 새로 그리면(makeComic) 그건 다른 구성이니 다시 저장할 수 있게 풀어준다.
    savedThisAd: false,

    myTab: 'history', history: [],
    // Result 화면이 "새로 만든 광고 끝"인지 "보관함에서 옛 항목을 보는 중"인지 구분한다 —
    // 후자면 "이대로 저장"을 보여주지 않는다(이미 저장된 걸 또 저장하면 중복이 생긴다).
    viewingHistory: false,

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

  // 새로고침해도 마지막 화면을 유지한다 — 데이터는 아래 "처음 불러오기"가 다시 채운다.
  useEffect(() => {
    try {
      sessionStorage.setItem(SCREEN_NAV_KEY, JSON.stringify({ screen: state.screen, stack: state.stack }));
    } catch {
      // 세션 저장을 못 써도(사생활 보호 모드 등) 화면 이동 자체는 그대로 동작해야 한다.
    }
  }, [state.screen, state.stack]);

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
        const [store, character, ad, storyboard, items, prods, history, trend] = await Promise.all([
          StoreAPI.get(), CharacterAPI.get(), AdAPI.get(), StoryboardAPI.get(),
          ProductionAPI.listItems(), ProductionAPI.listRecords(), HistoryAPI.list(),
          TrendAPI.list(),
        ]);
        update({
          ...store, ...character, ...ad, ...storyboard, ...trend,
          items, prods, history,
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

  /** 밈 전체 중 GPT 추천을 받는다 — 활용 상황은 이제 사장님이 안 고르고 GPT가 가게·캐릭터·
   *  오늘 알릴 내용을 보고 알아서 판단한다. 성공하면 추천 요청 팝업은 닫고 결과 팝업으로
   *  넘어간다 — 실패하면 요청 팝업에 그대로 남겨서 한줄입력을 고쳐 다시 시도할 수 있게 한다. */
  const recommendTrendMeme = useCallback(async () => {
    const s = stateRef.current;
    update({ trendRecommendLoading: true });
    try {
      const result = await TrendAPI.recommend(s.trendRecommendNote.trim());
      update({ trendRecommendResult: result, trendRecommendLoading: false, trendRecommendPopupOpen: false });
    } catch (e) {
      update({ trendRecommendLoading: false });
      fail(e);
    }
  }, [update, fail]);

  const closeTrendRecommend = useCallback(() => update({ trendRecommendResult: null }), [update]);

  /** 추천 결과 팝업의 picks는 목록이라(지금은 보통 1개), 어느 걸 눌렀는지 memeId로 받는다.
   *  밈 자체를 누르면, 리스트에서 그 밈을 고른 것처럼 선택만 해두고 팝업만 닫는다 —
   *  광고 만들기로 곧장 넘어가지 않아서, 유래·활용예시를 아래 상세 패널에서 먼저
   *  훑어보고 판단할 수 있다. 검색어도 같이 비운다 — 예전에 쳐둔 검색어가 추천된 밈의
   *  이름·유래·활용예시와 안 겹치면 리스트에서 걸러져서, Trend.jsx의 "선택이 안 보이면
   *  맨 위로 되돌리는" 로직이 방금 고른 밈을 곧장 다른 밈으로 덮어써버린다. */
  const selectTrendRecommendMeme = useCallback((memeId) => {
    update({ trendSel: memeId, trendRecommendResult: null, trendSearch: '' });
  }, [update]);

  /** 고른 후보를 그대로 선택한 걸로 치고 광고 만들기로 넘어간다. */
  const useTrendRecommendMeme = useCallback((memeId) => {
    update({ trendSel: memeId, trendRecommendResult: null });
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
   *  참고 안 하겠다는 선택이니 지운다. applyAd()가 trendSel을 광고 설정 확정 때 백엔드로
   *  넘기는데, 지난번 선택이 남아 있으면 이번에도 그 밈이 대화에 반영돼 버린다. */
  const pickAdEntryDirect = useCallback(() => {
    update({ adEntryOpen: false, trendSel: '' });
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

  /** 빈 칸을 한 번에 채워 달라고 한다. 대화로 한 칸씩 가는 게 번거로운 분을 위한 지름길.
   *  **이미 적어 둔 칸은 그대로 둔다** — 반쯤 채우다 눌러도 앞서 정한 게 남는다.
   *  누르기 전에 시트에 직접 타이핑한 내용을 먼저 저장한다. 안 그러면 방금 친 글자가
   *  빈 칸으로 취급돼 덮어써진다. */
  const autofillChar = useCallback(async () => {
    update({ charThinking: true });
    try {
      await syncCharSheet();
      update(await CharacterAPI.autofill());
    } catch (e) { fail(e); } finally { update({ charThinking: false }); }
  }, [update, fail, syncCharSheet]);


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
      // 트렌드 화면에서 밈을 골라 왔으면(trendSel) 같이 보낸다 — 대화(story_llm)가
      // 그 밈을 자동으로 반영한다. 별도로 카드를 만들거나 고르는 단계는 없다.
      const res = await AdAPI.apply(s.trendSel);
      const sb = await StoryboardAPI.get();
      // 광고 설정을 새로 확정하면 백엔드가 스토리보드를 처음 상태로 되돌린다(reset_storyboard) —
      // 이전에 만든 다른 광고를 저장한 적이 있어도 이건 새 구성이니 다시 저장할 수 있게 푼다.
      update({ ...sb, savedThisAd: false });

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

  /** "스토리 제안받기" 버튼 — 아무것도 안 적고, 가게·캐릭터·생산 기록·(있으면) 밈만으로
   *  바로 제안받는다. 자동으로는 안 뜨고 이 버튼을 눌러야만 부른다. */
  const suggestStory = useCallback(async () => {
    update({ sbThinking: true });
    try {
      const updated = await StoryboardAPI.suggest();
      update({ ...updated, sbThinking: false });
    } catch (e) { update({ sbThinking: false }); fail(e); }
  }, [update, fail]);

  /** "밈 추천받기" 버튼 — 지금까지 대화에서 쓴 문장을 근거로 밈을 추천받는다. 자동으로는
   *  안 뜨고 이 버튼을 눌러야만 부른다. 결과는 confirm 카드로 오고 승인해야 반영된다. */
  const recommendMeme = useCallback(async () => {
    update({ sbThinking: true });
    try {
      const updated = await StoryboardAPI.recommendMeme();
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

  // ---------- 결과 / 저장 ----------
  const openResult = useCallback(() => {
    const s = stateRef.current;
    if (!s.plan.length) { toast('먼저 대화로 컷 구성을 만들어주세요'); return; }
    // 4컷만화는 그림이 광고의 핵심이라 "네컷 그리기"를 먼저 끝내야 한다. 인스타 게시물은
    // 문구만으로도 올릴 수 있는 형식이라 그림을 요구하지 않는다.
    if (s.adType === '4컷만화') {
      const cuts = s.comicCuts || [];
      const ready = cuts.length >= s.plan.length && cuts.every((c) => c.status === 'done');
      if (!ready) { toast('먼저 네컷 그리기를 끝내주세요'); return; }
    }
    // 히스토리에서 옛 항목을 봤을 때(viewingHistory) 켜둔 값이 남아있을 수 있으니,
    // 새로 만드는 흐름으로 들어올 땐 항상 꺼둔다 — "보관함에 저장" 버튼이 이 값으로 갈린다.
    update({ viewingHistory: false });
    go('result');
  }, [go, toast, update]);
  const backToSb = useCallback(() => update((s) => ({ screen: 'sb', stack: s.stack.filter((x) => x !== 'result') })), [update]);

  const download = useCallback(async () => {
    const s = stateRef.current;
    if (!s.plan.length) { toast('저장할 구성이 없어요'); return; }
    if (s.savedThisAd) { toast('이미 보관함에 저장했어요'); return; }
    try {
      // plan은 컷 문장만 갖고 있다 — 실제로 그려진 네컷 그림(comicCuts)을 n으로 맞춰
      // 같이 넣어야, 나중에 히스토리에서 다시 열었을 때 그림까지 보인다.
      const comicByN = new Map((s.comicCuts || []).map((c) => [c.n, c]));
      const entry = await HistoryAPI.add({
        title: `${s.adType} · ${s.adConcept}`,
        meta: `${s.plan.length}컷 구성`,
        cuts: s.plan.map((c) => {
          const drawn = comicByN.get(c.n);
          return {
            n: c.n, short: c.short || '', line: c.line || '',
            image: drawn?.status === 'done' ? drawn.image : null,
            status: drawn?.status || 'empty',
          };
        }),
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
    const cuts = h.cuts || [];
    update({
      plan: cuts.map((c, i) => ({ n: c.n ?? i + 1, short: c.short || '', line: c.line || '' })),
      // 저장할 때 comicCuts(그린 그림)를 cuts에 같이 넣어 뒀으니, 다시 열 때도 그대로
      // 복원한다 — image 유무로 status를 다시 판단한다(옛 항목엔 status 자체가 없을 수 있어서).
      comicCuts: cuts.map((c, i) => ({
        n: c.n ?? i + 1, short: c.short || '', line: c.line || '',
        image: c.image || null, status: c.image ? 'done' : 'empty',
      })),
      // 이미 저장된 항목을 보는 것뿐이라 "이대로 저장"은 필요 없다 — Result.jsx가 이 값으로 숨긴다.
      viewingHistory: true,
    });
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
      recommendTrendMeme, closeTrendRecommend, useTrendRecommendMeme, selectTrendRecommendMeme,
      openAdEntry, closeAdEntry, pickAdEntryTrend, pickAdEntryDirect,
      editStore, saveStore, toggleClosedDay, uploadStoreImage, deleteStoreImage,
      genCandidates, sendChar, selectCand, rerollCand, loadChar, resetChar, confirmChar, toggleCharEdit,
      saveCharSheet, focusCharField, acceptCharSuggestion, declineCharSuggestion, autofillChar,
      confirmPending, declinePending,
      applyAd,
      toggleSbSet, toggleSbProd, sendSb, suggestStory, recommendMeme, makeComic,
      openResult, backToSb, download,
      myHistory, myStoreTab, myChar, editStoreFromMy, openHistoryItem, delHistoryItem,
      addItem, delItem, renameItem, addProd, patchProd, setSoldOut, delProd,
      exportData, importFile,
    },
  };
}
