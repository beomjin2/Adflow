import { colors } from '../theme.js';

/** 그림 한 칸. 상태는 서버가 준 것 그대로 네 가지다 —
 *  empty(아직 없음) · generating(그리는 중) · done(그림 있음) · failed(실패).
 *
 *  예전엔 그림이 없으면 색 그라디언트를 깔았다. 사장님은 그걸 자기 캐릭터라고 생각하고
 *  "이거 왜 이래요"라고 물었다. 없으면 없다고, 그리는 중이면 얼마나 남았는지 적는다. */
export default function ImageSlot({
  slot, size = 92, selected = false, selectable = false,
  onClick, onReroll, rerollTitle = '같은 설정으로 다시 그리기',
  eta = 0, showLabel = true,
}) {
  const status = slot?.status || 'empty';
  const image = slot?.image || null;
  const label = slot?.label || '';

  const border = selected
    ? `2.5px solid ${colors.primary}`
    : status === 'failed'
      ? `1.5px solid ${colors.warnBorder}`
      : `1px solid ${colors.cardBorder}`;

  const base = {
    position: 'relative', width: size, height: size, borderRadius: 12,
    border, overflow: 'hidden', background: status === 'failed' ? colors.warnBg : colors.bg,
    display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
    gap: 4, padding: 6, textAlign: 'center', flex: 'none',
  };

  const clickable = selectable && status === 'done';
  const Tag = clickable ? 'button' : 'div';

  return (
    <div style={{ position: 'relative', flex: 'none' }}>
      <Tag
        onClick={clickable ? onClick : undefined}
        title={clickable ? '이 그림으로 정하기' : undefined}
        style={{ ...base, cursor: clickable ? 'pointer' : 'default', font: 'inherit', color: colors.text }}
      >
        {status === 'done' && image && (
          <img src={image} alt={label || '생성된 그림'} loading="lazy" style={{
            position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover',
          }} />
        )}

        {status === 'generating' && (
          <>
            <Spinner />
            <span style={{ fontSize: 10.5, fontWeight: 700, color: colors.textSub, lineHeight: '14px' }}>
              그리는 중
            </span>
            {eta > 0 && (
              <span style={{ fontSize: 10, color: colors.textFaint, lineHeight: '13px' }}>
                약 {formatEta(eta)}
              </span>
            )}
          </>
        )}

        {status === 'failed' && (
          <span style={{ fontSize: 10.5, fontWeight: 700, color: colors.warnText, lineHeight: '15px' }}>
            그리지 못했어요
          </span>
        )}

        {status === 'empty' && (
          <span style={{ fontSize: 10.5, color: colors.textFaint, lineHeight: '15px' }}>
            아직 없어요
          </span>
        )}

        {showLabel && label && status === 'done' && (
          <span style={{
            position: 'absolute', left: 6, bottom: 6, fontSize: 10.5, fontWeight: 700,
            color: colors.text, background: 'rgba(255,255,255,.88)', borderRadius: 6, padding: '2px 6px',
          }}>{label}</span>
        )}

        {selected && status === 'done' && (
          <span style={{
            position: 'absolute', left: 6, top: 6, fontSize: 10.5, fontWeight: 800,
            color: '#fff', background: colors.primary, borderRadius: 999, padding: '2px 8px',
          }}>선택함</span>
        )}
      </Tag>

      {onReroll && status !== 'generating' && (
        <button
          onClick={onReroll}
          title={status === 'failed' ? '다시 시도' : rerollTitle}
          style={{
            position: 'absolute', top: 5, right: 5, width: 28, height: 28, borderRadius: 9,
            border: 0, background: 'rgba(255,255,255,.95)', color: colors.text,
            fontSize: 14, cursor: 'pointer', boxShadow: '0 1px 4px rgba(0,0,0,.16)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >↻</button>
      )}
    </div>
  );
}

/** "약 1분 30초" 처럼 읽어서 바로 아는 형태로. 초만 쓰면 '95초'가 얼마인지 감이 안 온다. */
export function formatEta(seconds) {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s}초 남았어요`;
  const m = Math.floor(s / 60);
  const rest = s % 60;
  return rest ? `${m}분 ${rest}초 남았어요` : `${m}분 남았어요`;
}

function Spinner() {
  return (
    <span style={{
      width: 18, height: 18, borderRadius: '50%',
      border: `2.5px solid ${colors.cardBorder}`, borderTopColor: colors.primary,
      animation: 'spin .8s linear infinite', display: 'inline-block',
    }} />
  );
}
