import { colors } from '../../theme.js';

export default function DataTab({ state, actions }) {
  const missingProds = state.prods.filter(p => !p.soldOut);
  const summary = [
    { k: '저장된 광고', v: `${state.history.length}건` },
    { k: '생산 기록', v: `${state.prods.length}건${missingProds.length ? ` · 미입력 ${missingProds.length}` : ''}` },
    { k: '품목', v: `${state.items.length}개` },
    { k: '마스코트', v: state.charConfirmed ? `${state.charName || '이름 없음'} · 4방향 이미지` : '아직 확정 안 됨' },
    { k: '가게 정보', v: state.storeSaved ? `${state.storeCategory} · 이미지 ${state.storeImages.length}장` : '미입력' }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 13 }}>
      <div style={{ background: colors.onboardBg, border: `1px solid ${colors.onboardBorder}`, borderRadius: 16, padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={{ fontSize: 15, fontWeight: 700, letterSpacing: -.2 }}>지금까지 만든 모든 것을 파일 하나로 내보내고, 다시 불러올 수 있어요</span>
        <span style={{ fontSize: 12.5, lineHeight: '19px', color: colors.textSub }}>가게 정보 · 마스코트 캐릭터와 이미지 · 품목 · 생산 기록 · 저장된 광고 히스토리 · 광고 설정이 모두 담깁니다.</span>
      </div>

      <div style={{ background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 16, padding: '15px 16px', display: 'flex', flexDirection: 'column', gap: 11 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: colors.textSub }}>이 파일에 담기는 것</span>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: 9 }}>
          {summary.map(b => (
            <div key={b.k} style={{ background: colors.bg, borderRadius: 11, padding: '11px 13px', display: 'flex', flexDirection: 'column', gap: 3 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: colors.textFaint }}>{b.k}</span>
              <span style={{ fontSize: 14, fontWeight: 700, color: colors.text }}>{b.v}</span>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 11, flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 260px', background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 16, padding: '15px 16px', display: 'flex', flexDirection: 'column', gap: 9 }}>
          <span style={{ fontSize: 13.5, fontWeight: 700 }}>내보내기</span>
          <span style={{ fontSize: 12.5, lineHeight: '19px', color: colors.textSub }}>JSON 백업 파일 한 개로 내려받아요. 다른 기기에서 불러오면 그대로 이어서 작업할 수 있어요.</span>
          <span style={{ flex: 1 }} />
          <button onClick={actions.exportData} style={{ height: 48, borderRadius: 12, border: 0, background: colors.primary, color: '#fff', fontSize: 15, fontWeight: 700, cursor: 'pointer', boxShadow: '0 6px 12px rgba(22,160,107,.32)' }}>백업 파일 내보내기</button>
        </div>
        <div style={{ flex: '1 1 260px', background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 16, padding: '15px 16px', display: 'flex', flexDirection: 'column', gap: 9 }}>
          <span style={{ fontSize: 13.5, fontWeight: 700 }}>불러오기</span>
          <span style={{ fontSize: 12.5, lineHeight: '19px', color: colors.textSub }}>내보낸 파일을 고르면 히스토리 · 내 정보 · 마스코트 이미지까지 그대로 복원돼요. 현재 화면의 내용은 덮어써지고, AI와 주고받은 대화는 새로 시작합니다.</span>
          <span style={{ flex: 1 }} />
          <label onClick={actions.importFile} style={{ height: 48, borderRadius: 12, border: `1.5px solid ${colors.inputBorder}`, background: '#fff', color: colors.text, fontSize: 15, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>백업 파일 선택해 불러오기</label>
        </div>
      </div>

      <div style={{
        fontSize: 12.5, lineHeight: '19px', padding: '12px 14px', borderRadius: 12,
        background: state.backupErr ? colors.warnBg : (state.backupNote ? colors.onboardBg : colors.bg),
        border: `1px solid ${state.backupErr ? colors.warnBorder : (state.backupNote ? colors.onboardBorder : colors.cardBorder)}`,
        color: state.backupErr ? colors.warnText : (state.backupNote ? colors.primarySoftText : colors.textFaint),
        fontWeight: state.backupNote ? 600 : 500
      }}>
        {state.backupNote || '내보낸 파일은 이 프로토타입에서만 열 수 있어요.'}
      </div>
    </div>
  );
}
