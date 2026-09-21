import { colors } from '../theme.js';
import { PrimaryButton, SecondaryButton, SoftButton } from '../components/ui/Button.jsx';
import { buildAdText, adTextForClipboard, characterImage } from '../lib/adText.js';

export default function Save({ state, actions }) {
  const { headline, lines, info, tags } = buildAdText(state);
  const charImg = characterImage(state);
  const saved = state.savedThisAd;

  /** navigator.clipboard(HTTPS·localhost 같은 보안 컨텍스트에서만 있음)가 없거나 실패했을 때
   *  쓰는 구식 폴백 — 임시 textarea에 넣고 선택한 뒤 execCommand('copy')로 복사한다.
   *  지금 이 서비스가 HTTP로 떠 있어서 navigator.clipboard 자체가 없는 경우가 많다. */
  const copyFallback = (text) => {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    // 화면 밖으로 보내되 display:none은 안 된다 — 그러면 select()가 아무것도 못 고른다.
    textarea.style.position = 'fixed';
    textarea.style.top = '-1000px';
    textarea.style.left = '-1000px';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    let ok = false;
    try {
      ok = document.execCommand('copy');
    } catch {
      ok = false;
    }
    document.body.removeChild(textarea);
    return ok;
  };

  const copy = async () => {
    const text = adTextForClipboard(state);
    if (!text) { actions.toast('복사할 문구가 없어요'); return; }

    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        actions.toast('문구를 복사했어요');
        return;
      } catch {
        // 아래 폴백으로 넘어간다.
      }
    }

    if (copyFallback(text)) {
      actions.toast('문구를 복사했어요');
    } else {
      actions.toast('복사가 안 돼요 — 위 문구를 길게 눌러 직접 복사해주세요');
    }
  };

  return (
    <div style={{ padding: '26px 22px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}>
      <div style={{ width: 340, maxWidth: '100%', border: `1px solid ${colors.cardBorder}`, borderRadius: 16, overflow: 'hidden', background: '#fff' }}>
        {charImg && (
          <img src={charImg} alt={state.charName || '가게 캐릭터'} style={{
            width: '100%', aspectRatio: '1/1', objectFit: 'cover', display: 'block',
            borderBottom: `1px solid ${colors.cardBorder}`,
          }} />
        )}
        <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 7 }}>
          {headline && <span style={{ fontSize: 15.5, fontWeight: 700, lineHeight: '23px' }}>{headline}</span>}
          {lines.length > 1 && (
            <span style={{ fontSize: 13.5, color: colors.textSub, lineHeight: '20px', whiteSpace: 'pre-line' }}>
              {lines.slice(1).join('\n')}
            </span>
          )}
          {info && <span style={{ fontSize: 13, color: colors.textSub, lineHeight: '20px' }}>{info}</span>}
          {tags.length > 0 && (
            <span style={{ fontSize: 13, fontWeight: 600, color: colors.primarySoftText }}>{tags.join(' ')}</span>
          )}
        </div>
      </div>

      <span style={{ fontSize: 14, color: colors.textSub, textAlign: 'center', maxWidth: 440, lineHeight: '22px' }}>
        {saved
          ? '보관함에 저장했어요. 내 정보 → 히스토리에서 다시 꺼내 볼 수 있어요.'
          : '‘보관함에 저장’을 누르면 이 내용이 남아, 나중에 다시 꺼내 쓸 수 있어요.'}
      </span>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, width: 340, maxWidth: '100%' }}>
        <PrimaryButton onClick={actions.download} disabled={saved}>{saved ? '보관함에 저장했어요' : '보관함에 저장'}</PrimaryButton>
        <SoftButton onClick={copy} style={{ height: 48, fontSize: 15 }}>문구 복사하기</SoftButton>
        <SecondaryButton onClick={actions.goHome}>홈으로</SecondaryButton>
      </div>
    </div>
  );
}
