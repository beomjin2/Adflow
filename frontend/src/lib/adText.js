/** 광고 문구를 만든다. 재료는 사장님이 직접 넣은 것뿐이다 —
 *  가게 정보, 대화로 정한 컷, 생산 기록.
 *
 *  예전 화면은 '눈이 번쩍! 소금빵 갓 나왔습니다', '#연남동빵집' 같은 문장을 코드에 박아두고
 *  모든 가게에 똑같이 보여줬다. 소금빵을 팔지 않는 가게에도 소금빵 광고가 나왔다.
 *  여기서는 재료가 없으면 그 줄을 아예 만들지 않는다. 지어내지 않는다. */

/** 주소에서 동네 이름만. '서울 마포구 연남로 21' → '연남로'가 아니라 행정동만 집는다. */
function neighborhood(address) {
  if (!address) return '';
  const token = address
    .split(/\s+/)
    .find((t) => /(동|읍|면)$/.test(t) && t.length >= 2 && !/^[0-9]/.test(t));
  return token || '';
}

/** 공백·기호를 빼서 해시태그로 쓸 수 있는 형태로. 빈 문자열이면 태그를 만들지 않는다. */
function tagify(word) {
  const cleaned = String(word || '').replace(/[\s#·,./\\]+/g, '');
  return cleaned ? `#${cleaned}` : '';
}

/**
 * @returns {{headline: string, lines: string[], info: string, tags: string[], empty: boolean}}
 */
export function buildAdText(state) {
  const plan = state.plan || [];
  const lines = plan.map((c) => c.line).filter(Boolean);

  // 제목은 사장님이 정한 첫 컷 문장이다. 없으면 제목도 없다.
  const headline = lines[0] || '';

  // 가게 정보 줄 — 있는 항목만 · 로 잇는다. 없는 항목 자리에 예시를 넣지 않는다.
  const hours = state.storeOpenTime && state.storeCloseTime
    ? `${state.storeOpenTime} – ${state.storeCloseTime}`
    : '';
  const info = [state.storeCategory, state.storeAddress, hours].filter(Boolean).join(' · ');

  // 해시태그 — 업종, 동네, 최근 생산 품목에서만 뽑는다.
  const recentItems = (state.prods || []).slice(0, 2).map((p) => p.name).filter(Boolean);
  const tags = [
    ...recentItems.map(tagify),
    tagify(state.storeCategory),
    tagify(neighborhood(state.storeAddress)),
  ].filter((t, i, arr) => t && arr.indexOf(t) === i);

  return { headline, lines, info, tags, empty: lines.length === 0 };
}

/** 인스타에 그대로 붙여 넣을 수 있는 한 덩어리 텍스트. */
export function adTextForClipboard(state) {
  const { lines, info, tags } = buildAdText(state);
  return [lines.join('\n'), info, tags.join(' ')].filter(Boolean).join('\n\n');
}

/** 확정된 캐릭터 그림 한 장 — 사장님이 고른 후보 그 장이다. */
export function characterImage(state) {
  const picked = (state.charCands || [])[state.charSelected];
  return picked && picked.status === 'done' ? picked.image : null;
}
