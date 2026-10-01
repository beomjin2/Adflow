import { useState } from 'react';
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

      <ResetAllCard onReset={actions.resetAll} />
    </div>
  );
}

/** 전부 지우고 처음부터. 되돌릴 수 없으니 팝업으로 한 번 더 묻는다(보관함의 삭제와 같은 모양).
 *  백업 카드 **아래**에 둔다 — 지우기 전에 백업부터 받으라는 순서가 화면 순서와 같아야 한다. */
function ResetAllCard({ onReset }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    const ok = await onReset();
    // 성공하면 페이지가 새로고침되므로 여기 안 온다. 실패했을 때만 버튼을 다시 열어 준다.
    if (!ok) { setBusy(false); setOpen(false); }
  };

  return (
    <div style={{ background: '#fff', border: `1px solid ${colors.warnBorder}`, borderRadius: 16, padding: '15px 16px', display: 'flex', flexDirection: 'column', gap: 9 }}>
      <span style={{ fontSize: 14.5, fontWeight: 700 }}>처음 상태로 초기화</span>
      <span style={{ fontSize: 13.5, lineHeight: '21px', color: colors.textSub }}>
        가게 정보 · 캐릭터 · 광고 설정 · 광고 대화 · 생산 기록 · 보관한 광고를 전부 지우고 처음 쓰는 상태로 돌아갑니다.
        마스코트 보관소와 트렌드 밈은 남아요. 지우기 전에 위에서 백업 파일을 받아두세요.
      </span>
      <button onClick={() => setOpen(true)} disabled={busy}
        style={{ height: 52, borderRadius: 12, border: `1.5px solid ${colors.warnAccent}`, background: '#fff', color: colors.warnText, fontSize: 16, fontWeight: 700, cursor: busy ? 'default' : 'pointer', opacity: busy ? .6 : 1 }}>
        처음 상태로 초기화
      </button>

      {open && (
        <div
          onClick={(e) => { if (e.target === e.currentTarget && !busy) setOpen(false); }}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(15,17,19,.42)', zIndex: 100,
            display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
          }}
        >
          <div style={{
            width: '100%', maxWidth: 340, background: '#fff', borderRadius: 18, padding: 22,
            display: 'flex', flexDirection: 'column', gap: 14, animation: 'pop .18s ease',
            boxShadow: '0 20px 50px rgba(0,0,0,.22)',
          }}>
            <span style={{ fontSize: 16, fontWeight: 700 }}>전부 지우고 처음부터 할까요?</span>
            <span style={{ fontSize: 13, lineHeight: '19px', color: colors.textSub }}>
              가게 정보 · 캐릭터 · 광고 대화 · 생산 기록 · 보관한 광고가 사라지고 되돌릴 수 없어요.
              백업 파일을 아직 안 받았다면 취소하고 먼저 받아두세요.
            </span>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={run} disabled={busy}
                style={{ flex: 1, height: 46, borderRadius: 11, border: 0, background: colors.warnAccent, color: '#fff', fontSize: 14, fontWeight: 700, cursor: busy ? 'default' : 'pointer', opacity: busy ? .7 : 1 }}>
                {busy ? '지우는 중…' : '지우고 처음부터'}
              </button>
              <button onClick={() => setOpen(false)} disabled={busy}
                style={{ flex: 'none', height: 46, padding: '0 16px', borderRadius: 11, border: `1.5px solid ${colors.inputBorder}`, background: '#fff', color: colors.text, fontSize: 14, fontWeight: 700, cursor: 'pointer' }}>
                취소
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
