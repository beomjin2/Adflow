import { colors, cardBase } from '../theme.js';
import { PrimaryButton, SecondaryButton } from '../components/ui/Button.jsx';

export default function Home({ state, actions, charLocked, adLocked }) {
  const missingProds = state.prods.filter(p => !p.soldOut);

  const storeStatus = state.storeSaved ? '입력 완료 · 보기/수정' : '아직 안 하셨어요';
  const charStatus = state.charConfirmed
    ? (state.charName ? `확정 — ${state.charName}` : '확정함')
    : charLocked ? '가게 정보를 먼저 넣어주세요' : '아직 안 하셨어요';
  const adStatus = adLocked ? '캐릭터를 먼저 정해주세요' : '시작할 수 있어요';
  const prodStatus = state.prods.length
    ? (missingProds.length ? `매진 시각 미입력 ${missingProds.length}건` : `기록 ${state.prods.length}건`)
    : '기록 없음';

  return (
    <div style={{ padding: '24px 22px 26px', display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{ background: colors.onboardBg, border: `1px solid ${colors.onboardBorder}`, borderRadius: 16, padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={{ fontSize: 20, fontWeight: 700, letterSpacing: -.4, lineHeight: '29px' }}>
          가게 정보만 넣으면, 광고 문구를 만들어 드려요
        </span>
        <span style={{ fontSize: 14.5, lineHeight: '22px', color: colors.textSub }}>
          가게 정보 → 마스코트 캐릭터 → 알릴 내용 대화. 순서대로 누르시면 됩니다.
          중간에 그만두셔도 적어둔 건 그대로 남아요.
        </span>
      </div>

      {missingProds.length > 0 && (
        <button onClick={actions.openProdTab} style={{ cursor: 'pointer', textAlign: 'left', background: colors.warnBg, border: `1px solid ${colors.warnBorder}`, borderRadius: 14, padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', minHeight: 48 }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: colors.warnText }}>매진 시각이 비어 있는 기록 {missingProds.length}건</span>
          <span style={{ fontSize: 13, color: colors.warnText2, lineHeight: '19px' }}>언제 다 팔렸는지 적어두면 다음 광고 시간을 잡아드려요</span>
          <span style={{ flex: 1 }} />
          <span style={{ fontSize: 13, fontWeight: 700, color: colors.warnText2 }}>지금 입력 →</span>
        </button>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 12 }}>
        <StepCard onClick={actions.goStore} step="1단계" title="가게 정보 넣기" desc="업종 · 상품 사진 · 영업시간"
          status={storeStatus} statusColor={state.storeSaved ? colors.primary : colors.warnAccent} />
        <StepCard onClick={actions.goChar} step="2단계" title="마스코트 캐릭터" desc="대화로 우리 가게 캐릭터를 만들어요"
          status={charStatus} statusColor={state.charConfirmed ? colors.primary : charLocked ? colors.textFaint : colors.warnAccent}
          locked={charLocked} />
        <StepCard onClick={actions.openAdEntry} step="3단계" title="광고 만들기" desc="종류와 느낌을 고르고 내용을 정해요"
          status={adStatus} statusColor={adLocked ? colors.textFaint : colors.primary} locked={adLocked} />
        <StepCard onClick={actions.openProdTab} step="언제든지" stepColor="#4A86C5" title="생산 기록" desc="품목 · 만든 시각 · 매진 시각"
          status={prodStatus} statusColor={missingProds.length ? colors.warnAccent : state.prods.length ? colors.primary : colors.textFaint} />
        <StepCard onClick={actions.goTrend} step="언제든지" stepColor="#7B5CFA" title="트렌드 확인" desc="요즘 뜨는 밈을 둘러봐요"
          status={state.trendItems.length ? `${state.trendItems.length}개 수집됨` : '아직 없음'}
          statusColor={state.trendItems.length ? colors.primary : colors.textFaint} />
      </div>

      <button onClick={actions.goMy} style={{ cursor: 'pointer', background: colors.softBg, border: 0, borderRadius: 14, padding: '16px 18px', display: 'flex', alignItems: 'center', gap: 12, textAlign: 'left', flexWrap: 'wrap', minHeight: 48 }}>
        <span style={{ fontSize: 15, fontWeight: 700 }}>내 정보</span>
        <span style={{ fontSize: 13, color: colors.textSub }}>보관함 · 생산 기록 · 가게/캐릭터 정보 · 백업</span>
        <span style={{ flex: 1 }} />
        <span style={{ fontSize: 13, fontWeight: 700, color: colors.textSub }}>
          {state.history.length ? `보관한 광고 ${state.history.length}개 →` : '열기 →'}
        </span>
      </button>

      {state.adEntryOpen && (
        <div
          onClick={(e) => { if (e.target === e.currentTarget) actions.closeAdEntry(); }}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(15,17,19,.4)', zIndex: 100,
            display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
          }}
        >
          <div style={{
            width: '100%', maxWidth: 380, background: '#fff', borderRadius: 18, padding: 22,
            display: 'flex', flexDirection: 'column', gap: 16, animation: 'pop .18s ease',
            boxShadow: '0 20px 50px rgba(0,0,0,.22)',
          }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span style={{ fontSize: 17, fontWeight: 700, letterSpacing: -.3 }}>광고를 어떻게 만들까요?</span>
              <span style={{ fontSize: 13.5, lineHeight: '20px', color: colors.textSub }}>
                요즘 뜨는 밈을 참고해서 만들 수도 있고, 바로 내용을 정할 수도 있어요.
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
              <PrimaryButton onClick={actions.pickAdEntryTrend}>
                트렌드 참고해서 만들기
              </PrimaryButton>
              <SecondaryButton onClick={actions.pickAdEntryDirect}>
                트렌드 없이 바로 만들기
              </SecondaryButton>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StepCard({ onClick, step, stepColor = colors.primary, title, desc, status, statusColor, locked }) {
  return (
    <button
      onClick={onClick}
      aria-disabled={locked || undefined}
      style={{ ...cardBase, cursor: locked ? 'not-allowed' : 'pointer', opacity: locked ? .5 : 1, border: `1px solid ${colors.cardBorder}`, minHeight: 130 }}
    >
      <span style={{ fontSize: 12, fontWeight: 700, color: stepColor, letterSpacing: .4 }}>{step}</span>
      <span style={{ fontSize: 17, fontWeight: 700 }}>{title}</span>
      <span style={{ fontSize: 13.5, lineHeight: '20px', color: colors.textSub }}>{desc}</span>
      <span style={{ fontSize: 13, fontWeight: 700, color: statusColor }}>{status}</span>
    </button>
  );
}
