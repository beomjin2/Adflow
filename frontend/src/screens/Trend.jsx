import { useEffect, useMemo, useRef, useState } from 'react';
import { colors } from '../theme.js';
import { TextInput, Select } from '../components/ui/Field.jsx';
import { PrimaryButton, SecondaryButton } from '../components/ui/Button.jsx';
import { situationLabel } from '../lib/situationLabel.js';

/** 화면에 보여줄 날짜 — periodStart(스파이크 구간 시작일) > peakDate(스파이크 정점일)
 *  > published(등록일) 순으로 있는 값을 쓴다. 스파이크를 못 찾은 밈은 peakDate까지
 *  비어 있을 수 있어 등록일로 대신한다.
 *
 *  표기를 "2026.09.06" 하나로 맞춘다. 값마다 출처가 달라 모양이 제각각이다 —
 *  네이버에서 온 periodStart 는 "2026-09-06", Trend A Word 등록일은 "2026.09.09",
 *  고구마팜 등록일은 "2026. 08. 26". 그대로 두면 한 목록에 세 가지가 섞인다.
 *  숫자 8자리를 못 뽑으면(형식을 모르는 값이면) 원문 그대로 둔다 — 지어내지 않는다.
 *  정렬은 이 함수 결과에서 숫자만 다시 뽑아 쓰므로 표기를 바꿔도 순서는 그대로다. */
function trendDate(m) {
  const raw = m.periodStart || m.peakDate || m.published || '';
  const d = raw.replace(/\D/g, '');
  if (d.length < 8) return raw;
  return `${d.slice(0, 4)}.${d.slice(4, 6)}.${d.slice(6, 8)}`;
}

/** "2026-08-26" / "2026. 08. 26" 같은 표기에서 숫자만 뽑아 날짜로 만든다. 값이 없으면
 *  null — 막대그래프에서 "정보없음"으로 최하 높이가 된다. */
function parsePublished(str) {
  const digits = (str || '').replace(/\D/g, '');
  if (digits.length < 8) return null;
  const y = Number(digits.slice(0, 4));
  const m = Number(digits.slice(4, 6));
  const d = Number(digits.slice(6, 8));
  const dt = new Date(y, m - 1, d);
  return Number.isNaN(dt.getTime()) ? null : dt;
}

/** 유행 상태 — periodStart/periodEnd 가 둘 다 있을 때만 "유행 중 / 유행 종료"와 기간을 낸다.
 *  검색 신호를 못 잡아 날짜를 정점일·등록일로 대신한 밈(estimated)은 지금도 쓰이는지 알 수
 *  없으므로 배지도 기간도 만들지 않는다 — 시작일을 대신할 수는 있어도 "아직 유행 중인가"는
 *  대신할 수 없다. */
/** 유행 상태 — periodStart/periodEnd 가 둘 다 있을 때만 낸다.
 *  검색 신호를 못 잡아 날짜를 정점일·등록일로 대신한 밈(estimated)은 지금도 쓰이는지
 *  알 수 없으므로 판정하지 않는다 — 시작일은 대신할 수 있어도 "아직 유행 중인가"는
 *  대신할 수 없다.
 *  base 는 수집 기준일. 그날로부터 3일 안까지 신호가 잡혔으면 아직 쓰이는 중으로 본다. */
function trendStatus(m, base) {
  const s = parsePublished(m.periodStart);
  const e = parsePublished(m.periodEnd);
  if (!s || !e || !base) return { estimated: true, ongoing: false };
  const ongoing = (base.getTime() - e.getTime()) / 86400000 <= 3;
  return { estimated: false, ongoing };
}

/** 팝업 공통 — **가시성**이 목적이다.
 *
 *  전에는 배경이 rgba(...,.42) 뿐이고 블러도 없어서, 뒤의 밈 목록(칩·카드가 빽빽한
 *  화면)이 그대로 비쳐 팝업이 떠 있는지가 잘 안 보였다. 같은 화면의 이미지 확대
 *  팝업은 이미 .72 를 쓰고 있었다 — 그쪽에 맞춘다.
 *
 *  내용이 길 때 아래가 잘리던 것도 같이 고친다(maxHeight + 스크롤). */
const POPUP_OVERLAY = {
  position: 'fixed', inset: 0, background: 'rgba(15,17,19,.66)', zIndex: 100,
  display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
  backdropFilter: 'blur(3px)', WebkitBackdropFilter: 'blur(3px)',
};

const POPUP_CARD = {
  width: '100%', background: '#fff', borderRadius: 18, padding: 22,
  display: 'flex', flexDirection: 'column', gap: 14, animation: 'pop .18s ease',
  boxShadow: '0 24px 60px rgba(0,0,0,.34)', border: '1px solid rgba(0,0,0,.06)',
  maxHeight: '86vh', overflowY: 'auto',
};

export default function Trend({ state, actions }) {
  // 밈 대표 이미지 확대 보기. 썸네일이 150px 정사각으로 잘려 있어 원본 구도가 안 보인다 —
  // 눌러서 원본 비율 그대로 크게 볼 수 있게 한다. 열려 있는 이미지 URL만 담는다(null이면 닫힘).
  const [zoomImage, setZoomImage] = useState(null);
  // 썸네일 호버 여부. 인라인 스타일이라 :hover 를 못 쓰고 상태로 들고 있는다.
  const [thumbHover, setThumbHover] = useState(false);

  const {
    trendItems, trendCollectedAt, trendFilter, trendSearch, trendSort, trendSel, trendOnlyOngoing,
    trendRecommendNote, trendRecommendLoading, trendRecommendResult, trendRecommendPopupOpen,
  } = state;

  // 트렌드 확인 화면에 들어올 때마다 추천 팝업을 먼저 보여준다 — 화면 안에 묻혀있던
  // "카테고리 고르고 추천받기"가 눈에 안 띈다는 피드백을 반영. 화면을 나갔다 다시
  // 들어오면(컴포넌트가 다시 마운트되면) 또 뜬다.
  useEffect(() => {
    actions.set('trendRecommendPopupOpen', true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 밈 필터 — meam/memes_classified.json의 situation(상황 카테고리)을 기준으로 고른다.
  // 값이 없는 항목은 필터 목록에 안 넣는다(분류가 안 된 구버전 데이터일 수 있으니).
  // 광고에 바로 쓰기 애매한 카테고리는 개수와 상관없이 뒤로 보낸다 — 불만_토로는 뒤쪽,
  // 미분류는 그중에서도 맨 마지막(가장 낮은 우선순위)으로 고정한다.
  const situationRank = (name) => {
    if (name === '미분류') return 2;
    if (name === '불만_토로') return 1;
    return 0;
  };
  const situations = useMemo(() => {
    const counts = new Map();
    for (const m of trendItems) {
      if (!m.situation) continue;
      counts.set(m.situation, (counts.get(m.situation) || 0) + 1);
    }
    const list = Array.from(counts, ([situation, count]) => ({ situation, count }));
    return list.sort((a, b) => situationRank(a.situation) - situationRank(b.situation) || b.count - a.count);
  }, [trendItems]);

  // 수집 기준일 — 서버가 준 collected_at(crawling/memes_all.json 의 _meta.generated_at).
  // "유행 중" 판정과 하단 표기가 같은 값을 쓴다. 실행 시각(오늘)을 쓰면 크롤링 주기가
  // 길 때 살아 있던 밈이 전부 종료로 바뀌고, periodEnd 의 최댓값으로 추정하면 최근에
  // 뜬 밈이 하나도 없는 달에 기준일이 통째로 과거로 밀린다.
  const baseDate = useMemo(() => parsePublished(trendCollectedAt), [trendCollectedAt]);

  const filtered = useMemo(() => {
    const q = trendSearch.trim();
    return trendItems.filter((m) => {
      if (trendFilter !== '전체' && m.situation !== trendFilter) return false;
      if (trendOnlyOngoing && !trendStatus(m, baseDate).ongoing) return false;
      if (!q) return true;
      return m.name.includes(q) || m.origin.includes(q) || m.summary.includes(q);
    });
  }, [trendItems, trendFilter, trendSearch, trendOnlyOngoing, baseDate]);

  const sorted = useMemo(() => {
    if (trendSort === '이름순') return filtered.slice().sort((a, b) => a.name.localeCompare(b.name, 'ko'));
    if (trendSort === '과거순') {
      // 배열을 그대로 뒤집으면 날짜 정보가 없는 밈(최신순 맨 끝)이 맨 앞으로 튀어나온다 —
      // 날짜 없음은 어느 방향으로 정렬해도 맨 뒤에 있어야 하니, 날짜 숫자로 직접 오름차순
      // 정렬하고 빈 값만 가장 큰 값으로 취급해 계속 맨 뒤에 둔다.
      const dateKey = (m) => trendDate(m).replace(/\D/g, '') || '99999999';
      return filtered.slice().sort((a, b) => dateKey(a).localeCompare(dateKey(b)));
    }
    // 백엔드가 이미 최신순으로 준다.
    return filtered;
  }, [filtered, trendSort]);


  // 처음 들어오면 오른쪽이 비어 있어 화면이 허전하다. 목록 맨 위 밈을 자동으로 연다.
  // 필터·검색·정렬로 목록이 바뀌어 고른 밈이 사라지면 다시 맨 위로 옮긴다.
  // 단, 상세 패널 "닫기"로 일부러 선택을 비웠을 땐 자동으로 다시 채우지 않는다 —
  // closedRef가 없으면 닫기가 trendSel을 ''로 만드는 순간 이 effect가 "선택이
  // 사라졌다"고 보고 곧장 맨 위 밈을 다시 선택해버려서, 닫기 버튼이 아예 안 먹혔다.
  const closedRef = useRef(false);
  useEffect(() => {
    if (!sorted.length) {
      if (trendSel) actions.set('trendSel', '');
      return;
    }
    if (trendSel === '' && closedRef.current) return;
    if (!sorted.some((m) => m.id === trendSel)) actions.set('trendSel', sorted[0].id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sorted, trendSel]);

  const selected = trendItems.find((m) => m.id === trendSel) || null;
  const selStatus = selected ? trendStatus(selected, baseDate) : null;
  const selectMeme = (id) => { closedRef.current = false; actions.set('trendSel', id); };
  const closeSelected = () => { closedRef.current = true; actions.set('trendSel', ''); };

  const filterChip = (label, on, onClick) => (
    <button
      key={label}
      onClick={onClick}
      style={{
        height: 30, padding: '0 13px', borderRadius: 999,
        border: `1.5px solid ${on ? colors.primary : colors.cardBorder}`,
        background: on ? colors.primarySoft : '#fff',
        color: on ? colors.primarySoftText : colors.textSub,
        fontSize: 12, fontWeight: 700, cursor: 'pointer',
      }}
    >
      {label}
    </button>
  );

  return (
    <div style={{ padding: 22, display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 상단에 있던 막대그래프·사이트별 요약과, 아래 목록과 똑같던 필터 칩 줄을 걷어냈다.
          막대 높이로 쓸 수 있는 값이 없었고(네이버는 절대 검색량을 주지 않는다),
          사이트별 카드는 아래 목록과 같은 밈을 순서만 바꿔 한 번 더 보여주고 있었다.
          추천 버튼은 AppShell 헤더 오른쪽으로 옮겼다. */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <div style={{ flex: '1 1 300px', minWidth: 0, background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 16, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: '13px 14px', borderBottom: `1px solid ${colors.cardBorder}`, display: 'flex', flexDirection: 'column', gap: 9, background: colors.bg }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <TextInput
                value={trendSearch}
                onChange={(e) => actions.set('trendSearch', e.target.value)}
                placeholder="밈 검색 — 이름·설명"
                style={{ flex: 1, minWidth: 0, height: 40 }}
              />
              <SecondaryButton
                onClick={() => {
                  actions.set('trendSearch', '');
                  actions.set('trendFilter', '전체');
                  actions.set('trendOnlyOngoing', false);
                }}
                style={{ flex: 'none', height: 40, padding: '0 13px', fontSize: 13 }}
              >
                초기화
              </SecondaryButton>
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {filterChip(`전체 (${trendItems.length})`, trendFilter === '전체', () => actions.set('trendFilter', '전체'))}
              {situations.map((s) => filterChip(
                `${situationLabel(s.situation)} (${s.count})`,
                trendFilter === s.situation,
                () => actions.set('trendFilter', s.situation),
              ))}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 11.5, color: colors.textFaint, whiteSpace: 'nowrap', flex: 'none' }}>{sorted.length}개 밈</span>
              <span style={{ flex: 1 }} />
              <label
                style={{
                  display: 'flex', alignItems: 'center', gap: 5, flex: 'none', cursor: 'pointer',
                  fontSize: 11.5, fontWeight: 700, whiteSpace: 'nowrap',
                  color: trendOnlyOngoing ? colors.primarySoftText : colors.textSub,
                  background: trendOnlyOngoing ? colors.primarySoft : colors.softBg,
                  border: `1px solid ${trendOnlyOngoing ? colors.primary : colors.cardBorder}`,
                  borderRadius: 999, padding: '4px 10px',
                }}
              >
                <input
                  type="checkbox"
                  checked={trendOnlyOngoing}
                  onChange={(e) => actions.set('trendOnlyOngoing', e.target.checked)}
                  style={{ width: 13, height: 13, margin: 0, accentColor: colors.primary, cursor: 'pointer' }}
                />
                유행 중만
              </label>
              <Select
                value={trendSort}
                onChange={(e) => actions.set('trendSort', e.target.value)}
                style={{ height: 30, fontSize: 12, padding: '0 6px', width: 84, flex: 'none' }}
              >
                <option value="최신순">최신순</option>
                <option value="과거순">과거순</option>
                <option value="이름순">이름순</option>
              </Select>
            </div>
          </div>

          <div style={{ padding: 10, display: 'flex', flexDirection: 'column', gap: 7, maxHeight: 460, overflowY: 'auto' }}>
            {sorted.length === 0 && (
              <span style={{ fontSize: 12.5, lineHeight: '19px', color: colors.textFaint, padding: '14px 6px' }}>
                검색 결과가 없어요 — 다른 키워드로 찾아보세요.
              </span>
            )}
            {sorted.map((m) => {
              const on = trendSel === m.id;
              return (
                <button
                  key={m.id}
                  onClick={() => selectMeme(m.id)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10, width: '100%', minHeight: 46, cursor: 'pointer',
                    border: `1.5px solid ${on ? colors.primary : colors.cardBorder}`,
                    background: on ? colors.onboardBg : '#fff', borderRadius: 12, padding: '9px 12px',
                  }}
                >
                  <span style={{
                    fontSize: 10.5, fontWeight: 800, color: on ? colors.primarySoftText : colors.textSub,
                    background: on ? colors.primarySoft : colors.softBg, borderRadius: 7, padding: '4px 2px',
                    flex: 'none', width: 92, textAlign: 'center', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>{situationLabel(m.situation)}</span>
                  {trendStatus(m, baseDate).ongoing && (
                    <span
                      title="아직 유행 중"
                      style={{ flex: 'none', width: 6, height: 6, borderRadius: 999, background: colors.primary }}
                    />
                  )}
                  <span style={{
                    flex: 1, minWidth: 0, textAlign: 'left', fontSize: 13.5, fontWeight: 700, color: colors.text,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>{m.name}</span>
                  <span style={{ fontSize: 11.5, fontWeight: 700, color: colors.textFaint, flex: 'none', width: 72, textAlign: 'right', whiteSpace: 'nowrap' }}>
                    {trendDate(m) || '-'}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {selected && (
          <div style={{ flex: '1.25 1 340px', minWidth: 0, background: '#fff', border: `1.5px solid ${colors.onboardBorder}`, borderRadius: 16, padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
              <div
                onClick={() => selected.image && setZoomImage(selected.image)}
                onMouseEnter={() => setThumbHover(true)}
                onMouseLeave={() => setThumbHover(false)}
                style={{ flex: 'none', width: 150, height: 150, borderRadius: 13, border: `1px solid ${colors.cardBorder}`, background: colors.bg, overflow: 'hidden', cursor: selected.image ? 'zoom-in' : 'default', position: 'relative' }}
              >
                {selected.image ? (
                  <>
                    <img src={selected.image} alt={selected.name} style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
                    {/* 올려놨을 때만 반투명하게 덮고 가운데 돋보기를 띄운다 — 눌러서 크게 볼 수 있다는 신호 */}
                    <div
                      aria-hidden="true"
                      style={{
                        position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                        background: 'rgba(17,19,22,.42)', opacity: thumbHover ? 1 : 0,
                        transition: 'opacity .16s ease', pointerEvents: 'none',
                      }}
                    >
                      <svg
                        width="34" height="34" viewBox="0 0 24 24" fill="none"
                        stroke="#fff" strokeWidth="2" strokeLinecap="round"
                        style={{ transform: thumbHover ? 'scale(1)' : 'scale(.85)', transition: 'transform .16s ease' }}
                      >
                        <circle cx="10.5" cy="10.5" r="6.5" />
                        <line x1="15.5" y1="15.5" x2="21" y2="21" />
                        <line x1="10.5" y1="7.8" x2="10.5" y2="13.2" />
                        <line x1="7.8" y1="10.5" x2="13.2" y2="10.5" />
                      </svg>
                    </div>
                  </>
                ) : (
                  <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, color: colors.textFaint, textAlign: 'center', padding: 8 }}>
                    이미지 없음
                  </div>
                )}
              </div>

              <div style={{ flex: '1 1 220px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 18, fontWeight: 700, letterSpacing: -.3 }}>{selected.name}</span>
                  <span style={{ fontSize: 11, fontWeight: 700, color: colors.textSub, background: colors.softBg, borderRadius: 999, padding: '4px 9px' }}>
                    {selected.sourceLabel}
                  </span>
                  {/* 아직 쓰이는 밈만 표시한다. "유행 종료"까지 배지로 달면 회색 배지가 목록의
                      절반을 덮어 초록 배지의 강조가 죽는다 — 끝났다는 건 아래 "유행 기간" 칸이
                      과거형(N일간)과 흐린 색으로 알려준다. */}
                  {selStatus && !selStatus.estimated && selStatus.ongoing && (
                    <span style={{
                      fontSize: 11, fontWeight: 700, borderRadius: 999, padding: '4px 9px',
                      color: colors.primarySoftText, background: colors.primarySoft,
                    }}>
                      ● 유행 중
                    </span>
                  )}
                </div>

                {selected.origin && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <span style={{ fontSize: 10.5, fontWeight: 800, color: colors.textFaint, letterSpacing: .3 }}>유래</span>
                    <span style={{ fontSize: 13, lineHeight: '20px', color: colors.text, whiteSpace: 'pre-line' }}>{selected.origin}</span>
                  </div>
                )}

                {selected.summary && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <span style={{ fontSize: 10.5, fontWeight: 800, color: colors.textFaint, letterSpacing: .3 }}>활용 예시</span>
                    <span style={{ fontSize: 13, lineHeight: '20px', color: colors.textSub, whiteSpace: 'pre-line' }}>{selected.summary}</span>
                  </div>
                )}

                <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
                  {[
                    // 조회수는 목업용 가짜 숫자였다(README) — 네이버는 절대 검색량을 안 준다.
                    // 그 자리에 "유행 기간"을 넣어봤지만 뺐다: period_start~period_end 는 검색
                    // 신호가 잡힌 구간이지 밈이 그 기간 내내 유행했다는 뜻이 아니라서, 숫자로
                    // 박아두면 재지 않은 걸 잰 것처럼 보인다(냐냐냥 196일째 같은 값이 나온다).
                    // 지금 쓸 수 있는 밈인지는 제목 옆 "유행 중" 배지가 답한다.
                    { k: '사이트', v: selected.sourceLabel },
                    { k: '유행 시작일', v: trendDate(selected) || '정보없음' },
                  ].map((st) => (
                    <div key={st.k} style={{ background: colors.bg, borderRadius: 10, padding: '8px 11px', display: 'flex', flexDirection: 'column', gap: 2, minWidth: 92 }}>
                      <span style={{ fontSize: 10.5, fontWeight: 600, color: colors.textFaint }}>{st.k}</span>
                      <span style={{ fontSize: 13.5, fontWeight: 700, color: colors.text }}>{st.v}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap' }}>
              <PrimaryButton onClick={actions.useTrendMeme} style={{ flex: '1 1 200px', height: 44 }}>
                이 밈으로 광고 만들기
              </PrimaryButton>
              {selected.url && (
                <a
                  href={selected.url}
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    flex: 'none', height: 44, padding: '0 16px', borderRadius: 11, border: `1.5px solid ${colors.inputBorder}`,
                    background: '#fff', color: colors.text, fontSize: 14, fontWeight: 700,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', textDecoration: 'none',
                  }}
                >
                  원문에서 보기
                </a>
              )}
              <SecondaryButton onClick={closeSelected} style={{ flex: 'none', height: 44, padding: '0 16px' }}>
                닫기
              </SecondaryButton>
            </div>
          </div>
        )}
      </div>

      {/* 날짜의 출처를 한 줄로 밝힌다. 검색으로 시점을 못 잡은 밈은 원문 등록일을 대신
          보여주고 있어서, 이 문장이 없으면 화면이 모든 날짜를 "유행 시작일"이라고
          말하는 셈이 된다. 수집 기준일도 같이 적는다 — 유행 중 판정이 오늘이 아니라
          이 날짜를 기준으로 돌아가기 때문이다. */}
      <span style={{ fontSize: 11.5, lineHeight: '18px', color: colors.textFaint, padding: '0 2px' }}>
        유행 시작일은 네이버 검색어트렌드 기준이며, 검색 데이터가 없는 일부 밈은 원문 등록일로 대신 표시합니다.
        {baseDate && ` · 최근 수집 ${baseDate.getFullYear()}.${String(baseDate.getMonth() + 1).padStart(2, '0')}.${String(baseDate.getDate()).padStart(2, '0')}`}
        {/* "유행 중" 배지를 무엇으로 판정하는지 적어 둔다(강사님 피드백). 판정은 trendStatus():
            네이버 급등 구간(평소 수준의 3배 또는 최고치의 10% 중 높은 선을 넘은 날들)의 마지막 날이
            수집 기준일로부터 3일 안이면 유행 중. "3배"만 쓰면 10% 조건이 빠져 부정확해 뭉뚱그려 적는다. */}
        <br />
        '유행 중'은 수집일 기준 최근 3일 안까지 네이버 검색량이 평소보다 크게 높게 유지된 밈입니다.
      </span>

      {trendRecommendPopupOpen && !trendRecommendResult && (
        <div
          onClick={(e) => { if (e.target === e.currentTarget) actions.set('trendRecommendPopupOpen', false); }}
          style={{
            ...POPUP_OVERLAY,
          }}
        >
          <div style={{
            ...POPUP_CARD, maxWidth: 380,
          }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <span style={{ fontSize: 17, fontWeight: 700, letterSpacing: -.3 }}>✨ 밈 추천받기</span>
              <span style={{ fontSize: 13, lineHeight: '19px', color: colors.textSub }}>
                가게 정보·캐릭터·오늘 알릴 내용을 보고 지금 가장 잘 어울리는 밈을 하나 골라드려요.
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: colors.textFaint }}>오늘 알릴 내용 (선택)</span>
              <TextInput
                value={trendRecommendNote}
                onChange={(e) => actions.set('trendRecommendNote', e.target.value)}
                placeholder="예) 오늘 소금빵 신메뉴 나왔어요"
                style={{ height: 44 }}
              />
            </div>

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <PrimaryButton
                onClick={actions.recommendTrendMeme}
                disabled={trendRecommendLoading}
                style={{ flex: '1 1 160px', height: 46 }}
              >
                {trendRecommendLoading ? '추천 중…' : '추천받기'}
              </PrimaryButton>
              <SecondaryButton
                onClick={() => actions.set('trendRecommendPopupOpen', false)}
                style={{ flex: 'none', height: 46, padding: '0 16px' }}
              >
                괜찮아요, 둘러볼게요
              </SecondaryButton>
            </div>
          </div>
        </div>
      )}

      {trendRecommendResult && (
        <div
          onClick={(e) => { if (e.target === e.currentTarget) actions.closeTrendRecommend(); }}
          style={{
            ...POPUP_OVERLAY,
          }}
        >
          <div style={{
            ...POPUP_CARD, maxWidth: 400,
          }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 11.5, fontWeight: 800, color: colors.primaryHover, letterSpacing: .02 }}>GPT 추천</span>
              <span style={{ fontSize: 13, color: colors.textSub }}>
                지금은 <b style={{ color: colors.text }}>{situationLabel(trendRecommendResult.situation)}</b> 쪽 밈이 어울린다고 보고, 그 안에서 하나 골랐어요.
              </span>
            </div>

            {trendRecommendResult.picks.map((pick) => (
              <div key={pick.meme.id} style={{ display: 'flex', flexDirection: 'column', gap: 9, border: `1px solid ${colors.cardBorder}`, borderRadius: 14, padding: 13 }}>
                <button
                  onClick={() => actions.selectTrendRecommendMeme(pick.meme.id)}
                  title="밈 리스트에서 이 밈 보기"
                  style={{ display: 'flex', gap: 12, alignItems: 'center', border: 0, background: 'transparent', padding: 0, cursor: 'pointer', textAlign: 'left' }}
                >
                  <div style={{ flex: 'none', width: 52, height: 52, borderRadius: 12, background: colors.bg, overflow: 'hidden' }}>
                    {pick.meme.image ? (
                      <img src={pick.meme.image} alt={pick.meme.name} style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
                    ) : null}
                  </div>
                  <div style={{ fontSize: 16, fontWeight: 700, letterSpacing: -.01, color: colors.text }}>{pick.meme.name}</div>
                </button>
                <span style={{ fontSize: 13, lineHeight: '20px', color: colors.textSub, background: colors.softBg, borderRadius: 10, padding: '9px 11px' }}>
                  {pick.reason}
                </span>
                <PrimaryButton onClick={() => actions.useTrendRecommendMeme(pick.meme.id)} style={{ height: 42 }}>
                  이 밈으로 광고 만들기
                </PrimaryButton>
              </div>
            ))}

            <SecondaryButton onClick={actions.closeTrendRecommend} style={{ height: 44 }}>
              닫기
            </SecondaryButton>
          </div>
        </div>
      )}

      {zoomImage && (
        <div
          onClick={() => setZoomImage(null)}
          role="dialog"
          aria-label="밈 이미지 확대 보기"
          style={{
            position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(17,19,22,.72)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24, cursor: 'zoom-out',
          }}
        >
          {/* 원본이 긴 변 480px 라 <img> 를 그냥 두면 실제 크기대로만 나와서 "확대"가 체감되지 않는다.
              고정 크기 상자 안에서 object-fit: contain 으로 채워 비율은 지키면서 키운다. */}
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: 'min(92vw, 780px)', height: 'min(84vh, 780px)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'default',
            }}
          >
            <img
              src={zoomImage}
              alt=""
              style={{
                width: '100%', height: '100%', objectFit: 'contain', display: 'block',
                borderRadius: 12, filter: 'drop-shadow(0 20px 60px rgba(0,0,0,.45))',
              }}
            />
          </div>
          <button
            type="button"
            onClick={() => setZoomImage(null)}
            aria-label="닫기"
            style={{
              position: 'fixed', top: 20, right: 24, width: 40, height: 40, borderRadius: 999,
              border: 'none', background: 'rgba(255,255,255,.92)', color: '#111316',
              fontSize: 20, lineHeight: '40px', cursor: 'pointer',
            }}
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
}
