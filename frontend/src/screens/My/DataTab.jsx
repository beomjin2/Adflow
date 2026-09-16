import { colors } from '../../theme.js';

export default function DataTab({ state, actions }) {
  const missingProds = state.prods.filter(p => !p.soldOut);
  const summary = [
    { k: '보관한 광고', v: `${state.history.length}건` },
    { k: '생산 기록', v: `${state.prods.length}건${missingProds.length ? ` · 미입력 ${missingProds.length}` : ''}` },
    { k: '품목', v: `${state.items.length}개` },
    { k: '마스코트', v: state.charConfirmed ? (state.charName || '이름 없음') : '아직 확정 안 됨' },
    { k: '가게 정보', v: state.storeSaved ? `${state.storeCategory || '업종 미입력'} · 사진 ${state.storeImages.length}장` : '미입력' }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 13 }}>
      <div style={{ background: colors.onboardBg, border: `1px solid ${colors.onboardBorder}`, borderRadius: 16, padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={{ fontSize: 16, fontWeight: 700, letterSpacing: -.2, lineHeight: '24px' }}>
          적어두신 내용을 파일 하나로 내려받을 수 있어요
        </span>
        <span style={{ fontSize: 13.5, lineHeight: '21px', color: colors.textSub }}>
          가게 정보 · 캐릭터 · 품목 · 생산 기록 · 보관한 광고가 담깁니다. 컴퓨터가 바뀌거나 할 때를 대비해 가끔 받아두세요.
        </span>
      </div>

      <div style={{ background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 16, padding: '15px 16px', display: 'flex', flexDirection: 'column', gap: 11 }}>
        <span style={{ fontSize: 13.5, fontWeight: 700, color: colors.textSub }}>이 파일에 담기는 것</span>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: 9 }}>
          {summary.map(b => (
            <div key={b.k} style={{ background: colors.bg, borderRadius: 11, padding: '11px 13px', display: 'flex', flexDirection: 'column', gap: 3 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: colors.textFaint }}>{b.k}</span>
              <span style={{ fontSize: 15, fontWeight: 700, color: colors.text }}>{b.v}</span>
            </div>
          ))}
        </div>
      </div>

      <div style={{ background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 16, padding: '15px 16px', display: 'flex', flexDirection: 'column', gap: 9 }}>
        <span style={{ fontSize: 14.5, fontWeight: 700 }}>백업 파일 내려받기</span>
        <span style={{ fontSize: 13.5, lineHeight: '21px', color: colors.textSub }}>
          JSON이라는 형식의 파일 한 개로 받습니다. 그대로 두셨다가 필요할 때 저희에게 주시면 됩니다.
        </span>
        <button onClick={actions.exportData} style={{ height: 52, borderRadius: 12, border: 0, background: colors.primary, color: '#fff', fontSize: 16, fontWeight: 700, cursor: 'pointer', boxShadow: '0 6px 12px rgba(22,160,107,.32)' }}>
          백업 파일 내려받기
        </button>
        {/* 되지 않는 '불러오기' 버튼은 두지 않는다. 눌렀는데 아무 일도 안 일어나면
            사장님은 백업이 안 된 줄 안다. 준비되면 그때 버튼을 만든다. */}
        <span style={{ fontSize: 12.5, lineHeight: '19px', color: colors.textFaint }}>
          백업 파일을 다시 넣는 기능은 아직 준비 중이에요.
        </span>
      </div>

      {state.backupNote && (
        <div role="status" style={{
          fontSize: 13.5, lineHeight: '20px', padding: '13px 14px', borderRadius: 12,
          background: state.backupErr ? colors.warnBg : colors.onboardBg,
          border: `1px solid ${state.backupErr ? colors.warnBorder : colors.onboardBorder}`,
          color: state.backupErr ? colors.warnText : colors.primarySoftText,
          fontWeight: 600
        }}>
          {state.backupNote}
        </div>
      )}
    </div>
  );
}
