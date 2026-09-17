import { useEffect, useMemo } from 'react';
import { colors, cardBase } from '../theme.js';
import { TextInput, Select } from '../components/ui/Field.jsx';
import { PrimaryButton, SecondaryButton } from '../components/ui/Button.jsx';

/** 사이트별로 최근 3건씩 보여주는 요약 카드. 원본 디자인(fix_for_yeonjin/dashboard.html)엔
 *  막대그래프·순위를 "조회수"로 매겼지만 그건 목업용 가짜 숫자였다(README 참고) — 네이버
 *  계열 트렌드는 상대 검색량만 주지 절대 조회수를 안 준다. */
function siteTopItems(items, source) {
  return items.filter((m) => m.source === source).slice(0, 3);
}

/** 화면에 보여줄 날짜 — periodStart(스파이크 구간 시작일) > peakDate(스파이크 정점일)
 *  > published(등록일) 순으로 있는 값을 쓴다. 스파이크를 못 찾은 밈은 peakDate까지
 *  비어 있을 수 있어 등록일로 대신하고, 위픽레터처럼 등록일도 없는 소스는 결국
 *  "정보없음"으로 남는다. */
function trendDate(m) {
  return m.periodStart || m.peakDate || m.published || '';
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

function daysAgo(str) {
  const dt = parsePublished(str);
  if (!dt) return null;
  return Math.max(0, Math.floor((Date.now() - dt.getTime()) / 86400000));
}

export default function Trend({ state, actions }) {
  const {
    trendItems, trendSites, trendFilter, trendSearch, trendSort, trendSel,
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

  const filtered = useMemo(() => {
    const q = trendSearch.trim();
    return trendItems.filter((m) => {
      if (trendFilter !== '전체' && m.situation !== trendFilter) return false;
      if (!q) return true;
      return m.name.includes(q) || m.origin.includes(q) || m.summary.includes(q);
    });
  }, [trendItems, trendFilter, trendSearch]);

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

  // 막대그래프 — 검색/정렬과 무관하게 "밈 필터"만 반영한다(목업의 barSource와 동일).
  // trendItems는 백엔드가 이미 트렌드 날짜(periodStart, 없으면 등록일) 내림차순으로 준다.
  const barSource = useMemo(() => {
    const byFilter = trendFilter === '전체' ? trendItems : trendItems.filter((m) => m.situation === trendFilter);
    return byFilter.slice(0, 5);
  }, [trendItems, trendFilter]);

  // 점수 = "얼마나 최근인가" — daysAgo가 작을수록(최근일수록) 점수가 크다.
  // 날짜를 모르는 항목은 0점으로 가장 짧은 막대가 된다.
  const barScores = useMemo(() => {
    const known = barSource.map((m) => daysAgo(trendDate(m))).filter((d) => d != null);
    const maxKnown = known.length ? Math.max(...known) : 0;
    return barSource.map((m) => {
      const d = daysAgo(trendDate(m));
      return d == null ? 0 : maxKnown - d + 1;
    });
  }, [barSource]);
  const barMax = Math.max(1, ...barScores);

  const selected = trendItems.find((m) => m.id === trendSel) || null;
  const selectMeme = (id) => actions.set('trendSel', id);

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
      <div style={{ ...cardBase, gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: colors.textSub }}>활용 상황</span>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {filterChip(`전체 (${trendItems.length})`, trendFilter === '전체', () => actions.set('trendFilter', '전체'))}
            {situations.map((s) => filterChip(
              `${s.situation} (${s.count})`,
              trendFilter === s.situation,
              () => actions.set('trendFilter', s.situation),
            ))}
          </div>
          <span style={{ flex: 1 }} />
          <button
            onClick={() => actions.set('trendRecommendPopupOpen', true)}
            style={{
              height: 40, padding: '0 18px', borderRadius: 999, border: 0, flex: 'none',
              background: colors.primary, color: '#fff', boxShadow: '0 4px 10px rgba(22,160,107,.3)',
              fontSize: 14, fontWeight: 700, cursor: 'pointer',
            }}
          >
            ✨ 밈 추천받기
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 14, height: 160 }}>
          {barSource.map((m, i) => {
            const on = (trendSel || '') === m.id;
            const height = Math.max(14, Math.round(barScores[i] / barMax * 104));
            return (
              <div key={m.id} style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, justifyContent: 'flex-end', height: '100%' }}>
                <span style={{
                  fontSize: 11.5, fontWeight: on ? 700 : 600, color: on ? colors.text : colors.textSub,
                  textAlign: 'center', lineHeight: '15px', overflow: 'hidden', textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap', width: '100%',
                }}>{m.name}</span>
                <button
                  onClick={() => selectMeme(m.id)}
                  title={m.name}
                  style={{
                    width: '100%', border: 0, padding: 0, cursor: 'pointer', borderRadius: '8px 8px 4px 4px',
                    background: on ? colors.primary : colors.onboardBorder, height,
                  }}
                />
                <span style={{ fontSize: 12, fontWeight: 700, color: on ? colors.primaryHover : colors.primary }}>{trendDate(m) || '정보없음'}</span>
              </div>
            );
          })}
          {barSource.length === 0 && (
            <span style={{ fontSize: 12.5, color: colors.textFaint, alignSelf: 'center' }}>이 필터에 해당하는 밈이 없어요.</span>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(190px,1fr))', gap: 10 }}>
          {trendSites.map((s) => (
            <div key={s.source} style={{ background: colors.bg, borderRadius: 13, padding: '12px 13px', display: 'flex', flexDirection: 'column', gap: 9 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                <span style={{ fontSize: 12.5, fontWeight: 700 }}>{s.label}</span>
                <span style={{ flex: 1 }} />
                <span style={{ fontSize: 10.5, fontWeight: 600, color: colors.textFaint }}>최신순</span>
              </div>
              {siteTopItems(trendItems, s.source).map((m, i) => {
                const on = trendSel === m.id;
                return (
                  <button
                    key={m.id}
                    onClick={() => selectMeme(m.id)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 8, width: '100%', textAlign: 'left',
                      cursor: 'pointer', border: `1.5px solid ${on ? colors.primary : colors.cardBorder}`,
                      background: on ? colors.primarySoft : '#fff', borderRadius: 10, padding: '8px 10px',
                    }}
                  >
                    <span style={{
                      fontSize: 10.5, fontWeight: 800, color: i === 0 ? colors.primarySoftText : colors.textFaint,
                      background: i === 0 ? colors.primarySoft : colors.softBg, borderRadius: 6, padding: '3px 6px', flex: 'none',
                    }}>{i + 1}위</span>
                    <span style={{
                      fontSize: 12.5, fontWeight: 600, color: colors.text, overflow: 'hidden',
                      textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0,
                    }}>{m.name}</span>
                    <span style={{ flex: 1 }} />
                    <span style={{ fontSize: 11, fontWeight: 700, color: colors.textFaint, flex: 'none' }}>{trendDate(m) || '-'}</span>
                  </button>
                );
              })}
              {siteTopItems(trendItems, s.source).length === 0 && (
                <span style={{ fontSize: 12, color: colors.textFaint }}>아직 없어요.</span>
              )}
            </div>
          ))}
        </div>
      </div>

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
                onClick={() => { actions.set('trendSearch', ''); actions.set('trendFilter', '전체'); }}
                style={{ flex: 'none', height: 40, padding: '0 13px', fontSize: 13 }}
              >
                초기화
              </SecondaryButton>
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {filterChip(`전체 (${trendItems.length})`, trendFilter === '전체', () => actions.set('trendFilter', '전체'))}
              {situations.map((s) => filterChip(
                `${s.situation} (${s.count})`,
                trendFilter === s.situation,
                () => actions.set('trendFilter', s.situation),
              ))}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 11.5, color: colors.textFaint, whiteSpace: 'nowrap', flex: 'none' }}>{sorted.length}개 밈</span>
              <span style={{ flex: 1 }} />
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
                  }}>{m.situation || '미분류'}</span>
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
              <div style={{ flex: 'none', width: 150, height: 150, borderRadius: 13, border: `1px solid ${colors.cardBorder}`, background: colors.bg, overflow: 'hidden' }}>
                {selected.image ? (
                  <img src={selected.image} alt={selected.name} style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
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
                    { k: '사이트', v: selected.sourceLabel },
                    { k: '유행 시작일', v: trendDate(selected) || '정보없음' },
                    { k: '조회수', v: selected.views != null ? `${selected.views.toLocaleString()}회` : '정보없음' },
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
              <SecondaryButton onClick={() => actions.set('trendSel', '')} style={{ flex: 'none', height: 44, padding: '0 16px' }}>
                닫기
              </SecondaryButton>
            </div>
          </div>
        )}
      </div>

      {trendRecommendPopupOpen && !trendRecommendResult && (
        <div
          onClick={(e) => { if (e.target === e.currentTarget) actions.set('trendRecommendPopupOpen', false); }}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(15,17,19,.42)', zIndex: 100,
            display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
          }}
        >
          <div style={{
            width: '100%', maxWidth: 380, background: '#fff', borderRadius: 18, padding: 22,
            display: 'flex', flexDirection: 'column', gap: 14, animation: 'pop .18s ease',
            boxShadow: '0 20px 50px rgba(0,0,0,.22)',
          }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <span style={{ fontSize: 17, fontWeight: 700, letterSpacing: -.3 }}>✨ 밈 추천받기</span>
              <span style={{ fontSize: 13, lineHeight: '19px', color: colors.textSub }}>
                어떤 상황에 쓸 밈인지 골라주시면, 그 안에서 캐릭터랑 잘 맞는 걸 하나 골라드려요.
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: colors.textFaint }}>활용 상황</span>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {situations.map((s) => filterChip(
                  `${s.situation} (${s.count})`,
                  trendFilter === s.situation,
                  () => actions.set('trendFilter', s.situation),
                ))}
              </div>
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
                disabled={trendFilter === '전체' || trendRecommendLoading}
                style={{ flex: '1 1 160px', height: 46 }}
              >
                {trendRecommendLoading ? '추천 중…' : trendFilter === '전체' ? '먼저 활용 상황을 골라주세요' : '추천받기'}
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
            position: 'fixed', inset: 0, background: 'rgba(15,17,19,.42)', zIndex: 100,
            display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
          }}
        >
          <div style={{
            width: '100%', maxWidth: 380, background: '#fff', borderRadius: 18, padding: 22,
            display: 'flex', flexDirection: 'column', gap: 16, animation: 'pop .18s ease',
            boxShadow: '0 20px 50px rgba(0,0,0,.22)',
          }}>
            <span style={{ fontSize: 11.5, fontWeight: 800, color: colors.primaryHover, letterSpacing: .02 }}>GPT 추천</span>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
              <div style={{ flex: 'none', width: 56, height: 56, borderRadius: 12, background: colors.bg, overflow: 'hidden' }}>
                {trendRecommendResult.meme.image ? (
                  <img src={trendRecommendResult.meme.image} alt={trendRecommendResult.meme.name} style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
                ) : null}
              </div>
              <div>
                <div style={{ fontSize: 17, fontWeight: 700, letterSpacing: -.01 }}>{trendRecommendResult.meme.name}</div>
                <span style={{ display: 'inline-block', marginTop: 3, fontSize: 11, fontWeight: 700, color: colors.textSub, background: colors.softBg, borderRadius: 999, padding: '3px 9px' }}>
                  {trendRecommendResult.meme.situation}
                </span>
              </div>
            </div>
            <span style={{ fontSize: 13, lineHeight: '20px', color: colors.textSub, background: colors.softBg, borderRadius: 10, padding: '10px 12px' }}>
              {trendRecommendResult.reason}
            </span>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <PrimaryButton onClick={actions.useTrendRecommendMeme} style={{ flex: '1 1 140px', height: 44 }}>
                이 밈으로 광고 만들기
              </PrimaryButton>
              <SecondaryButton onClick={actions.recommendTrendMeme} disabled={trendRecommendLoading} style={{ flex: 'none', height: 44, padding: '0 16px' }}>
                다시 추천
              </SecondaryButton>
              <SecondaryButton onClick={actions.closeTrendRecommend} style={{ flex: 'none', height: 44, padding: '0 16px' }}>
                닫기
              </SecondaryButton>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
