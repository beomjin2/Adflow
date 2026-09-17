import { colors } from '../theme.js';
import { PrimaryButton, SecondaryButton, SoftButton } from '../components/ui/Button.jsx';
import { buildAdText, adTextForClipboard, characterImage } from '../lib/adText.js';
import ComicPanels from '../components/ComicPanels.jsx';

export default function Result({ state, actions }) {
  const { headline, lines, info, tags, empty } = buildAdText(state);
  const charImg = characterImage(state);

  const copy = async () => {
    const text = adTextForClipboard(state);
    if (!text) { actions.toast('복사할 문구가 없어요'); return; }
    try {
      await navigator.clipboard.writeText(text);
      actions.toast('문구를 복사했어요 — 인스타에 붙여 넣으세요');
    } catch {
      // https가 아니거나 브라우저가 막으면 클립보드를 못 쓴다. 그럴 땐 직접 고르시게 안내한다.
      actions.toast('복사가 안 돼요 — 아래 문구를 길게 눌러 직접 복사해주세요');
    }
  };

  if (empty) {
    return (
      <div style={{ padding: 40, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}>
        <span style={{ fontSize: 15, color: colors.textFaint, textAlign: 'center', lineHeight: '23px' }}>
          아직 정해진 내용이 없어요.<br />대화로 알리고 싶은 내용을 먼저 정해주세요.
        </span>
        <SecondaryButton onClick={actions.backToSb} style={{ minWidth: 200 }}>대화로 돌아가기</SecondaryButton>
      </div>
    );
  }

  return (
    <div style={{ padding: 22, display: 'flex', gap: 18, flexWrap: 'wrap', alignItems: 'flex-start' }}>
      {/* 컷 구성 — 사장님이 정한 문장 그대로. 네컷 그림은 스토리보드에서 "네컷 그리기"를 눌렀을 때만 생긴다. */}
      <div style={{ flex: '1 1 340px', minWidth: 0, border: `1px solid ${colors.cardBorder}`, borderRadius: 18, background: '#fff', overflow: 'hidden' }}>
        <div style={{ padding: '14px 16px', borderBottom: `1px solid ${colors.cardBorder}`, display: 'flex', alignItems: 'center', gap: 10 }}>
          {charImg && (
            <img src={charImg} alt={state.charName || '가게 캐릭터'} style={{
              width: 44, height: 44, borderRadius: 11, objectFit: 'cover', flex: 'none',
              border: `1px solid ${colors.cardBorder}`,
            }} />
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
            <span style={{ fontSize: 14, fontWeight: 700 }}>{state.charName || '우리 가게'}</span>
            <span style={{ fontSize: 12, color: colors.textFaint, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {state.adType || '광고'}{state.adConcept ? ` · ${state.adConcept}` : ''}
            </span>
          </div>
        </div>
        {(state.comicCuts || []).some((c) => c.status !== 'empty') && (
          <div style={{ padding: '12px 12px 0' }}>
            <ComicPanels cuts={state.comicCuts || []} eta={state.sbEta} onReroll={actions.rerollCut} />
          </div>
        )}
        <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
          {state.plan.map((c) => (
            <div key={c.n} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
              <span style={{
                fontSize: 12, fontWeight: 800, color: colors.primarySoftText, background: colors.primarySoft,
                borderRadius: 7, padding: '4px 8px', flex: 'none',
              }}>{c.n}컷</span>
              <span style={{ fontSize: 15, lineHeight: '23px', color: colors.text }}>{c.line}</span>
            </div>
          ))}
        </div>
      </div>

      <div style={{ flex: '1 1 280px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ background: colors.bg, borderRadius: 16, padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: colors.textFaint, letterSpacing: .4 }}>올릴 문구</span>
          {headline && (
            <span style={{ fontSize: 18, fontWeight: 700, letterSpacing: -.3, lineHeight: '27px' }}>{headline}</span>
          )}
          {lines.length > 1 && (
            <span style={{ fontSize: 15, lineHeight: '23px', color: colors.textSub, whiteSpace: 'pre-line' }}>
              {lines.slice(1).join('\n')}
            </span>
          )}
          {info && <span style={{ fontSize: 14, lineHeight: '21px', color: colors.textSub }}>{info}</span>}
          {tags.length > 0 && (
            <span style={{ fontSize: 14, fontWeight: 600, color: colors.primarySoftText }}>{tags.join(' ')}</span>
          )}
        </div>

        <SoftButton onClick={copy} style={{ height: 48, fontSize: 15 }}>문구 복사하기</SoftButton>
        <SecondaryButton onClick={actions.backToSb} style={{ height: 52, fontSize: 16 }}>대화로 돌아가 고치기</SecondaryButton>
        <PrimaryButton onClick={actions.confirmResult}>이대로 저장</PrimaryButton>
      </div>
    </div>
  );
}
