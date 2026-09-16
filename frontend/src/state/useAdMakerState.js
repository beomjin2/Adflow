import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AdAPI, CharacterAPI, HistoryAPI, ProductionAPI, StoreAPI, StoryboardAPI,
} from '../api/client.js';

/** 그림 생성 진행을 확인하는 간격. 백엔드가 generating=false를 주면 멈춘다. */
const POLL_MS = 3000;
/** 안전장치 — 백엔드가 영영 끝났다고 말해주지 않아도 25분이면 폴링을 멈춘다. */
const POLL_MAX_TICKS = 500;

/** 오늘 날짜(YYYY-MM-DD). toISOString()은 UTC라서 한국 시간 오전 9시 전에는 어제가 나온다 —
 *  새벽에 만든 걸 기록하는 가게가 많아서 그대로 쓰면 하루씩 밀린다. */
function today() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
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

    charName: '', charAge: '', charGender: '', charHobby: '', charLook: '',
    charMsgs: [], charInput: '', charThinking: false,
    charCands: [], charSelected: -1, charViews: [],
    charConfirmed: false, charInfoReadOnly: true,
    // 그림 생성 진행 상태 — 백엔드가 준 값이다. 화면의 "약 N초 남았어요"가 여기서 나온다.
    charGenerating: false, charQueue: 0, charEta: 0,

    adType: '', adConcept: '',

    sbMsgs: [], sbInput: '', sbThinking: false,
    plan: [], sbProdLogged: false, sbSetOpen: false, sbProdOpen: false, pending: {},

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
        // generating=false면 끝났다는 뜻이다. 칸 상태를 하나씩 보고 판단하면
        // 실패(failed) 칸이 섞였을 때 폴링이 안 멈춘다.
        if (!progress.charGenerating) stopPolling();
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
        const [store, character, ad, storyboard, items, prods, history] = await Promise.all([
          StoreAPI.get(), CharacterAPI.get(), AdAPI.get(), StoryboardAPI.get(),
          ProductionAPI.listItems(), ProductionAPI.listRecords(), HistoryAPI.list(),
        ]);
        update({
          ...store, ...character, ...ad, ...storyboard,
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

  const genCandidates = useCallback(async () => {
    update({ charThinking: true });
    await runGenerating(() => CharacterAPI.genCandidates());
    update({ charThinking: false });
  }, [update, runGenerating]);

  const selectCand = useCallback(async (i) => {
    await runGenerating(() => CharacterAPI.select(i));
  }, [runGenerating]);

  const rerollCand = useCallback(async (i) => {
    await runGenerating(() => CharacterAPI.rerollCandidate(i));
  }, [runGenerating]);

  const rerollView = useCallback(async (i) => {
    await runGenerating(() => CharacterAPI.rerollView(i));
  }, [runGenerating]);

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
      await CharacterAPI.update({ name: s.charName, age: s.charAge, gender: s.charGender, hobby: s.charHobby, look: s.charLook });
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
        const updated = await CharacterAPI.update({ name: s.charName, age: s.charAge, gender: s.charGender, hobby: s.charHobby, look: s.charLook });
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
      update({ ...sb });
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
    try {
      const entry = await HistoryAPI.add({
        title: `${s.adType} · ${s.adConcept}`,
        meta: `${s.plan.length}컷 구성`,
        cuts: s.plan.map((c) => ({ n: c.n, short: c.short || '', line: c.line || '' })),
      });
      update((st) => ({ history: [entry, ...st.history] }));
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
      goStore, goChar, goAd, goMy, openProdTab, goData,
      editStore, saveStore, toggleClosedDay, uploadStoreImage, deleteStoreImage,
      genCandidates, sendChar, selectCand, rerollCand, rerollView, loadChar, resetChar, confirmChar, toggleCharEdit,
      confirmPending, declinePending,
      applyAd,
      toggleSbSet, toggleSbProd, sendSb,
      openResult, backToSb, confirmResult, download,
      myHistory, myStoreTab, myChar, editStoreFromMy, openHistoryItem,
      addItem, delItem, renameItem, addProd, patchProd, setSoldOut, delProd,
      exportData, importFile,
    },
  };
}
