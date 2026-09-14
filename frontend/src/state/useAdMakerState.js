import { useCallback, useRef, useState } from 'react';
import {
  BASE_PLAN, TRENDS, generateCandidates, generateViews,
  itemFrom, qtyFrom, dayFrom, timeFrom, isoDay, fmtDay
} from '../mock/aiResponses.js';
import { randomHue } from '../theme.js';

const SEEDED = true;

function initialState() {
  return {
    screen: 'home',
    stack: [],
    toast: '',

    storeSaved: SEEDED,
    storeReadOnly: SEEDED,
    storeCategory: '베이커리',
    storeAddress: SEEDED ? '서울 마포구 연남로 21' : '',
    storeHours: SEEDED ? '08:00 – 20:00, 월 휴무' : '',
    storeDesc: SEEDED ? '매일 새벽 반죽해 오븐에서 바로 꺼내는 동네 빵집. 소금빵과 통밀 캄파뉴가 간판이에요.' : '',
    storeImages: SEEDED ? [{ label: '소금빵', hue: 38 }, { label: '오늘 구운 빵 진열대', hue: 26 }] : [],

    charName: '', charAge: '', charGender: '', charHobby: '', charLook: '',
    charMsgs: [{ role: 'ai', kind: 'text', text: '어떤 마스코트를 원하세요? 가게 분위기나 느낌을 편하게 말해주세요.' }],
    charInput: '',
    charThinking: false,
    charCands: [],
    charSelected: -1,
    charViews: [],
    charConfirmed: false,
    charInfoReadOnly: true,

    adType: '인스타 게시물',
    adConcept: '유쾌함',
    trendPopup: false,
    trendApplied: false,
    trendPick: TRENDS[0],
    openTrend: '',
    fromAd: false,

    sbMsgs: [{ role: 'ai', kind: 'text', text: '어떤 이야기로 광고를 만들까요? 알리고 싶은 걸 말해주세요.' }],
    sbInput: '',
    sbThinking: false,
    plan: [],
    comicCuts: [],
    sbProdLogged: false,
    sbSetOpen: false,
    sbProdOpen: false,

    myTab: 'history',
    history: [],

    items: SEEDED ? ['소금빵', '버터 크루아상', '통밀 캄파뉴'] : [],
    prods: SEEDED ? [
      { id: 3, name: '소금빵', qty: '60개', date: isoDay(0), time: '07:40', soldOut: '' },
      { id: 2, name: '버터 크루아상', qty: '40개', date: isoDay(-1), time: '13:20', soldOut: '' },
      { id: 1, name: '통밀 캄파뉴', qty: '12개', date: isoDay(-1), time: '06:50', soldOut: '16:10' }
    ] : [],
    newItem: '',
    draftItem: SEEDED ? '소금빵' : '',
    draftQty: '', draftDate: isoDay(0), draftTime: '', draftSold: '',

    notifOpen: false,
    pending: {},
    backupNote: '', backupErr: false
  };
}

export function useAdMakerState() {
  const [state, setState] = useState(initialState);
  const toastTimer = useRef(null);

  const update = useCallback((patch) => {
    setState(s => ({ ...s, ...(typeof patch === 'function' ? patch(s) : patch) }));
  }, []);

  const set = useCallback((field, value) => update({ [field]: value }), [update]);

  const toast = useCallback((msg) => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    update({ toast: msg });
    toastTimer.current = setTimeout(() => update({ toast: '' }), 2200);
  }, [update]);

  const go = useCallback((screen) => {
    update(s => ({ screen, stack: [...s.stack, s.screen] }));
  }, [update]);

  const back = useCallback(() => {
    update(s => {
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

  const resetDemo = useCallback(() => setState(initialState()), []);

  // ---------- store ----------
  const editStore = useCallback(() => { update({ storeReadOnly: false }); toast('편집할 수 있어요'); }, [update, toast]);
  const saveStore = useCallback(() => {
    update({ storeSaved: true, storeReadOnly: true });
    toast('가게 정보를 저장했어요');
  }, [update, toast]);
  const addImage = useCallback(() => {
    update(s => ({ storeImages: [...s.storeImages, { label: `이미지 ${s.storeImages.length + 1}`, hue: randomHue() }] }));
  }, [update]);
  const rerollStoreImage = useCallback((i) => {
    update(s => ({ storeImages: s.storeImages.map((im, idx) => idx === i ? { ...im, hue: randomHue() } : im) }));
    toast('다시 생성했어요');
  }, [update, toast]);

  // ---------- proposal / confirm (storyboard의 plan/comic 제안-승인 카드) ----------
  const confirmPending = useCallback((pid) => {
    update(s => {
      const p = s.pending[pid];
      if (!p) return {};
      const key = p.which === 'char' ? 'charMsgs' : 'sbMsgs';
      const patch = { pending: { ...s.pending, [pid]: { ...p, status: 'applied' } } };
      if (p.kind === 'plan') {
        patch.plan = p.payload.plan;
        patch[key] = [...s[key], { role: 'ai', kind: 'plan', ref: 'plan' }];
      } else if (p.kind === 'comic') {
        patch.comicCuts = p.payload.cuts;
        patch[key] = [...s[key], { role: 'ai', kind: 'comic', ref: 'comic' }];
      } else {
        patch[key] = s[key];
      }
      return patch;
    });
    toast('반영했어요');
  }, [update, toast]);

  const declinePending = useCallback((pid) => {
    update(s => {
      const p = s.pending[pid];
      if (!p || p.status !== 'open') return {};
      const key = p.which === 'char' ? 'charMsgs' : 'sbMsgs';
      return {
        pending: { ...s.pending, [pid]: { ...p, status: 'declined' } },
        [key]: [...s[key], { role: 'ai', kind: 'text', text: '그대로 둘게요. 어떻게 바꾸면 좋을지 말해주세요.' }]
      };
    });
  }, [update]);

  // ---------- character ----------
  const genCandidates = useCallback(() => {
    update(s => ({
      charThinking: true
    }));
    setTimeout(() => {
      const cands = generateCandidates(3);
      update(s => ({
        charThinking: false,
        charCands: cands, charSelected: -1,
        charMsgs: [...s.charMsgs, { role: 'ai', kind: 'cands', ref: 'cands' }]
      }));
    }, 700);
  }, [update]);

  const sendChar = useCallback(() => {
    const text = state.charInput.trim();
    if (!text) return;
    update(s => ({ charInput: '', charMsgs: [...s.charMsgs, { role: 'me', kind: 'text', text }] }));
    aiChar(text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.charInput, update]);

  function aiChar(userText) {
    update({ charThinking: true });
    setTimeout(() => {
      update(s => {
        if (!s.charCands.length) {
          return {
            charThinking: false,
            charName: s.charName || '동글이',
            charLook: s.charLook || `${userText} 느낌으로 그려볼게요.`,
            charCands: generateCandidates(3),
            charSelected: -1,
            charMsgs: [...s.charMsgs,
              { role: 'ai', kind: 'text', text: '이름·외형을 채웠어요. 왼쪽에서 직접 고쳐도 돼요.' },
              { role: 'ai', kind: 'cands', ref: 'cands' }]
          };
        }
        return {
          charThinking: false,
          charMsgs: [...s.charMsgs, { role: 'ai', kind: 'text', text: '알겠어요, 반영해서 다시 뽑아볼게요.' }]
        };
      });
    }, 700);
  }

  const selectCand = useCallback((i) => {
    update({ charThinking: true });
    setTimeout(() => {
      update(s => {
        const views = generateViews();
        return {
          charThinking: false,
          charSelected: i, charViews: views,
          charMsgs: [...s.charMsgs,
            { role: 'me', kind: 'text', text: `${i + 1}번으로 할게요` },
            { role: 'ai', kind: 'text', text: `${i + 1}번으로 정했어요. 4방향으로 뽑아둘게요 — 확정하면 광고에 계속 쓰여요.` },
            { role: 'ai', kind: 'views', ref: 'views' }]
        };
      });
    }, 600);
  }, [update]);

  const rerollCand = useCallback((i) => {
    update(s => ({ charCands: s.charCands.map((c, idx) => idx === i ? { ...c, hue: randomHue() } : c) }));
    toast('다시 그렸어요');
  }, [update, toast]);

  const rerollView = useCallback((i) => {
    update(s => ({ charViews: s.charViews.map((v, idx) => idx === i ? { ...v, hue: randomHue() } : v) }));
    toast('다시 그렸어요');
  }, [update, toast]);

  const loadChar = useCallback(() => {
    const views = generateViews();
    update(s => ({
      charName: '동글이', charAge: '3살', charGender: '남성', charHobby: '빵 굽기',
      charLook: '앞치마를 두른 통통한 곰. 둥근 눈, 밀색 털, 밀가루 묻은 베이지 앞치마.',
      charCands: s.charCands.length ? s.charCands : generateCandidates(3),
      charSelected: 0, charViews: views,
      charMsgs: [...s.charMsgs,
        { role: 'ai', kind: 'text', text: '지난번에 만든 캐릭터를 불러왔어요.' },
        { role: 'ai', kind: 'views', ref: 'views' }]
    }));
  }, [update]);

  const confirmChar = useCallback(() => {
    if (state.charSelected < 0) return;
    update({ charConfirmed: true, charInfoReadOnly: true });
    toast('캐릭터를 확정했어요');
    go('charInfo');
  }, [state.charSelected, update, toast, go]);

  const toggleCharEdit = useCallback(() => {
    update(s => ({ charInfoReadOnly: !s.charInfoReadOnly }));
    if (!state.charInfoReadOnly) toast('캐릭터 정보를 저장했어요');
  }, [state.charInfoReadOnly, update, toast]);

  // ---------- ad ----------
  const applyAd = useCallback(() => { update({ trendPopup: true }); }, [update]);
  const resetSb = useCallback((withTrend) => {
    update({
      sbMsgs: [{
        role: 'ai', kind: 'text', text: withTrend
          ? '이 트렌드로 광고를 만들어볼게요. 먼저 — 오늘 생산한 품목이 있나요? 품목 이름과 수량을 말해주면 생산 기록으로 남겨둘게요.'
          : '광고를 만들기 전에 하나만요 — 오늘 생산한 품목이 있나요? 품목 이름과 수량을 말해주면 생산 기록으로 남겨둘게요.'
      }],
      plan: [], comicCuts: [], sbProdLogged: false
    });
  }, [update]);
  const trendYes = useCallback(() => {
    update({ trendPopup: false, trendApplied: true });
    resetSb(true);
    go('sb');
  }, [update, resetSb, go]);
  const trendNo = useCallback(() => {
    update({ trendPopup: false, trendApplied: false });
    resetSb(false);
    go('sb');
  }, [update, resetSb, go]);
  const goTrendFromAd = useCallback(() => { update({ fromAd: true, trendPopup: false }); go('trend'); }, [update, go]);
  const backToAd = useCallback(() => { update({ fromAd: false, screen: 'ad', trendPopup: true }); }, [update]);

  // ---------- trend ----------
  const toggleTrendAccordion = useCallback((name) => {
    update(s => ({ openTrend: s.openTrend === name ? '' : name }));
  }, [update]);
  const useTrend = useCallback((name) => {
    if (!state.charConfirmed) { toast('캐릭터를 먼저 확정해주세요'); return; }
    update({ trendPick: name, trendApplied: true, fromAd: false });
    resetSb(true);
    go('sb');
  }, [state.charConfirmed, toast, update, resetSb, go]);

  // ---------- storyboard ----------
  const toggleSbSet = useCallback(() => update(s => ({ sbSetOpen: !s.sbSetOpen })), [update]);
  const toggleSbProd = useCallback(() => update(s => ({ sbProdOpen: !s.sbProdOpen })), [update]);

  function aiSb(userText) {
    update({ sbThinking: true });
    setTimeout(() => {
      update(s => {
        if (!s.sbProdLogged) {
          if (/안\s?했|없어|없습니다|안했|건너|아니/.test(userText || '')) {
            return {
              sbThinking: false, sbProdLogged: true,
              sbMsgs: [...s.sbMsgs, { role: 'ai', kind: 'text', text: '알겠어요, 생산 기록은 넘어갈게요. 그럼 어떤 이야기로 광고를 만들까요?' }]
            };
          }
          const name = itemFrom(userText);
          const qty = qtyFrom(userText);
          const day = dayFrom(userText);
          const isToday = day === isoDay(0);
          const id = Date.now();
          return {
            sbThinking: false, sbProdLogged: true,
            items: s.items.includes(name) ? s.items : [...s.items, name],
            prods: [{ id, name, qty, date: day, time: timeFrom(userText), soldOut: '' }, ...s.prods],
            sbMsgs: [...s.sbMsgs,
              { role: 'ai', kind: 'text', text: `'${name}' 생산 기록을 ${fmtDay(day)}${isToday ? '(오늘)' : ''}로 남겼어요. 다르면 아래에서 바로 고쳐주세요. 매진 시각을 비워두면 알림으로 다시 물어볼게요.` },
              { role: 'ai', kind: 'prod', prodId: id },
              { role: 'ai', kind: 'text', text: `그럼 ${name} 이야기로 광고를 만들어볼까요? 알리고 싶은 걸 말해주세요.` }]
          };
        }

        let kind, diffs, payload;
        if (!s.plan.length) {
          const plan = BASE_PLAN.map(c => ({ ...c }));
          if (s.trendApplied) plan[2] = { ...plan[2], line: `'${s.trendPick}' 밈을 그대로 따라 하는 손님 리액션 컷.` };
          kind = 'plan';
          diffs = plan.map(c => ({ label: `${c.n}컷`, from: '아직 없음', to: c.line }));
          payload = { plan };
        } else if (!s.comicCuts.length) {
          const nextLine = '손님이 소금빵을 들고 과장되게 놀라는 컷 — 효과선 추가.';
          const plan = s.plan.map(c => c.n === 3 ? { ...c, line: nextLine } : c);
          kind = 'plan';
          diffs = [{ label: '3컷', from: (s.plan[2] && s.plan[2].line) || '없음', to: nextLine }];
          payload = { plan };
        } else {
          const cuts = s.comicCuts.map(c => c.n === 2 ? { ...c, hue: randomHue() } : c);
          kind = 'comic';
          diffs = [{ label: '2컷 그림', from: '지금 그림', to: '새로 뽑은 그림' }];
          payload = { cuts };
        }
        const pid = 'p' + Date.now() + Math.random().toString(36).slice(2, 6);
        return {
          sbThinking: false,
          pending: { ...s.pending, [pid]: { which: 'sb', kind, diffs, payload, status: 'open' } },
          sbMsgs: [...s.sbMsgs, { role: 'ai', kind: 'confirm', pid }]
        };
      });
    }, 700);
  }

  const sendSb = useCallback(() => {
    const text = state.sbInput.trim();
    if (!text) return;
    update(s => ({ sbInput: '', sbMsgs: [...s.sbMsgs, { role: 'me', kind: 'text', text }] }));
    aiSb(text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.sbInput, update]);

  const makeComic = useCallback(() => {
    if (!state.plan.length) { toast('먼저 대화로 플랜을 만들어주세요'); return; }
    update({ sbThinking: true });
    setTimeout(() => {
      update(s => {
        const base = randomHue();
        const cuts = s.plan.map((c, i) => ({ n: c.n, short: c.short, line: c.line, hue: (base + i * 26) % 360 }));
        const existed = s.comicCuts.length > 0;
        const pid = 'p' + Date.now() + Math.random().toString(36).slice(2, 6);
        return {
          sbThinking: false,
          pending: {
            ...s.pending,
            [pid]: {
              which: 'sb', kind: 'comic', status: 'open',
              diffs: cuts.map(c => ({ label: `${c.n}컷`, from: existed ? '지금 그림' : '아직 없음', to: c.line })),
              payload: { cuts }
            }
          },
          sbMsgs: [...s.sbMsgs, { role: 'ai', kind: 'confirm', pid }]
        };
      });
    }, 900);
  }, [state.plan, toast, update]);

  const rerollCut = useCallback((n) => {
    update(s => ({ comicCuts: s.comicCuts.map(c => c.n === n ? { ...c, hue: randomHue() } : c) }));
    toast(`${n}컷만 다시 그렸어요`);
  }, [update, toast]);

  // ---------- result / save ----------
  const openResult = useCallback(() => go('result'), [go]);
  const backToSb = useCallback(() => update(s => ({ screen: 'sb', stack: s.stack.filter(x => x !== 'result') })), [update]);
  const confirmResult = useCallback(() => go('save'), [go]);
  const download = useCallback(() => {
    update(s => {
      const item = {
        id: Date.now(),
        title: `${s.adType} · ${s.adConcept}`,
        meta: `${s.trendApplied ? s.trendPick + ' · ' : ''}네컷만화 · 방금 저장`,
        cuts: s.comicCuts.map(c => ({ hue: c.hue }))
      };
      return { history: [item, ...s.history] };
    });
    toast('이미지와 문구를 내려받았어요');
  }, [update, toast]);

  // ---------- my / production ----------
  const myHistory = useCallback(() => update({ myTab: 'history', notifOpen: false }), [update]);
  const myStoreTab = useCallback(() => go('myStore'), [go]);
  const myChar = useCallback(() => {
    if (!state.charConfirmed) { toast('아직 확정된 캐릭터가 없어요'); return; }
    go('charInfo');
  }, [state.charConfirmed, toast, go]);
  const editStoreFromMy = useCallback(() => { update({ storeReadOnly: false }); go('store'); }, [update, go]);
  const openHistoryItem = useCallback((h) => {
    update({ comicCuts: h.cuts.map((c, i) => ({ n: i + 1, short: BASE_PLAN[i].short, hue: c.hue })) });
    go('result');
  }, [update, go]);

  const addItem = useCallback(() => {
    const name = state.newItem.trim();
    if (!name) return;
    update(s => ({ newItem: '', items: s.items.includes(name) ? s.items : [...s.items, name] }));
  }, [state.newItem, update]);
  const delItem = useCallback((name) => {
    update(s => ({ items: s.items.filter(n => n !== name) }));
  }, [update]);
  const renameItem = useCallback((oldName, newName) => {
    update(s => ({
      items: s.items.map(n => n === oldName ? newName : n),
      prods: s.prods.map(p => p.name === oldName ? { ...p, name: newName } : p)
    }));
  }, [update]);

  const addProd = useCallback(() => {
    if (!state.draftItem) { toast('품목을 먼저 골라주세요'); return; }
    const id = Date.now();
    update(s => ({
      prods: [{ id, name: s.draftItem, qty: s.draftQty, date: s.draftDate, time: s.draftTime, soldOut: s.draftSold }, ...s.prods],
      draftQty: '', draftTime: '', draftSold: ''
    }));
    toast('생산 기록을 저장했어요');
  }, [state.draftItem, update, toast]);
  const patchProd = useCallback((id, patch) => {
    update(s => ({ prods: s.prods.map(p => p.id === id ? { ...p, ...patch } : p) }));
  }, [update]);
  const setSoldOut = useCallback((id, value) => {
    patchProd(id, { soldOut: value });
    if (value) toast('매진 시각을 기록했어요');
  }, [patchProd, toast]);
  const delProd = useCallback((id) => {
    update(s => ({ prods: s.prods.filter(p => p.id !== id) }));
  }, [update]);

  const exportData = useCallback(() => {
    update({ backupNote: '백업 파일을 만들었어요 (프로토타입 — 실제 다운로드는 준비 중).', backupErr: false });
  }, [update]);
  const importFile = useCallback(() => {
    update({ backupNote: '이 프로토타입에서는 불러오기가 아직 준비 중이에요.', backupErr: true });
  }, [update]);

  return {
    state,
    charLocked, adLocked,
    actions: {
      set, toast, go, back, goHome, resetDemo,
      goStore, goChar, goAd, goTrendHome, goMy, openProdTab, goData,
      editStore, saveStore, addImage, rerollStoreImage,
      genCandidates, sendChar, selectCand, rerollCand, rerollView, loadChar, confirmChar, toggleCharEdit,
      confirmPending, declinePending,
      applyAd, trendYes, trendNo, goTrendFromAd, backToAd,
      toggleTrendAccordion, useTrend,
      toggleSbSet, toggleSbProd, sendSb, makeComic, rerollCut,
      openResult, backToSb, confirmResult, download,
      myHistory, myStoreTab, myChar, editStoreFromMy, openHistoryItem,
      addItem, delItem, renameItem, addProd, patchProd, setSoldOut, delProd,
      exportData, importFile
    }
  };
}
