import { colors, cardBase } from '../theme.js';

export default function Home({ state, actions, charLocked, adLocked }) {
  const missingProds = state.prods.filter(p => !p.soldOut);

  const storeStatus = state.storeSaved ? '입력 완료 · 보기/수정' : '미입력';
  const charStatus = state.charConfirmed ? `확정 — ${state.charName}` : charLocked ? '잠김 · 가게 정보 먼저' : '아직 없음';
  const adStatus = adLocked ? '잠김 · 캐릭터 먼저' : '시작할 수 있어요';
  const prodStatus = state.prods.length
    ? (missingProds.length ? `매진 미입력 ${missingProds.length}건` : `기록 ${state.prods.length}건 · 모두 입력됨`)
    : '기록 없음';

  return (
    <div style={{ padding: '24px 22px 26px', display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{ background: colors.onboardBg, border: `1px solid ${colors.onboardBorder}`, borderRadius: 16, padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={{ fontSize: 19, fontWeight: 700, letterSpacing: -.4 }}>가게 정보만 넣으면, AI가 네컷만화 광고를 만들어 드려요</span>
        <span style={{ fontSize: 13.5, lineHeight: '20px', color: colors.textSub }}>
          가게 정보 → 마스코트 캐릭터 → 스토리보드 대화 → 네컷만화. 세 단계만 거치면 인스타에 바로 올릴 수 있는 빵집 광고가 나옵니다.
        </span>
      </div>

      {missingProds.length > 0 && (
        <button onClick={actions.openProdTab} style={{ cursor: 'pointer', textAlign: 'left', background: colors.warnBg, border: `1px solid ${colors.warnBorder}`, borderRadius: 14, padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13.5, fontWeight: 700, color: colors.warnText }}>매진 시각이 비어 있는 생산 기록 {missingProds.length}건</span>
          <span style={{ fontSize: 12.5, color: colors.warnText2, lineHeight: '18px' }}>언제 매진됐는지 적어두면 다음 광고 타이밍을 잡아드려요</span>
          <span style={{ flex: 1 }} />
          <span style={{ fontSize: 12.5, fontWeight: 700, color: colors.warnText2 }}>지금 입력 →</span>
        </button>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(210px,1fr))', gap: 12 }}>
        <StepCard onClick={actions.goStore} step="STEP 1" title="가게 정보 입력" desc="업종 · 상품 사진 · 영업시간"
          status={storeStatus} statusColor={state.storeSaved ? colors.primary : colors.warnAccent} />
        <StepCard onClick={actions.goChar} step="STEP 2" title="마스코트 캐릭터" desc="AI와 대화하며 캐릭터를 만들어요"
          status={charStatus} statusColor={state.charConfirmed ? colors.primary : charLocked ? colors.textFaint : colors.warnAccent}
          locked={charLocked} />
        <StepCard onClick={actions.goAd} step="STEP 3" title="광고 생성" desc="종류 · 컨셉을 고르고 네컷만화까지"
          status={adStatus} statusColor={adLocked ? colors.textFaint : colors.primary} locked={adLocked} />
        <StepCard onClick={actions.goTrendHome} step="언제든지" stepColor="#4A86C5" title="트렌드 확인" desc="이번 주 뜨는 밈·해시태그 대시보드"
          status="바로 열기" statusColor={colors.textFaint} />
        <StepCard onClick={actions.openProdTab} step="언제든지" stepColor="#4A86C5" title="생산 기록" desc="품목 · 생산 시각 · 매진 시각"
          status={prodStatus} statusColor={missingProds.length ? colors.warnAccent : state.prods.length ? colors.primary : colors.textFaint} />
      </div>

      <button onClick={actions.goMy} style={{ cursor: 'pointer', background: colors.softBg, border: 0, borderRadius: 14, padding: '15px 18px', display: 'flex', alignItems: 'center', gap: 12, textAlign: 'left' }}>
        <span style={{ fontSize: 14, fontWeight: 700 }}>내 정보</span>
        <span style={{ fontSize: 12.5, color: colors.textSub }}>히스토리 · 생산 기록 · 가게/캐릭터 정보 · 내보내기</span>
        <span style={{ flex: 1 }} />
        <span style={{ fontSize: 12, fontWeight: 700, color: colors.textSub }}>저장된 광고 {state.history.length}개 →</span>
      </button>
    </div>
  );
}

function StepCard({ onClick, step, stepColor = colors.primary, title, desc, status, statusColor, locked }) {
  return (
    <button onClick={onClick} style={{ ...cardBase, cursor: locked ? 'not-allowed' : 'pointer', opacity: locked ? .45 : 1, border: `1px solid ${colors.cardBorder}` }}>
      <span style={{ fontSize: 11, fontWeight: 700, color: stepColor, letterSpacing: .4 }}>{step}</span>
      <span style={{ fontSize: 16, fontWeight: 700 }}>{title}</span>
      <span style={{ fontSize: 12.5, lineHeight: '18px', color: colors.textSub }}>{desc}</span>
      <span style={{ fontSize: 12, fontWeight: 700, color: statusColor }}>{status}</span>
    </button>
  );
}
