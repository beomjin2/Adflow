import { colors } from '../theme.js';

const TITLES = {
  home: ['AI 광고 만들기', '가게 정보로 광고 문구를 만들어요'],
  store: (s) => ['가게 정보', s.storeReadOnly ? '저장된 내용을 보고 있어요' : '입력하는 중'],
  char: ['마스코트 캐릭터 만들기', '대화로 캐릭터를 완성해요'],
  charInfo: ['캐릭터 정보', '확정한 마스코트'],
  ad: ['광고 만들기', '종류와 느낌을 골라주세요'],
  trend: ['트렌드 확인', '요즘 뜨는 밈을 둘러봐요'],
  sb: ['알릴 내용 정하기', '대화로 만들고 대화로 고쳐요'],
  result: (s) => ['완성된 광고', s.adType ? `${s.adType} 기준` : '내용을 확인해주세요'],
  save: ['저장하기', '복사해서 바로 올리세요'],
  my: ['내 정보', '보관함 · 생산 기록 · 가게 · 캐릭터 · 백업'],
  myStore: ['내 가게 정보', '조회 전용']
};

export default function AppShell({ state, actions, missingProdsCount, children }) {
  const titleEntry = TITLES[state.screen] || TITLES.home;
  const [title, subtitle] = typeof titleEntry === 'function' ? titleEntry(state) : titleEntry;
  const showChips = state.screen === 'sb' || state.screen === 'result';
  // 값이 있는 것만 보여준다. 고른 적 없는 '인스타 게시물'이 머리말에 떠 있으면 고른 줄 안다.
  const chips = [state.adType, state.adConcept, state.charName].filter(Boolean);

  return (
    <div style={{ minHeight: '100vh', padding: '18px 14px 56px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
      <div style={{ width: '100%', maxWidth: 1020, display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: 14, fontWeight: 800, color: colors.primary, letterSpacing: -.2 }}>AI 광고 만들기</span>
        <div style={{ flex: 1 }} />
        <div style={{ position: 'relative' }}>
          <button onClick={() => actions.set('notifOpen', !state.notifOpen)} style={{
            height: 40, borderRadius: 999, padding: '0 14px', fontSize: 13.5, fontWeight: 700,
            border: `1px solid ${missingProdsCount ? colors.warnBorder : colors.cardBorder}`,
            background: missingProdsCount ? colors.warnBg : '#fff',
            color: missingProdsCount ? colors.warnText : colors.textSub,
            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 7
          }}>
            알림
            {missingProdsCount > 0 && (
              <span style={{ fontSize: 11.5, fontWeight: 800, background: colors.warnAccent, color: '#fff', borderRadius: 999, padding: '2px 7px' }}>
                {missingProdsCount}
              </span>
            )}
          </button>
          {state.notifOpen && (
            <div style={{
              position: 'absolute', top: 46, right: 0, width: 322, maxWidth: 'calc(100vw - 28px)', background: '#fff',
              border: `1px solid ${colors.cardBorder}`, borderRadius: 14, boxShadow: '0 14px 30px rgba(18,22,26,.16)',
              padding: 12, display: 'flex', flexDirection: 'column', gap: 9, zIndex: 60, animation: 'pop .16s ease'
            }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: colors.textFaint, letterSpacing: .3 }}>알림</span>
              {missingProdsCount === 0 ? (
                <span style={{ fontSize: 13.5, lineHeight: '20px', color: colors.textFaint, padding: '4px 2px 8px' }}>
                  지금은 알려드릴 게 없어요. 매진 시각이 빈 기록이 생기면 여기로 알려드려요.
                </span>
              ) : state.prods.filter(p => !p.soldOut).map(p => (
                <div key={p.id} style={{ display: 'flex', alignItems: 'center', gap: 10, background: colors.warnBg, border: `1px solid ${colors.warnBorder}`, borderRadius: 11, padding: '10px 11px' }}>
                  <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <span style={{ fontSize: 13.5, fontWeight: 700, color: colors.warnText }}>‘{p.name}’ 매진 시각을 적어주세요</span>
                    <span style={{ fontSize: 12.5, color: colors.warnText2 }}>{p.date} {p.time} 생산{p.qty ? ' · ' + p.qty : ''}</span>
                  </div>
                  <button onClick={actions.openProdTab} style={{ height: 40, borderRadius: 9, border: 0, background: colors.warnText2, color: '#fff', fontSize: 13, fontWeight: 700, padding: '0 13px', cursor: 'pointer', flex: 'none' }}>입력</button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div style={{ width: '100%', maxWidth: 1020, background: '#fff', borderRadius: 20, boxShadow: '0 2px 6px rgba(20,28,36,.05)', overflow: 'hidden', border: `1px solid ${colors.cardBorder}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 18px', borderBottom: `1px solid ${colors.cardBorder}`, background: '#fff', flexWrap: 'wrap' }}>
          {state.screen !== 'home' && (
            <button onClick={actions.back} aria-label="뒤로" style={{ width: 44, height: 44, borderRadius: 12, border: 0, background: colors.softBg, color: colors.text, cursor: 'pointer', fontSize: 18, display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>←</button>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1, minWidth: 0 }}>
            <span style={{ fontSize: 18, fontWeight: 700, letterSpacing: -.3 }}>{title}</span>
            <span style={{ fontSize: 12.5, fontWeight: 500, color: colors.textFaint }}>{subtitle}</span>
          </div>
          {showChips && chips.length > 0 && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', paddingLeft: 6 }}>
              {chips.map((text, i) => (
                <span key={i} style={{ fontSize: 12, fontWeight: 600, background: colors.bg, border: `1px solid ${colors.cardBorder}`, color: colors.textSub, borderRadius: 999, padding: '5px 11px' }}>
                  {text}
                </span>
              ))}
            </div>
          )}
          <div style={{ flex: 1 }} />
          {(state.screen === 'store' && state.storeReadOnly) || state.screen === 'myStore' ? (
            <span style={{ fontSize: 12, fontWeight: 700, background: colors.primarySoft, color: colors.primarySoftText, borderRadius: 999, padding: '6px 12px' }}>조회 모드</span>
          ) : null}
          {/* 트렌드 확인 화면의 주 동작. 본문에 두면 목록 위에 버튼만 있는 빈 줄이 하나 생겨서
              헤더의 남는 오른쪽 공간으로 올렸다. */}
          {state.screen === 'trend' && (
            <button
              onClick={() => actions.set('trendRecommendPopupOpen', true)}
              style={{
                height: 38, padding: '0 16px', borderRadius: 999, border: 0, flex: 'none',
                background: colors.primary, color: '#fff', boxShadow: '0 4px 10px rgba(22,160,107,.3)',
                fontSize: 13.5, fontWeight: 700, cursor: 'pointer',
              }}
            >
              ✨ 밈 추천받기
            </button>
          )}
        </div>

        {children}
      </div>

      {state.toast && (
        <div role="status" style={{
          position: 'fixed', left: '50%', bottom: 28, transform: 'translateX(-50%)',
          maxWidth: 'calc(100vw - 32px)', textAlign: 'center',
          background: colors.dark, color: '#fff', fontSize: 14.5, fontWeight: 600,
          padding: '13px 20px', borderRadius: 16, boxShadow: '0 10px 24px rgba(18,22,26,.25)',
          animation: 'pop .18s ease', zIndex: 40, lineHeight: '21px'
        }}>{state.toast}</div>
      )}
    </div>
  );
}
