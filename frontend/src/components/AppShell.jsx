import { useEffect, useRef } from 'react';
import { colors } from '../theme.js';

const TITLES = {
  home: ['AI 광고 만들기', '가게 정보로 광고 문구를 만들어요'],
  store: (s) => ['가게 정보', s.storeReadOnly ? '저장된 내용을 보고 있어요' : '입력하는 중'],
  char: ['마스코트 캐릭터 만들기', '대화로 캐릭터를 완성해요'],
  charInfo: ['캐릭터 정보', '확정한 마스코트'],
  ad: ['광고 만들기', '종류와 느낌을 골라주세요'],
  trend: ['트렌드 보고서', '요즘 뜨는 밈을 둘러봐요'],
  sb: ['알릴 내용 정하기', '대화로 만들고 대화로 고쳐요'],
  result: (s) => ['완성된 광고', s.adType ? `${s.adType} 기준` : '내용을 확인해주세요'],
  save: ['저장하기', '복사해서 바로 올리세요'],
  my: ['내 정보', '보관함 · 생산 기록 · 가게 · 캐릭터 · 백업'],
  myStore: ['내 가게 정보', '조회 전용'],
};

// 단계 화면에서 "지금 어디쯤인지"를 머리말 위에 적는다.
const CRUMB = { store: '1단계', char: '2단계', ad: '3단계', sb: '3단계', result: '3단계', save: '3단계' };

// 흰 카드(.ad-body) 안에 넣지 않는 화면. 개선안에서 이 두 화면은 카드 여러 장이
// 배경 위에 나란히 놓인 모양이라, 큰 카드로 한 번 더 감싸면 테두리가 두 겹이 된다.
const FULL_BLEED = new Set(['ad', 'sb']);

export default function AppShell({ state, actions, missingProdsCount, children }) {
  const titleEntry = TITLES[state.screen] || TITLES.home;
  const [title, subtitle] = typeof titleEntry === 'function' ? titleEntry(state) : titleEntry;
  const isHome = state.screen === 'home';
  const showChips = state.screen === 'sb' || state.screen === 'result';
  // 값이 있는 것만 보여준다. 고른 적 없는 '인스타 게시물'이 머리말에 떠 있으면 고른 줄 안다.
  const chips = [state.adType, state.adConcept, state.charName].filter(Boolean);
  const bellRef = useRef(null);

  // 바깥을 누르면 알림이 닫힌다 — 예전엔 한 번 열면 다른 걸 눌러도 떠 있었다.
  useEffect(() => {
    if (!state.notifOpen) return undefined;
    const onDown = (e) => { if (bellRef.current && !bellRef.current.contains(e.target)) actions.set('notifOpen', false); };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [state.notifOpen, actions]);

  const missing = state.prods.filter((p) => !p.soldOut);

  return (
    <div className="ad-page">
      <div className="ad-wrap">
        <header className="ad-top">
          <button className="ad-brand" onClick={actions.goHome}><i>AD</i>AI 광고 만들기</button>
          <span className="ad-grow" />
          <div className="ad-bell" ref={bellRef}>
            <button className="ad-notice" aria-haspopup="true" aria-expanded={state.notifOpen}
              onClick={() => actions.set('notifOpen', !state.notifOpen)}>
              알림<span className={`ad-badge${missingProdsCount ? '' : ' zero'}`}>{missingProdsCount}</span>
            </button>
            {state.notifOpen && (
              <div className="ad-drop" role="menu">
                <div className="ad-drop-h">{missingProdsCount ? `확인할 알림 ${missingProdsCount}건` : '알림'}</div>
                {missingProdsCount === 0 ? (
                  <div className="ad-drop-empty">지금은 알려드릴 게 없어요. 매진 시각이 빈 기록이 생기면 여기로 알려드려요.</div>
                ) : missing.map((p) => (
                  <div className="ad-drop-item" key={p.id}>
                    <span className="dot" />
                    <span className="t">
                      <b>‘{p.name}’ 매진 시각을 적어주세요</b>
                      <span>{p.date} {p.time} 생산{p.qty ? ` · ${p.qty}개` : ''}</span>
                    </span>
                    <button className="go" onClick={() => { actions.set('notifOpen', false); actions.openProdTab(); }}>입력</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </header>

        {isHome ? children : (
          <>
            <div className="ad-ph">
              <button className="ad-back" aria-label="뒤로" onClick={actions.back}>←</button>
              <div className="t">
                {CRUMB[state.screen] && (
                  <span style={{ fontSize: 13, fontWeight: 700, color: colors.primary, letterSpacing: .2 }}>
                    {CRUMB[state.screen]}
                  </span>
                )}
                <h1>{title}</h1>
                <p>{subtitle}</p>
              </div>
              {showChips && chips.length > 0 && (
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {chips.map((text, i) => <span className="ad-chip" key={i}>{text}</span>)}
                </div>
              )}
              <span className="ad-grow" />
              {((state.screen === 'store' && state.storeReadOnly) || state.screen === 'myStore') && (
                <span className="ad-pill green">조회 모드</span>
              )}
              {state.screen === 'trend' && (
                <button className="ad-hdr-btn" onClick={() => actions.set('trendRecommendPopupOpen', true)}>
                  ✨ 밈 추천받기
                </button>
              )}
            </div>
            {FULL_BLEED.has(state.screen) ? children : <div className="ad-body">{children}</div>}
          </>
        )}
      </div>

      {state.toast && (
        <div role="status" style={{
          position: 'fixed', left: '50%', bottom: 28, transform: 'translateX(-50%)',
          maxWidth: 'calc(100vw - 32px)', textAlign: 'center',
          background: colors.dark, color: '#fff', fontSize: 14.5, fontWeight: 600,
          padding: '13px 20px', borderRadius: 16, boxShadow: '0 10px 24px rgba(18,22,26,.25)',
          animation: 'pop .18s ease', zIndex: 40, lineHeight: '21px',
        }}>{state.toast}</div>
      )}
    </div>
  );
}
