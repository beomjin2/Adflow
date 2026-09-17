/** 얇은 fetch 래퍼. 상대경로(/api/...)로 호출 — 배포 환경(nginx 같은 origin)과
 * 로컬 dev(vite proxy, vite.config.js의 server.proxy) 양쪽에서 그대로 동작한다.
 *
 * 백엔드는 400에 사람이 읽는 한국어 문장을 detail로 준다
 * (예: "업종 · 주소 · 가게 소개을(를) 채워주세요"). 그 문장을 그대로 화면에 띄운다 —
 * 여기서 "요청 실패"로 뭉개면 사장님은 무엇이 비었는지 알 방법이 없다. */
async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  let res;
  try {
    res = await fetch(path, {
      headers: isFormData ? undefined : { 'Content-Type': 'application/json' },
      ...options,
    });
  } catch {
    throw new Error('인터넷 연결을 확인해주세요. 잠시 뒤 다시 시도해주세요.');
  }
  if (!res.ok) {
    let detail = '';
    try {
      const body = await res.json();
      detail = typeof body.detail === 'string' ? body.detail : '';
    } catch {
      // 본문이 JSON이 아닐 수 있다 — 그러면 상태코드로 안내한다.
    }
    if (!detail) {
      detail = res.status >= 500
        ? '서버에 문제가 생겼어요. 잠시 뒤 다시 시도해주세요.'
        : `요청을 처리하지 못했어요 (${res.status})`;
    }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}

const get = (path) => request(path);
const post = (path, body) => request(path, { method: 'POST', body: body !== undefined ? JSON.stringify(body) : undefined });
const put = (path, body) => request(path, { method: 'PUT', body: JSON.stringify(body) });
const patch = (path, body) => request(path, { method: 'PATCH', body: JSON.stringify(body) });
const del = (path) => request(path, { method: 'DELETE' });
const upload = (path, file) => {
  const form = new FormData();
  form.append('file', file);
  return request(path, { method: 'POST', body: form });
};

// ---------- mappers: snake_case API -> camelCase 프론트 상태 ----------
// ImageItem은 {label, image, status}. image는 그대로 <img src>에 넣는 문자열이고,
// status는 empty | generating | done | failed 다. 서버가 준 값을 해석하지 않고 그대로 쓴다
// (지금은 /api/media/... URL이지만 예전 데이터엔 data URI가 남아 있을 수 있다).
const mapSlot = (s) => ({
  label: s?.label || '',
  image: s?.image || null,
  status: s?.status || 'empty',
});

const mapStore = (s) => ({
  storeSaved: s.saved, storeCategory: s.category, storeAddress: s.address,
  storeHours: s.hours, storeOpenTime: s.open_time, storeCloseTime: s.close_time,
  storeClosedDays: s.closed_days || [], storeDesc: s.desc,
  storeImages: (s.images || []).map(mapSlot),
  storeMaxImages: s.max_images,
});

/** 캐릭터 응답에서 "진행 상태"만 뽑는다. 폴링은 3초마다 도는데 이때 시트 입력란까지
 *  덮어쓰면 사장님이 타이핑하던 글자가 사라진다. 그래서 둘을 나눠 둔다.
 *
 *  charSheet(읽기 전용 8줄)는 진행 쪽에 둔다 — 대화가 채운 값을 바로 비춰야 하고,
 *  사장님이 직접 고치는 건 charLook 같은 개별 입력 상태이지 이 배열이 아니다. */
const mapCharacterProgress = (c) => ({
  charConfirmed: c.confirmed,
  charCands: (c.candidates || []).map(mapSlot),
  charSelected: c.selected_index,
  charMsgs: c.messages || [],
  charSheet: c.sheet || [],
  charSheetDone: !!c.sheet_complete,
  charMissing: c.missing || [],
  charEditing: c.editing || '',
  charPending: c.pending || {},
  charGenerating: !!c.generating,
  charQueue: c.queue_depth || 0,
  charEta: c.eta_seconds || 0,
});

const mapCharacter = (c) => ({
  charName: c.name, charAge: c.age, charGender: c.gender, charLook: c.look,
  charOutfit: c.outfit, charAbilities: c.abilities, charDesc: c.desc,
  charKeywords: (c.keywords || []).join(', '),
  ...mapCharacterProgress(c),
});

const mapAd = (a) => ({ adType: a.ad_type, adConcept: a.ad_concept });

const mapStoryboard = (sb) => ({
  sbMsgs: sb.messages || [], plan: sb.plan || [],
  sbProdLogged: sb.prod_logged, pending: sb.pending || {},
  comicCuts: (sb.comic_cuts || []).map((c) => ({ ...mapSlot(c), n: c.n, line: c.line })),
  sbGenerating: !!sb.generating,
  sbEta: sb.eta_seconds || 0,
});

const mapRecord = (r) => ({
  id: r.id, name: r.name, qty: r.qty, date: r.date, time: r.time, soldOut: r.sold_out,
});

const mapHistory = (h) => ({ id: h.id, title: h.title, meta: h.meta, cuts: h.cuts || [] });

// ---------- store ----------
export const StoreAPI = {
  get: () => get('/api/store').then(mapStore),
  update: (fields) => put('/api/store', fields).then(mapStore),
  save: () => post('/api/store/save').then(mapStore),
  uploadImage: (file) => upload('/api/store/images/upload', file).then(mapStore),
  deleteImage: (i) => del(`/api/store/images/${i}`).then(mapStore),
};

// ---------- character ----------
// 대화로 시트 8칸을 채우고, 다 찬 뒤에 genCandidates()로 그림을 뽑는다.
// 생성은 백그라운드로 돈다 — POST는 즉시 돌아오고 칸이 status:"generating"으로 생기며,
// 실제 그림은 getProgress()를 3초 간격으로 불러서 채운다.
//
// chat()은 그림을 돌리지 않는다. 생성은 사장님이 버튼을 눌렀을 때만 시작된다.
export const CharacterAPI = {
  get: () => get('/api/character').then(mapCharacter),
  getProgress: () => get('/api/character').then(mapCharacterProgress),
  update: (fields) => put('/api/character', fields).then(mapCharacter),
  chat: (text) => post('/api/character/chat', { text }).then(mapCharacterProgress),
  // 시트에서 칸을 눌러 "이 칸을 대화로 고치겠다"고 알린다.
  focus: (field) => post(`/api/character/focus/${field}`).then(mapCharacterProgress),
  acceptSuggestion: (pid) => post(`/api/character/suggestions/${pid}/accept`).then(mapCharacter),
  declineSuggestion: (pid) => post(`/api/character/suggestions/${pid}/decline`).then(mapCharacterProgress),
  genCandidates: () => post('/api/character/candidates').then(mapCharacterProgress),
  rerollCandidate: (i) => post(`/api/character/candidates/${i}/reroll`).then(mapCharacterProgress),
  select: (i) => post(`/api/character/select/${i}`).then(mapCharacterProgress),
  loadPrevious: () => post('/api/character/load-previous').then(mapCharacterProgress),
  reset: () => post('/api/character/reset').then(mapCharacter),
  confirm: () => post('/api/character/confirm').then(mapCharacter),
};

// ---------- ad ----------
// 광고 단계에서 정하는 건 컷 구성·대사(텍스트)뿐이다. 이미지 생성은 없다.
export const AdAPI = {
  get: () => get('/api/ad').then(mapAd),
  update: (fields) => put('/api/ad', fields).then(mapAd),
  // { ok, message } 를 돌려준다. 앞 단계가 안 끝났으면 400 + 무엇이 비었는지.
  apply: () => post('/api/ad/apply'),
};

// ---------- storyboard ----------
export const StoryboardAPI = {
  get: () => get('/api/storyboard').then(mapStoryboard),
  chat: (text) => post('/api/storyboard/chat', { text }).then(mapStoryboard),
  confirm: (pid) => post(`/api/storyboard/confirm/${pid}`).then(mapStoryboard),
  decline: (pid) => post(`/api/storyboard/decline/${pid}`).then(mapStoryboard),
  makeComic: () => post('/api/storyboard/comic').then(mapStoryboard),
  rerollCut: (n) => post(`/api/storyboard/comic/${n}/reroll`).then(mapStoryboard),
  propose: (memeId) => post('/api/storyboard/propose', { meme_id: memeId }).then(mapStoryboard),
};

// ---------- meme ----------
const mapMeme = (m) => ({ id: m.id, title: m.title, source: m.source, card: m.card || {} });
export const MemeAPI = {
  list: () => get('/api/memes').then((rows) => rows.map(mapMeme)),
  create: (body) => post('/api/memes', body).then(mapMeme),
  remove: (id) => del(`/api/memes/${id}`),
};

// ---------- production ----------
export const ProductionAPI = {
  listItems: () => get('/api/production/items').then((rows) => rows.map((r) => r.name)),
  addItem: (name) => post('/api/production/items', { name }).then((r) => r.name),
  renameItem: (oldName, newName) => put(`/api/production/items/${encodeURIComponent(oldName)}`, { name: newName }),
  deleteItem: (name) => del(`/api/production/items/${encodeURIComponent(name)}`),
  listRecords: () => get('/api/production/records').then((rows) => rows.map(mapRecord)),
  addRecord: (body) => post('/api/production/records', body).then(mapRecord),
  patchRecord: (id, patchBody) => patch(`/api/production/records/${id}`, patchBody).then(mapRecord),
  deleteRecord: (id) => del(`/api/production/records/${id}`),
};

// ---------- history ----------
export const HistoryAPI = {
  list: () => get('/api/history').then((rows) => rows.map(mapHistory)),
  add: (body) => post('/api/history', body).then(mapHistory),
  exportAll: () => get('/api/history/export'),
};

// ---------- trend ----------
// 이름이 mapMeme가 아니라 mapTrendMeme인 이유: 위 MemeAPI 쪽 mapMeme(밈 카드)와
// 이름은 같아 보여도 다른 데이터 모양이라 겹치면 안 된다.
const mapTrendMeme = (m) => ({
  id: m.id, source: m.source, sourceLabel: m.source_label, name: m.name,
  url: m.url, image: m.image, origin: m.origin, summary: m.summary,
  published: m.published, views: m.views, category: m.category,
  situation: m.situation || '', situationScore: m.situation_score, adSafe: m.ad_safe,
});

export const TrendAPI = {
  list: () => get('/api/trend').then((r) => ({
    trendItems: (r.items || []).map(mapTrendMeme),
    trendSites: r.sites || [],
  })),
};
