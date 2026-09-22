import { useEffect, useState } from 'react';
import { colors } from '../../theme.js';
import ImageSlot, { formatEta } from '../ImageSlot.jsx';
import Lightbox from '../Lightbox.jsx';
import ComicPanels from '../ComicPanels.jsx';
import { situationLabel } from '../../lib/situationLabel.js';


/** 말풍선. 모양은 styles.css 의 `.ad-msg` 가 정한다 — 개선안에서 캐릭터 대화와
 *  광고 대화가 같은 모양이라 두 화면이 이 한 클래스를 같이 쓴다. */
export function TextBubble({ role, text }) {
  return <div className={`ad-msg ${role === 'me' ? 'me' : 'ai'}`}>{text}</div>;
}

export function CandidatesBubble({ items, selected, onSelect, onReroll, eta = 0 }) {
  // 크게 보고 있는 후보의 번호. -1이면 팝업이 닫혀 있다.
  const [preview, setPreview] = useState(-1);

  const drawing = items.filter((c) => c.status === 'generating').length;
  const failed = items.filter((c) => c.status === 'failed').length;
  const done = items.filter((c) => c.status === 'done').length;

  return (
    <div style={bubbleCardStyle}>
      <span style={bubbleTitleStyle}>
        {drawing > 0
          ? `그림을 그리고 있어요 — ${drawing}장 남았어요`
          : done > 0
            ? '후보가 나왔어요 — 눌러서 크게 보고 고르세요'
            : '아직 그림이 없어요'}
      </span>
      {drawing > 0 && eta > 0 && (
        <span style={hintStyle}>약 {formatEta(eta)}. 이 화면을 닫아도 계속 그려요.</span>
      )}
      <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap' }}>
        {items.map((c, i) => (
          <ImageSlot
            key={i} slot={c} size={96} eta={eta}
            selectable selected={selected === i}
            onClick={() => setPreview(i)} onReroll={() => onReroll(i)}
          />
        ))}
      </div>
      {failed > 0 && (
        <span style={{ ...hintStyle, color: colors.warnText }}>
          {failed}장은 그리지 못했어요. ↻ 를 누르면 그 자리만 다시 그려요.
        </span>
      )}
      {done > 0 && drawing === 0 && (
        <span style={hintStyle}>↻ 는 설정을 그대로 두고 그림만 다시 뽑아요. 고치고 싶은 점은 그냥 말해주세요.</span>
      )}

      {/* 그림을 누르면 여기서 크게 본다. 고르는 건 팝업 안의 '선택하기' 버튼이 한다 —
          누르는 것과 정하는 것은 다른 일이다. */}
      <Lightbox
        items={items} index={preview} selected={selected}
        onClose={() => setPreview(-1)} onMove={setPreview} onSelect={onSelect}
      />
    </div>
  );
}

/** 네컷 그림 — 대화 안에서 **말풍선까지 얹어** 보여준다.
 *
 *  전에는 작은 칸 넉 장(ImageSlot)만 놓았다. 그림은 보이는데 대사가 안 보여서,
 *  사장님은 광고가 어떻게 나올지 확인하려면 결과 화면까지 가야 했다. 지금은 여기서
 *  바로 완성된 모양을 본다 — 결과 화면·저장본과 같은 말풍선이다.
 *
 *  ComicPanels 를 그대로 쓴다. 대화창 폭에 맞춰 줄어들고, 더블클릭하면 한 컷을
 *  크게 본다. 컷마다 ↻ 로 그 칸만 다시 그릴 수 있다. */
export function ComicBubble({ cuts, eta = 0, onReroll }) {
  const items = cuts || [];
  if (!items.length) return null;

  const drawing = items.filter((c) => c.status === 'generating').length;
  const failed = items.filter((c) => c.status === 'failed').length;
  const done = items.filter((c) => c.status === 'done' && c.image).length;

  return (
    <div style={bubbleCardStyle}>
      <span style={bubbleTitleStyle}>
        {drawing > 0
          ? `네컷을 그리는 중 — ${drawing}컷 남았어요`
          : done > 0
            ? '네컷이 나왔어요 — 더블클릭하면 크게 보여요'
            : '아직 그림이 없어요'}
      </span>
      {drawing > 0 && eta > 0 && (
        <span style={hintStyle}>약 {formatEta(eta)}. 이 화면을 닫아도 계속 그려요.</span>
      )}
      <ComicPanels cuts={items} eta={eta} onReroll={onReroll} gap={6} />
      {failed > 0 && (
        <span style={{ ...hintStyle, color: colors.warnText }}>
          {failed}컷은 그리지 못했어요. ↻ 를 누르면 그 자리만 다시 그려요.
        </span>
      )}
      {done > 0 && drawing === 0 && (
        <span style={hintStyle}>마음에 안 드는 컷은 ↻ 로 그 칸만 다시 그릴 수 있어요.</span>
      )}
    </div>
  );
}

export function PlanBubble({ items }) {
  if (!items.length) return null;
  return (
    <div style={bubbleCardStyle}>
      <span style={bubbleTitleStyle}>지금까지 정해진 컷</span>
      {items.map((c) => (
        <div key={c.n} style={{ display: 'flex', gap: 9, alignItems: 'flex-start' }}>
          <span style={cutTagStyle}>{c.n}컷</span>
          <span style={{ fontSize: 14, lineHeight: '21px', color: colors.text }}>{c.line}</span>
        </div>
      ))}
      <span style={hintStyle}>고치고 싶은 컷을 말해주세요 — 그 자리에서 바로 반영돼요.</span>
    </div>
  );
}

export function ProdBubble({ prod, onChange }) {
  if (!prod) return null;
  const missing = !prod.soldOut;
  const fieldStyle = { height: 42, borderRadius: 9, border: `1.5px solid ${colors.inputBorder}`, background: '#fff', color: colors.text, fontSize: 16, padding: '0 10px', minWidth: 0 };
  return (
    <div style={bubbleCardStyle}>
      <span style={bubbleTitleStyle}>생산 기록을 남겼어요 — 여기서 바로 고칠 수 있어요</span>
      <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap' }}>
        <Field label="품목"><DraftField value={prod.name} onCommit={v => onChange({ name: v })} style={{ ...fieldStyle, flex: '2 1 150px' }} /></Field>
        <Field label="수량(개)">
          <DraftField value={prod.qty} onCommit={v => onChange({ qty: v })} sanitize={v => v.replace(/[^0-9]/g, '')}
            inputMode="numeric" style={{ ...fieldStyle, flex: '1 1 92px' }} />
        </Field>
        <Field label="생산 날짜"><input type="date" value={prod.date} onChange={e => onChange({ date: e.target.value })} style={{ ...fieldStyle, flex: '1 1 150px' }} /></Field>
        <Field label="생산 시각"><input type="time" value={prod.time} onChange={e => onChange({ time: e.target.value })} style={{ ...fieldStyle, flex: '1 1 118px' }} /></Field>
        <Field label="매진 시각"><input type="time" value={prod.soldOut} onChange={e => onChange({ soldOut: e.target.value })} style={{ ...fieldStyle, flex: '1 1 118px', borderColor: missing ? '#E0BE74' : colors.inputBorder }} /></Field>
      </div>
      <span style={{ fontSize: 12.5, fontWeight: 700, color: missing ? colors.warnText2 : colors.primary }}>
        {missing ? '매진 시각을 적어두면 다음 광고 시간을 잡아드려요' : `매진 ${prod.soldOut} 기록됨`}
      </span>
    </div>
  );
}

/** 타이핑마다 바로 onChange(→서버 PATCH)를 쏘면, 응답이 느릴 때 뒤늦게 도착한 이전
 *  글자의 응답이 입력값을 예전 상태로 덮어써 타이핑이 씹히는 것처럼 보인다(품목·수량 둘
 *  다 겪던 문제 — My/ProductionTab.jsx의 DraftInput과 같은 원인·같은 해법). 로컬에서만
 *  타이핑을 받고, 포커스를 벗어나거나 Enter를 눌렀을 때만 커밋한다. */
function DraftField({ value, onCommit, sanitize, style, ...props }) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);

  const commit = () => {
    if (draft === value) return;
    onCommit(draft);
  };

  return (
    <input
      value={draft}
      onChange={e => setDraft(sanitize ? sanitize(e.target.value) : e.target.value)}
      onBlur={commit}
      onKeyDown={e => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) e.target.blur(); }}
      style={style}
      {...props}
    />
  );
}

// 제안 종류마다 제목과 버튼 문구가 다르다. 키워드는 AI가 먼저 정해서 내놓는 것이라
// '바꾸기'가 아니라 '이대로 할게요'가 맞는 말이다.
const CONFIRM_COPY = {
  keywords: { title: '퍼스널 키워드 제안', yes: '이 키워드로 할게요', no: '직접 적을게요' },
  field: { title: '캐릭터 시트 수정', yes: '이대로 바꾸기', no: '그대로 두기' },
  plan: { title: '스토리 변경 제안', yes: '이대로 바꾸기', no: '그대로 두기' },
  meme: { title: '밈 추천', yes: '이 밈으로 바꾸기', no: '괜찮아요' },
  // 대화에서 "소금빵 50개 구웠어요" 같은 말이 나왔을 때. 스토리와 별개로 곁들여 뜬다.
  prod_add: { title: '생산 기록으로 남길까요?', yes: '남길게요', no: '안 남길래요' },
  // 가게 정보는 덮어쓰기라 '남길까요'가 아니라 '바꿀까요'다. diffs 가 before→after 를
  // 보여주고, basis 가 그렇게 읽은 근거(사장님 말 그대로)를 같이 보여준다.
  store_edit: { title: '가게 정보를 바꿀까요?', yes: '이렇게 바꾸기', no: '그대로 두기' },
};

/** 우리가 대신 정해준 값일 때, **무엇을 보고 정했는지**를 보여준다.
 *
 *  이게 없으면 사장님은 근거 없이 떨어진 값을 받는다 — 실제로 어느 가게든 같은
 *  캐릭터가 제안되던 시절엔 그게 "정해진 답을 띄운다"로 읽혔다. 인용한 말은
 *  백엔드가 가게 정보·시트 원문에 대고 맞춰 본 것만 내려온다(sheet_llm.evidence_from).
 *
 *  사장님이 직접 말한 수정에는 근거가 없다 — 그때는 이 블록이 통째로 안 나온다. */
function BasisBlock({ basis, why }) {
  const rows = basis || [];
  if (!rows.length && !why) return null;
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 6,
      background: colors.onboardBg, borderRadius: 10, padding: '9px 11px',
    }}>
      <span style={{ fontSize: 11.5, fontWeight: 800, color: colors.primarySoftText, letterSpacing: .3 }}>
        이걸 보고 정했어요
      </span>
      {rows.map((b, i) => (
        <div key={i} style={{ display: 'flex', gap: 7, alignItems: 'baseline', minWidth: 0 }}>
          <span style={{
            flex: 'none', fontSize: 11, fontWeight: 700, color: colors.textFaint,
            background: '#fff', borderRadius: 999, padding: '2px 7px',
          }}>{b.label}</span>
          <span style={{ flex: 1, minWidth: 0, fontSize: 12.5, lineHeight: '18px', color: colors.textSub }}>
            “{b.quote}”
          </span>
        </div>
      ))}
      {why && (
        <span style={{ fontSize: 12.5, lineHeight: '18px', color: colors.text }}>→ {why}</span>
      )}
    </div>
  );
}

export function ConfirmBubble({ pending, onConfirm, onDecline }) {
  if (!pending) return null;
  const open = pending.status === 'open';
  const { title, yes, no } = CONFIRM_COPY[pending.kind] || CONFIRM_COPY.plan;
  return (
    <div style={{ maxWidth: '96%', background: '#fff', border: `1.5px solid ${colors.onboardBorder}`, borderRadius: 14, padding: 13, display: 'flex', flexDirection: 'column', gap: 10, animation: 'pop .22s ease' }}>
      <span style={bubbleTitleStyle}>{title}</span>
      {(pending.diffs || []).map((d, i) => (
        <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 4, background: colors.bg, borderRadius: 10, padding: '9px 11px' }}>
          <span style={{ fontSize: 11.5, fontWeight: 800, color: colors.textFaint, letterSpacing: .3 }}>{d.label}</span>
          <span style={{ fontSize: 13, lineHeight: '19px', color: colors.textFaint, textDecoration: 'line-through' }}>{d.from}</span>
          <span style={{ fontSize: 14, lineHeight: '20px', color: colors.text, fontWeight: 600 }}>{d.to}</span>
        </div>
      ))}
      <BasisBlock basis={pending.basis} why={pending.why} />
      {open ? (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button onClick={onConfirm} style={{ flex: '1 1 160px', height: 48, borderRadius: 11, border: 0, background: colors.primary, color: '#fff', fontSize: 15, fontWeight: 700, cursor: 'pointer', boxShadow: '0 5px 10px rgba(22,160,107,.28)' }}>{yes}</button>
          <button onClick={onDecline} style={{ flex: '0 1 auto', height: 48, padding: '0 18px', borderRadius: 11, border: `1.5px solid ${colors.inputBorder}`, background: '#fff', color: colors.text, fontSize: 15, fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap' }}>{no}</button>
        </div>
      ) : (
        // superseded — 답을 안 한 사이에 같은 칸을 새로 정한 카드다. '바꾸지 않았어요'로
        // 묶어 두면 사장님이 거절한 것처럼 읽힌다. 거절한 적은 없고 지나갔을 뿐이다.
        <span style={{ fontSize: 12.5, fontWeight: 700, color: pending.status === 'applied' ? colors.primary : colors.textFaint }}>
          {pending.status === 'applied' ? '이 내용으로 바꿨어요'
            : pending.status === 'superseded' ? '이 제안 대신 아래에서 새로 정했어요'
            : '바꾸지 않았어요'}
        </span>
      )}
    </div>
  );
}

/** 고를 수 있는 스토리 제안 카드 묶음.
 *
 *  ConfirmBubble 은 "이대로 할까요?"라 예/아니오뿐이다. 여기는 서로 다른 스토리
 *  2~3개를 나란히 놓고 **고르게** 한다 — 사장님이 "뭐 만들까?"라고 했을 때
 *  막다른 길로 되돌려보내지 않으려고 만든 것이다.
 *
 *  하나를 고르면 백엔드가 같은 묶음의 나머지를 status:"closed"로 닫는다. 화면에서도
 *  버튼을 내려 다시 못 누르게 한다 — 스크롤을 올려 다른 걸 또 누르면 방금 정한
 *  구성이 조용히 덮어써지기 때문이다. */
export function OptionsBubble({ items, pending, onConfirm }) {
  const statusOf = (pid) => ((pending || {})[pid] || {}).status;
  const decided = (items || []).some((it) => statusOf(it.pid) !== 'open');

  return (
    <div style={{ maxWidth: '96%', display: 'flex', flexDirection: 'column', gap: 10, animation: 'pop .22s ease' }}>
      {(items || []).map((it) => {
        const status = statusOf(it.pid);
        const chosen = status === 'applied';
        return (
          <div key={it.pid} style={{
            background: '#fff',
            border: `1.5px solid ${chosen ? colors.primary : colors.onboardBorder}`,
            borderRadius: 14, padding: 13, display: 'flex', flexDirection: 'column', gap: 9,
            opacity: decided && !chosen ? 0.55 : 1,
          }}>
            <span style={bubbleTitleStyle}>{it.topic}</span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, background: colors.bg, borderRadius: 10, padding: '9px 11px' }}>
              {(it.cuts || []).map((c) => (
                <div key={c.n} style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
                  <span style={{ flex: 'none', fontSize: 11.5, fontWeight: 800, color: colors.textFaint, minWidth: 14 }}>{c.n}</span>
                  <span style={{ fontSize: 14, lineHeight: '20px', color: colors.text }}>{c.line}</span>
                </div>
              ))}
            </div>
            {status === 'open' && !decided ? (
              <button onClick={() => onConfirm(it.pid)} style={{
                height: 46, borderRadius: 11, border: 0, background: colors.primary, color: '#fff',
                fontSize: 15, fontWeight: 700, cursor: 'pointer', boxShadow: '0 5px 10px rgba(22,160,107,.28)',
              }}>이걸로 할게요</button>
            ) : (
              <span style={{ fontSize: 12.5, fontWeight: 700, color: chosen ? colors.primary : colors.textFaint }}>
                {chosen ? '이걸로 정했어요' : '이건 안 골랐어요'}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

/** 밈 추천 3개. 하나만 던지면 "이게 최선인가"를 확인할 길이 없어서 셋을 놓고 고르게 한다.
 *
 *  각 줄은 이름·상황·고른 이유만 짧게 보여주고, 누르면 팝업에서 **트렌드 화면과 같은
 *  원본**(유래·활용예시·출처·유행 시기)을 그대로 본다. 대화창에 유래를 통째로 펼치면
 *  스크롤이 대화를 덮어서, 짧게 보여주고 눌러서 깊이 보는 쪽으로 나눴다. */
export function MemeOptionsBubble({ items, pending, onConfirm }) {
  const [open, setOpen] = useState(null); // 팝업에 띄운 항목
  const statusOf = (pid) => ((pending || {})[pid] || {}).status;
  const decided = (items || []).some((it) => statusOf(it.pid) !== 'open');

  const Detail = ({ it, onClose }) => {
    const m = it.meme || {};
    const 기간 = [m.period_start, m.period_end].filter(Boolean).join(' ~ ');
    const rows = [
      ['유래', m.origin], ['활용 예시', m.usage_example], ['활용 상황', m.situation && situationLabel(m.situation)],
      ['유행 시기', 기간 || m.peak_date || m.published], ['출처', m.source_label],
    ].filter(([, v]) => String(v || '').trim());
    // 배경을 충분히 어둡게 하고 블러를 준다 — 뒤가 대화 기록이라 옅게 깔면
    // 팝업이 떠 있는지가 잘 안 보인다(Trend.jsx 의 POPUP_OVERLAY 와 같은 값).
    return (
      <div onClick={onClose} style={{
        position: 'fixed', inset: 0, background: 'rgba(15,17,19,.66)', zIndex: 60,
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 18,
        backdropFilter: 'blur(3px)', WebkitBackdropFilter: 'blur(3px)',
      }}>
        <div onClick={(e) => e.stopPropagation()} style={{
          background: '#fff', borderRadius: 16, padding: 20, maxWidth: 520, width: '100%',
          maxHeight: '82vh', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12,
          boxShadow: '0 24px 60px rgba(0,0,0,.34)', border: '1px solid rgba(0,0,0,.06)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 17, fontWeight: 800, color: colors.text }}>{m.name}</span>
            {m.situation && <span style={{ fontSize: 11.5, fontWeight: 700, color: colors.primarySoftText, background: colors.onboardBg, borderRadius: 999, padding: '3px 9px' }}>{situationLabel(m.situation)}</span>}
            <span style={{ flex: 1 }} />
            <button onClick={onClose} style={{ border: 0, background: 'none', fontSize: 20, cursor: 'pointer', color: colors.textFaint, lineHeight: 1 }}>×</button>
          </div>
          {m.image && <img src={m.image} alt={m.name} style={{ width: '100%', borderRadius: 10, objectFit: 'cover', maxHeight: 260 }} />}
          <div style={{ background: colors.onboardBg, borderRadius: 10, padding: '10px 12px' }}>
            <span style={{ fontSize: 11.5, fontWeight: 800, color: colors.primarySoftText }}>왜 골랐냐면</span>
            <div style={{ fontSize: 13.5, lineHeight: '20px', color: colors.text, marginTop: 4 }}>{it.reason}</div>
          </div>
          {rows.map(([label, value]) => (
            <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <span style={{ fontSize: 11.5, fontWeight: 800, color: colors.textFaint }}>{label}</span>
              <span style={{ fontSize: 13.5, lineHeight: '20px', color: colors.textSub, whiteSpace: 'pre-wrap' }}>{value}</span>
            </div>
          ))}
          {m.url && <a href={m.url} target="_blank" rel="noreferrer" style={{ fontSize: 12.5, color: colors.primary }}>원문 보기 ↗</a>}
          {statusOf(it.pid) === 'open' && !decided && (
            <button onClick={() => { onClose(); onConfirm(it.pid); }} style={{
              height: 48, borderRadius: 11, border: 0, background: colors.primary, color: '#fff',
              fontSize: 15, fontWeight: 700, cursor: 'pointer',
            }}>이 밈으로 할게요</button>
          )}
        </div>
      </div>
    );
  };

  return (
    <div style={{ maxWidth: '96%', display: 'flex', flexDirection: 'column', gap: 8, animation: 'pop .22s ease' }}>
      {(items || []).map((it) => {
        const m = it.meme || {};
        const status = statusOf(it.pid);
        const chosen = status === 'applied';
        return (
          <div key={it.pid} style={{
            background: '#fff', border: `1.5px solid ${chosen ? colors.primary : colors.onboardBorder}`,
            borderRadius: 13, padding: 12, display: 'flex', flexDirection: 'column', gap: 8,
            opacity: decided && !chosen ? 0.55 : 1,
          }}>
            <button onClick={() => setOpen(it)} style={{
              border: 0, background: 'none', padding: 0, textAlign: 'left', cursor: 'pointer',
              display: 'flex', flexDirection: 'column', gap: 5,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 14.5, fontWeight: 800, color: colors.text }}>{m.name}</span>
                {m.situation && <span style={{ fontSize: 11, fontWeight: 700, color: colors.primarySoftText, background: colors.onboardBg, borderRadius: 999, padding: '2px 8px' }}>{situationLabel(m.situation)}</span>}
                <span style={{ fontSize: 11.5, color: colors.textFaint }}>눌러서 자세히 ›</span>
              </div>
              <span style={{ fontSize: 13, lineHeight: '19px', color: colors.textSub }}>{it.reason}</span>
            </button>
            {status === 'open' && !decided ? (
              <button onClick={() => onConfirm(it.pid)} style={{
                height: 42, borderRadius: 10, border: 0, background: colors.primary, color: '#fff',
                fontSize: 14, fontWeight: 700, cursor: 'pointer',
              }}>이 밈으로 할게요</button>
            ) : (
              <span style={{ fontSize: 12.5, fontWeight: 700, color: chosen ? colors.primary : colors.textFaint }}>
                {chosen ? '이 밈으로 정했어요' : '이건 안 골랐어요'}
              </span>
            )}
          </div>
        );
      })}
      {open && <Detail it={open} onClose={() => setOpen(null)} />}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
      <span style={{ fontSize: 12, fontWeight: 700, color: colors.textFaint }}>{label}</span>
      {children}
    </div>
  );
}

const bubbleCardStyle = { maxWidth: '96%', background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 14, padding: 13, display: 'flex', flexDirection: 'column', gap: 9, animation: 'pop .22s ease' };
const bubbleTitleStyle = { fontSize: 14, fontWeight: 700 };
const hintStyle = { fontSize: 12.5, color: colors.textFaint, lineHeight: '18px' };
const cutTagStyle = { fontSize: 12, fontWeight: 700, color: colors.primarySoftText, background: colors.primarySoft, borderRadius: 6, padding: '3px 7px', flex: 'none' };
