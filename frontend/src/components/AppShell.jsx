import { colors } from '../theme.js';

const TITLES = {
  home: ['AI 광고 만들기', '네컷만화 광고를 3단계로'],
  store: (s) => ['가게 정보', s.storeReadOnly ? '저장된 내용을 보고 있어요' : '편집 중'],
  char: ['마스코트 캐릭터 만들기', 'AI와 대화하며 캐릭터를 완성해요'],
  charInfo: ['캐릭터 정보', '확정된 마스코트'],
  ad: ['광고 생성', '종류와 컨셉을 고르세요'],
  trend: ['트렌드 확인', '이번 주 뜨는 것들'],
  sb: (s) => [s.trendApplied ? '스토리보드 및 트렌드 선택' : '스토리보드', '대화로 만들고 대화로 고쳐요'],
  result: (s) => ['결과 크게 보기', `${s.adType} 기준`],
  save: ['결과물 저장', '내려받고 바로 올리세요'],
  my: ['내 정보', '히스토리 · 생산 기록 · 가게 · 캐릭터 · 백업'],
  myStore: ['내 가게 정보', '조회 전용']
};

const URL_PATHS = {
  home: '/', store: '/store', char: '/character', charInfo: '/character/info',
  ad: '/ad/new', trend: '/trend', sb: '/ad/storyboard', result: '/ad/result',
  save: '/ad/save', my: '/me', myStore: '/me/store'
};

export default function AppShell({ state, actions, missingProdsCount, children }) {
  const titleEntry = TITLES[state.screen] || TITLES.home;
  const [title, subtitle] = typeof titleEntry === 'function' ? titleEntry(state) : titleEntry;
  const showSettings = state.screen === 'sb' || state.screen === 'result';
  const chips = [
    { text: state.adType, accent: false },
    { text: state.adConcept, accent: false },
    state.trendApplied ? { text: state.trendPick, accent: true } : null,
    state.charName ? { text: state.charName, accent: false } : null
  ].filter(Boolean);

  return (
    <div style={{ minHeight: '100vh', padding: '22px 18px 56px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}>
      <div style={{ width: '100%', maxWidth: 1020, display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 999, padding: '6px 12px 6px 10px' }}>
          <Dot /><Dot /><Dot />
          <span style={{ fontSize: 11.5, color: colors.textFaint, marginLeft: 8, fontFamily: 'ui-monospace,Menlo,monospace' }}>
            ai-ad.kr{URL_PATHS[state.screen] || '/'}
          </span>
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ position: 'relative' }}>
          <button onClick={() => actions.set('notifOpen', !state.notifOpen)} style={{
            height: 32, borderRadius: 999, padding: '0 12px', fontSize: 12.5, fontWeight: 700,
            border: `1px solid ${missingProdsCount ? colors.warnBorder : colors.cardBorder}`,
            background: missingProdsCount ? colors.warnBg : '#fff',
            color: missingProdsCount ? colors.warnText : colors.textSub,
            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 7
          }}>
            알림
            {missingProdsCount > 0 && (
              <span style={{ fontSize: 11, fontWeight: 800, background: colors.warnAccent, color: '#fff', borderRadius: 999, padding: '2px 7px' }}>
                {missingProdsCount}
              </span>
            )}
          </button>
          {state.notifOpen && (
            <div style={{
              position: 'absolute', top: 40, right: 0, width: 322, background: '#fff',
              border: `1px solid ${colors.cardBorder}`, borderRadius: 14, boxShadow: '0 14px 30px rgba(18,22,26,.16)',
              padding: 12, display: 'flex', flexDirection: 'column', gap: 9, zIndex: 60, animation: 'pop .16s ease'
            }}>
              <span style={{ fontSize: 11.5, fontWeight: 700, color: colors.textFaint, letterSpacing: .3 }}>알림</span>
              {missingProdsCount === 0 ? (
                <span style={{ fontSize: 12.5, lineHeight: '19px', color: colors.textFaint, padding: '4px 2px 8px' }}>
                  매진 시각이 빈 생산 기록이 없어요. 새 기록이 생기면 여기로 알려드려요.
                </span>
              ) : state.prods.filter(p => !p.soldOut).map(p => (
                <div key={p.id} style={{ display: 'flex', alignItems: 'center', gap: 10, background: colors.warnBg, border: `1px solid ${colors.warnBorder}`, borderRadius: 11, padding: '10px 11px' }}>
                  <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <span style={{ fontSize: 12.5, fontWeight: 700, color: colors.warnText }}>'{p.name}' 매진 시각을 적어주세요</span>
                    <span style={{ fontSize: 11.5, color: colors.warnText2 }}>{p.date} {p.time} 생산{p.qty ? ' · ' + p.qty : ''}</span>
                  </div>
                  <button onClick={actions.openProdTab} style={{ height: 32, borderRadius: 9, border: 0, background: colors.warnText2, color: '#fff', fontSize: 12, fontWeight: 700, padding: '0 11px', cursor: 'pointer', flex: 'none' }}>입력</button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div style={{ width: '100%', maxWidth: 1020, background: '#fff', borderRadius: 20, boxShadow: '0 2px 6px rgba(20,28,36,.05)', overflow: 'hidden', border: `1px solid ${colors.cardBorder}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 20px', borderBottom: `1px solid ${colors.cardBorder}`, background: '#fff' }}>
          {state.screen !== 'home' && (
            <button onClick={actions.back} aria-label="뒤로" style={{ width: 34, height: 34, borderRadius: 10, border: 0, background: colors.softBg, color: colors.text, cursor: 'pointer', fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>←</button>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <span style={{ fontSize: 17, fontWeight: 700, letterSpacing: -.3 }}>{title}</span>
            <span style={{ fontSize: 11.5, fontWeight: 500, color: colors.textFaint }}>{subtitle}</span>
          </div>
          {showSettings && chips.length > 0 && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', paddingLeft: 6 }}>
              {chips.map((c, i) => (
                <span key={i} style={c.accent
                  ? { fontSize: 11, fontWeight: 700, background: colors.primarySoft, color: colors.primarySoftText, borderRadius: 999, padding: '5px 11px' }
                  : { fontSize: 11, fontWeight: 600, background: colors.bg, border: `1px solid ${colors.cardBorder}`, color: colors.textSub, borderRadius: 999, padding: '4px 10px' }}>
                  {c.text}
                </span>
              ))}
            </div>
          )}
          <div style={{ flex: 1 }} />
          {(state.screen === 'store' && state.storeReadOnly) || state.screen === 'myStore' ? (
            <span style={{ fontSize: 11, fontWeight: 700, background: colors.primarySoft, color: colors.primarySoftText, borderRadius: 999, padding: '5px 11px' }}>조회 모드</span>
          ) : null}
        </div>

        {children}
      </div>

      {state.toast && (
        <div style={{
          position: 'fixed', left: '50%', bottom: 28, transform: 'translateX(-50%)',
          background: colors.dark, color: '#fff', fontSize: 13.5, fontWeight: 600,
          padding: '12px 20px', borderRadius: 999, boxShadow: '0 10px 24px rgba(18,22,26,.25)',
          animation: 'pop .18s ease', zIndex: 40
        }}>{state.toast}</div>
      )}

      <span style={{ fontSize: 11.5, color: colors.textFaint }}>프로토타입 · 이미지는 생성 자리표시자입니다</span>
    </div>
  );
}

function Dot() {
  return <span style={{ width: 9, height: 9, border: `1.6px solid ${colors.cardBorder}`, borderRadius: '50%', display: 'inline-block' }} />;
}
