import { colors } from '../theme.js';
import { SecondaryButton, PrimaryButton } from '../components/ui/Button.jsx';
import { TRENDS, TREND_DETAIL } from '../mock/aiResponses.js';

const BAR_VALS = [92, 78, 64, 51, 37];
const BAR_LABELS = TRENDS.concat(['가을 신메뉴']).slice(0, 5);

export default function Trend({ state, actions }) {
  return (
    <div style={{ padding: 22, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 16, padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: colors.textSub }}>이번 주 급상승 — 검색량 지수</span>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 14, height: 150 }}>
          {BAR_LABELS.map((label, i) => (
            <div key={label} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, justifyContent: 'flex-end', height: '100%' }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: colors.primary }}>{BAR_VALS[i]}</span>
              <div style={{ width: '100%', borderRadius: '8px 8px 4px 4px', background: i === 0 ? colors.primary : colors.onboardBorder, height: `${Math.round(BAR_VALS[i] * 0.95)}px` }} />
              <span style={{ fontSize: 11.5, fontWeight: 600, color: colors.textSub, textAlign: 'center' }}>{label}</span>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: colors.textSub }}>트렌드 종류 — 누르면 자세히 보기</span>
        {TREND_DETAIL.map((t, i) => {
          const open = state.openTrend === t.name;
          return (
            <div key={t.name} style={{ border: `1px solid ${open ? colors.onboardBorder : colors.cardBorder}`, background: open ? colors.onboardBg : '#fff', borderRadius: 14, overflow: 'hidden' }}>
              <button onClick={() => actions.toggleTrendAccordion(t.name)} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 12, background: 'transparent', border: 0, cursor: 'pointer', padding: '15px 16px', textAlign: 'left' }}>
                <span style={{ fontSize: 11, fontWeight: 800, color: colors.primarySoftText, background: colors.primarySoft, borderRadius: 7, padding: '4px 8px', flex: 'none' }}>{i + 1}위</span>
                <span style={{ fontSize: 14.5, fontWeight: 700, color: colors.text }}>{t.name}</span>
                <span style={{ fontSize: 12, fontWeight: 700, color: colors.primary }}>{t.delta}</span>
                <span style={{ flex: 1 }} />
                <span style={{ fontSize: 15, color: colors.textFaint, transition: 'transform .18s ease', display: 'inline-block', transform: `rotate(${open ? 180 : 0}deg)` }}>⌄</span>
              </button>
              {open && (
                <div style={{ padding: '0 16px 16px', display: 'flex', flexDirection: 'column', gap: 12, animation: 'pop .18s ease' }}>
                  <span style={{ fontSize: 13, lineHeight: '20px', color: colors.textSub }}>{t.summary}</span>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {t.stats.map(st => (
                      <div key={st.k} style={{ background: colors.bg, borderRadius: 10, padding: '9px 12px', display: 'flex', flexDirection: 'column', gap: 2, minWidth: 96 }}>
                        <span style={{ fontSize: 11, fontWeight: 600, color: colors.textFaint }}>{st.k}</span>
                        <span style={{ fontSize: 14, fontWeight: 700, color: colors.text }}>{st.v}</span>
                      </div>
                    ))}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
                    {t.links.map(l => (
                      <div key={l.title} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span style={{ width: 6, height: 6, borderRadius: '50%', background: colors.primary, flex: 'none' }} />
                        <span style={{ fontSize: 13, fontWeight: 600 }}>{l.title}</span>
                        <span style={{ fontSize: 11.5, color: colors.textFaint }}>{l.meta}</span>
                      </div>
                    ))}
                  </div>
                  <button onClick={() => actions.useTrend(t.name)} style={{ alignSelf: 'flex-start', height: 40, borderRadius: 10, border: 0, background: colors.primarySoft, color: colors.primarySoftText, fontSize: 14, fontWeight: 700, padding: '0 16px', cursor: 'pointer' }}>
                    이 트렌드로 광고 만들기
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <SecondaryButton onClick={actions.goHome} style={{ flex: 1, height: 48, fontSize: 15 }}>메인 화면으로</SecondaryButton>
        {state.fromAd && (
          <PrimaryButton onClick={actions.backToAd} style={{ flex: 1, height: 48, fontSize: 15 }}>광고 생성으로 돌아가기</PrimaryButton>
        )}
      </div>
    </div>
  );
}
