import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AdAPI, CharacterAPI, HistoryAPI, ProductionAPI, StoreAPI, StoryboardAPI, TrendAPI,
} from '../api/client.js';

function initialState() {
  const today = new Date().toISOString().slice(0, 10);
  return {
    screen: 'home',
    stack: [],
    toast: '',
    loading: true,
    loadError: '',

    storeSaved: false, storeReadOnly: false,
    storeCategory: '', storeAddress: '', storeHours: '',
    storeOpenTime: '10:00', storeCloseTime: '21:00', storeClosedDays: [],
    storeDesc: '', storeImages: [],

    charName: '', charAge: '', charGender: '', charHobby: '', charLook: '',
    charMsgs: [], charInput: '', charThinking: false, charPending: {},
    charCands: [], charSelected: -1,
    charConfirmed: false, charInfoReadOnly: true,

    adType: '인스타 게시물', adConcept: '유쾌함',
    trendPopup: false, trendApplied: false, trendPick: '', openTrend: '', fromAd: false,
    trendBars: [], trendDetail: [],

    sbMsgs: [], sbInput: '', sbThinking: false,
    plan: [], comicCuts: [], sbProdLogged: false, sbSetOpen: false, sbProdOpen: false, pending: {},

    myTab: 'history', history: [],

    items: [], prods: [],
    newItem: '', draftItem: '', draftQty: '', draftDate: today, draftTime: '', draftSold: '',

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
    toastTimer.current = setTimeout(() => update({ toast: '' }), 2200);
  }, [update]);

  const fail = useCallback((e) => toast(e.message || '요청에 실패했어요'), [toast]);

  // ---------- initial load ----------
  useEffect(() => {
    (async () => {
      try {
        const [store, character, ad, trend, storyboard, items, prods, history] = await Promise.all([
          StoreAPI.get(), CharacterAPI.get(), AdAPI.get(), TrendAPI.get(), StoryboardAPI.get(),
          ProductionAPI.listItems(), ProductionAPI.listRecords(), HistoryAPI.list(),
        ]);
        update({
          ...store, ...character, ...ad,
          trendBars: trend.bars, trendDetail: trend.detail,
          ...storyboard,
          items, prods, history,
          storeReadOnly: store.storeSaved,
          draftItem: items[0] || '',
          loading: false,
        });
      } catch (e) {
        update({ loading: false, loadError: e.message || '백엔드에 연결할 수 없어요' });
      }
    })();
  }, [update]);

  // ---------- navigation (전부 로컬 UI 상태) ----------
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

  const goHome = useCallback(() => update({ screen: 'home', stack: [], trendPopup: false }), [update]);

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
  const goTrendHome = useCallback(() => { update({ fromAd: false }); go('trend'); }, [go, update]);
  const goMy = useCallback(() => { update({ myTab: 'history' }); go('my'); }, [go, update]);
  const openProdTab = useCallback(() => { update({ myTab: 'prod', notifOpen: false }); go('my'); }, [go, update]);
  const goData = useCallback(() => { update({ myTab: 'data', notifOpen: false }); go('my'); }, [go, update]);

  // ---------- store ----------
  const editStore = useCallback(() => { update({ storeReadOnly: false }); toast('편집할 수 있어요'); }, [update, toast]);

  const saveStore = useCallback(async () => {
    const s = stateRef.current;
    try {
      await StoreAPI.update({
        category: s.storeCategory, address: s.storeAddress, desc: s.storeDesc,
        open_time: s.storeOpenTime, close_time: s.storeCloseTime, closed_days: s.storeClosedDays,
      });
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
    try { update(await StoreAPI.uploadImage(file)); toast('이미지를 업로드했어요'); } catch (e) { fail(e); }
  }, [update, toast, fail]);

  const deleteStoreImage = useCallback(async (i) => {
    try { update(await StoreAPI.deleteImage(i)); } catch (e) { fail(e); }
  }, [update, fail]);

  // ---------- character ----------
  const sendChar = useCallback(async () => {
    const text = stateRef.current.charInput.trim();
    if (!text) return;
    update((s) => ({ charInput: '', charThinking: true, charMsgs: [...s.charMsgs, { role: 'me', kind: 'text', text }] }));
    try {
      const updated = await CharacterAPI.chat(text);
      update({ ...updated, charThinking: false });
    } catch (e) { update({ charThinking: false }); fail(e); }
  }, [update, fail]);

  const genCandidates = useCallback(async () => {
    update({ charThinking: true });
    try {
      const updated = await CharacterAPI.genCandidates();
      update(updated);
      // 항목만 먼저 반환됨 — 실제 이미지는 하나씩 순차로 채운다 (요청당 이미지 1장, 타임아웃 방지)
      // charThinking은 이 루프가 끝날 때까지 켜둬서 생성 중 리롤 버튼을 못 누르게 막는다.
      for (let i = 0; i < (updated.charCands || []).length; i++) {
        try { update(await CharacterAPI.rerollCandidate(i)); } catch (e) { fail(e); }
      }
    } catch (e) { fail(e); } finally { update({ charThinking: false }); }
  }, [update, fail]);

  const selectCand = useCallback(async (i) => {
    try { update(await CharacterAPI.select(i)); } catch (e) { fail(e); }
  }, [update, fail]);

  const rerollCand = useCallback(async (i) => {
    update({ charThinking: true });
    try { update(await CharacterAPI.rerollCandidate(i)); toast('다시 그렸어요'); }
    catch (e) { fail(e); }
    finally { update({ charThinking: false }); }
  }, [update, toast, fail]);

  const loadChar = useCallback(async () => {
    try { update(await CharacterAPI.loadPrevious()); } catch (e) { fail(e); }
  }, [update, fail]);

  const resetChar = useCallback(async () => {
    if (!window.confirm('캐릭터 대화와 후보를 전부 지우고 처음부터 다시 시작할까요?')) return;
    try { update(await CharacterAPI.reset()); } catch (e) { fail(e); }
  }, [update, fail]);

  const confirmCharPending = useCallback(async (pid) => {
    try { update(await CharacterAPI.confirmPending(pid)); } catch (e) { fail(e); }
  }, [update, fail]);

  const declineCharPending = useCallback(async (pid) => {
    try { update(await CharacterAPI.declinePending(pid)); } catch (e) { fail(e); }
  }, [update, fail]);

  const confirmChar = useCallback(async () => {
    const s = stateRef.current;
    if (s.charSelected < 0) return;
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

  // ---------- ad ----------
  const applyAd = useCallback(() => update({ trendPopup: true }), [update]);

  const trendYes = useCallback(async () => {
    const s = stateRef.current;
    try {
      await AdAPI.update({ ad_type: s.adType, ad_concept: s.adConcept });
      const updated = await AdAPI.trendYes();
      const sb = await StoryboardAPI.get();
      update({ ...updated, ...sb, trendPopup: false });
      go('sb');
    } catch (e) { fail(e); }
  }, [update, fail, go]);

  const trendNo = useCallback(async () => {
    const s = stateRef.current;
    try {
      await AdAPI.update({ ad_type: s.adType, ad_concept: s.adConcept });
      const updated = await AdAPI.trendNo();
      const sb = await StoryboardAPI.get();
      update({ ...updated, ...sb, trendPopup: false });
      go('sb');
    } catch (e) { fail(e); }
  }, [update, fail, go]);

  const goTrendFromAd = useCallback(() => { update({ fromAd: true, trendPopup: false }); go('trend'); }, [update, go]);
  const backToAd = useCallback(() => update({ fromAd: false, screen: 'ad', trendPopup: true }), [update]);

  // ---------- trend ----------
  const toggleTrendAccordion = useCallback((name) => {
    update((s) => ({ openTrend: s.openTrend === name ? '' : name }));
  }, [update]);

  const useTrend = useCallback(async (name) => {
    if (!stateRef.current.charConfirmed) { toast('캐릭터를 먼저 확정해주세요'); return; }
    try {
      const updated = await TrendAPI.use(name);
      const sb = await StoryboardAPI.get();
      update({ ...updated, ...sb, fromAd: false });
      go('sb');
    } catch (e) { fail(e); }
  }, [toast, update, fail, go]);

  // ---------- storyboard ----------
  const toggleSbSet = useCallback(() => update((s) => ({ sbSetOpen: !s.sbSetOpen })), [update]);
  const toggleSbProd = useCallback(() => update((s) => ({ sbProdOpen: !s.sbProdOpen })), [update]);

  const sendSb = useCallback(async () => {
    const s = stateRef.current;
    const text = s.sbInput.trim();
    if (!text) return;
    update((st) => ({ sbInput: '', sbThinking: true, sbMsgs: [...st.sbMsgs, { role: 'me', kind: 'text', text }] }));
    try {
      const updated = await StoryboardAPI.chat(text, { adType: s.adType, trendApplied: s.trendApplied, trendPick: s.trendPick });
      update({ ...updated, sbThinking: false });
    } catch (e) { update({ sbThinking: false }); fail(e); }
  }, [update, fail]);

  const confirmPending = useCallback(async (pid) => {
    try { update(await StoryboardAPI.confirm(pid)); toast('반영했어요'); } catch (e) { fail(e); }
  }, [update, toast, fail]);

  const declinePending = useCallback(async (pid) => {
    try { update(await StoryboardAPI.decline(pid)); } catch (e) { fail(e); }
  }, [update, fail]);

  const makeComic = useCallback(async () => {
    if (!stateRef.current.plan.length) { toast('먼저 대화로 플랜을 만들어주세요'); return; }
    update({ sbThinking: true });
    try {
      const updated = await StoryboardAPI.makeComic();
      update({ ...updated, sbThinking: false });
    } catch (e) { update({ sbThinking: false }); fail(e); }
  }, [toast, update, fail]);

  const rerollCut = useCallback(async (n) => {
    try { update(await StoryboardAPI.rerollCut(n)); toast(`${n}컷만 다시 그렸어요`); } catch (e) { fail(e); }
  }, [update, toast, fail]);

  // ---------- result / save ----------
  const openResult = useCallback(() => go('result'), [go]);
  const backToSb = useCallback(() => update((s) => ({ screen: 'sb', stack: s.stack.filter((x) => x !== 'result') })), [update]);
  const confirmResult = useCallback(() => go('save'), [go]);

  const download = useCallback(async () => {
    const s = stateRef.current;
    try {
      const entry = await HistoryAPI.add({
        title: `${s.adType} · ${s.adConcept}`,
        meta: `${s.trendApplied ? s.trendPick + ' · ' : ''}네컷만화 · 방금 저장`,
        cuts: s.comicCuts.map((c) => ({ hue: c.hue })),
      });
      update((st) => ({ history: [entry, ...st.history] }));
      toast('이미지와 문구를 내려받았어요');
    } catch (e) { fail(e); }
  }, [update, toast, fail]);

  // ---------- my / production ----------
  const myHistory = useCallback(() => update({ myTab: 'history', notifOpen: false }), [update]);
  const myStoreTab = useCallback(() => go('myStore'), [go]);
  const myChar = useCallback(() => {
    if (!stateRef.current.charConfirmed) { toast('아직 확정된 캐릭터가 없어요'); return; }
    go('charInfo');
  }, [toast, go]);
  const editStoreFromMy = useCallback(() => { update({ storeReadOnly: false }); go('store'); }, [update, go]);
  const openHistoryItem = useCallback((h) => {
    update({ comicCuts: h.cuts.map((c, i) => ({ n: i + 1, short: '', hue: c.hue })) });
    go('result');
  }, [update, go]);

  const addItem = useCallback(async () => {
    const name = stateRef.current.newItem.trim();
    if (!name) return;
    try {
      await ProductionAPI.addItem(name);
      update((s) => ({ newItem: '', items: s.items.includes(name) ? s.items : [...s.items, name] }));
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
    } catch (e) { fail(e); }
  }, [update, fail]);

  const addProd = useCallback(async () => {
    const s = stateRef.current;
    if (!s.draftItem) { toast('품목을 먼저 골라주세요'); return; }
    try {
      const record = await ProductionAPI.addRecord({
        name: s.draftItem, qty: s.draftQty, date: s.draftDate, time: s.draftTime, sold_out: s.draftSold,
      });
      update((st) => ({ prods: [record, ...st.prods], draftQty: '', draftTime: '', draftSold: '' }));
      toast('생산 기록을 저장했어요');
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
    if (value) toast('매진 시각을 기록했어요');
  }, [patchProd, toast]);

  const delProd = useCallback(async (id) => {
    try {
      await ProductionAPI.deleteRecord(id);
      update((s) => ({ prods: s.prods.filter((p) => p.id !== id) }));
    } catch (e) { fail(e); }
  }, [update, fail]);

  const exportData = useCallback(async () => {
    try {
      const res = await fetch('/api/history/export');
      if (!res.ok) throw new Error('내보내기에 실패했어요');
      await res.json();
      update({ backupNote: '백업 파일을 만들었어요 (프로토타입 — 실제 다운로드는 준비 중).', backupErr: false });
    } catch (e) {
      update({ backupNote: e.message, backupErr: true });
    }
  }, [update]);

  const importFile = useCallback(() => {
    update({ backupNote: '이 프로토타입에서는 불러오기가 아직 준비 중이에요.', backupErr: true });
  }, [update]);

  return {
    state,
    charLocked, adLocked,
    actions: {
      set, toast, go, back, goHome,
      goStore, goChar, goAd, goTrendHome, goMy, openProdTab, goData,
      editStore, saveStore, toggleClosedDay, uploadStoreImage, deleteStoreImage,
      genCandidates, sendChar, selectCand, rerollCand, loadChar, resetChar, confirmChar, toggleCharEdit,
      confirmCharPending, declineCharPending,
      confirmPending, declinePending,
      applyAd, trendYes, trendNo, goTrendFromAd, backToAd,
      toggleTrendAccordion, useTrend,
      toggleSbSet, toggleSbProd, sendSb, makeComic, rerollCut,
      openResult, backToSb, confirmResult, download,
      myHistory, myStoreTab, myChar, editStoreFromMy, openHistoryItem,
      addItem, delItem, renameItem, addProd, patchProd, setSoldOut, delProd,
      exportData, importFile,
    },
  };
}
