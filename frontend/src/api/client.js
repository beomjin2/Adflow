/** 얇은 fetch 래퍼. 상대경로(/api/...)로 호출 — 배포 환경(nginx 같은 origin)과
 * 로컬 dev(vite proxy, vite.config.js의 server.proxy) 양쪽에서 그대로 동작한다. */
async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  const res = await fetch(path, {
    headers: isFormData ? undefined : { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
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
const mapStore = (s) => ({
  storeSaved: s.saved, storeCategory: s.category, storeAddress: s.address,
  storeHours: s.hours, storeOpenTime: s.open_time, storeCloseTime: s.close_time,
  storeClosedDays: s.closed_days, storeDesc: s.desc, storeImages: s.images,
});

const mapCharacter = (c) => ({
  charName: c.name, charAge: c.age, charGender: c.gender, charHobby: c.hobby, charLook: c.look,
  charConfirmed: c.confirmed, charCands: c.candidates, charSelected: c.selected_index,
  charMsgs: c.messages, charPending: c.pending,
});

const mapAd = (a) => ({
  adType: a.ad_type, adConcept: a.ad_concept, trendApplied: a.trend_applied, trendPick: a.trend_pick,
});

const mapStoryboard = (sb) => ({
  sbMsgs: sb.messages, plan: sb.plan, comicCuts: sb.comic_cuts,
  sbProdLogged: sb.prod_logged, pending: sb.pending,
});

const mapRecord = (r) => ({
  id: r.id, name: r.name, qty: r.qty, date: r.date, time: r.time, soldOut: r.sold_out,
});

const mapHistory = (h) => ({ id: h.id, title: h.title, meta: h.meta, cuts: h.cuts });

// ---------- store ----------
export const StoreAPI = {
  get: () => get('/api/store').then(mapStore),
  update: (fields) => put('/api/store', fields).then(mapStore),
  save: () => post('/api/store/save').then(mapStore),
  uploadImage: (file) => upload('/api/store/images/upload', file).then(mapStore),
  deleteImage: (i) => del(`/api/store/images/${i}`).then(mapStore),
};

// ---------- character ----------
export const CharacterAPI = {
  get: () => get('/api/character').then(mapCharacter),
  update: (fields) => put('/api/character', fields).then(mapCharacter),
  chat: (text) => post('/api/character/chat', { text }).then(mapCharacter),
  genCandidates: () => post('/api/character/candidates').then(mapCharacter),
  rerollCandidate: (i) => post(`/api/character/candidates/${i}/reroll`).then(mapCharacter),
  select: (i) => post(`/api/character/select/${i}`).then(mapCharacter),
  loadPrevious: () => post('/api/character/load-previous').then(mapCharacter),
  reset: () => post('/api/character/reset').then(mapCharacter),
  confirm: () => post('/api/character/confirm').then(mapCharacter),
  confirmPending: (pid) => post(`/api/character/confirm/${pid}`).then(mapCharacter),
  declinePending: (pid) => post(`/api/character/decline/${pid}`).then(mapCharacter),
};

// ---------- ad ----------
export const AdAPI = {
  get: () => get('/api/ad').then(mapAd),
  update: (fields) => put('/api/ad', fields).then(mapAd),
  apply: () => post('/api/ad/apply'),
  trendYes: () => post('/api/ad/trend-yes').then(mapAd),
  trendNo: () => post('/api/ad/trend-no').then(mapAd),
};

// ---------- trend ----------
export const TrendAPI = {
  get: () => get('/api/trend'),
  use: (name) => post(`/api/trend/use/${encodeURIComponent(name)}`).then(mapAd),
};

// ---------- storyboard ----------
export const StoryboardAPI = {
  get: () => get('/api/storyboard').then(mapStoryboard),
  chat: (text, { adType, trendApplied, trendPick }) => {
    const qs = new URLSearchParams({
      ad_type: adType, trend_applied: String(trendApplied), trend_pick: trendPick || '',
    });
    return post(`/api/storyboard/chat?${qs.toString()}`, { text }).then(mapStoryboard);
  },
  confirm: (pid) => post(`/api/storyboard/confirm/${pid}`).then(mapStoryboard),
  decline: (pid) => post(`/api/storyboard/decline/${pid}`).then(mapStoryboard),
  makeComic: () => post('/api/storyboard/comic').then(mapStoryboard),
  rerollCut: (n) => post(`/api/storyboard/cuts/${n}/reroll`).then(mapStoryboard),
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
};
