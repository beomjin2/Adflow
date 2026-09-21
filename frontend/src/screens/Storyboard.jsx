import { colors } from '../theme.js';
import { Select, TextInput, TextArea } from '../components/ui/Field.jsx';
import { PrimaryButton, SecondaryButton, SoftButton } from '../components/ui/Button.jsx';
import ChatPanel from '../components/ChatPanel.jsx';

const EMPTY_HINT = `오늘 무엇을 알리고 싶으신가요?
편하게 말씀해주시면 컷으로 나눠 드려요.

예) 오늘 소금빵 30개 구웠어요
예) 이번 주말에 새 메뉴를 내요`;

/** 접었다 펴는 줄. 설정과 생산 기록은 광고를 만드는 동안 늘 펼쳐둘 내용이 아니라
 *  "지금 뭐로 되어 있더라" 하고 한 번 확인하는 것이라 접어 둔다. */
function Accordion({ open, onToggle, label, badge, badgeTone = 'soft', first, children }) {
  const tone = {
    soft: { background: colors.softBg, color: colors.textSub },
    green: { background: colors.primarySoft, color: colors.primarySoftText },
    warn: { background: colors.warnBg, color: colors.warnText, border: `1px solid ${colors.warnBorder}` },
  }[badgeTone];

  return (
    <div style={{ borderTop: first ? 0 : `1px solid ${colors.cardBorder}` }}>
      <button onClick={onToggle} aria-expanded={open} style={{
        width: '100%', display: 'flex', alignItems: 'center', gap: 10, background: 'transparent',
        border: 0, cursor: 'pointer', padding: '14px 0', textAlign: 'left', minHeight: 48,
      }}>
        <span style={{ fontSize: 15, fontWeight: 700, color: colors.text, flex: 'none' }}>{label}</span>
        {badge && (
          <span style={{
            display: 'inline-flex', alignItems: 'center', height: 26, padding: '0 10px',
            borderRadius: 999, fontSize: 12.5, fontWeight: 700, whiteSpace: 'nowrap', ...tone,
          }}>{badge}</span>
        )}
        <span style={{ flex: 1 }} />
        <span style={{
          fontSize: 14, color: colors.textFaint, transition: 'transform .18s ease',
          display: 'inline-block', transform: `rotate(${open ? 180 : 0}deg)`,
        }}>⌄</span>
      </button>
      {open && (
        <div style={{ padding: '0 0 14px', display: 'flex', flexDirection: 'column', gap: 10, animation: 'pop .18s ease' }}>
          {children}
        </div>
      )}
    </div>
  );
}

export default function Storyboard({ state, actions }) {
  const missingProds = state.prods.filter(p => !p.soldOut);
  const sbSummary = [state.adType, state.adConcept, state.charName].filter(Boolean).join(' · ') || '아직 안 정함';
  const selectedMemeCard = (state.memes || []).find(m => String(m.id) === String(state.memeId));
  const memeCard = selectedMemeCard?.card || {};
  // 트렌드 확인 화면에서 밈을 고르고 왔으면 applyAd()가, "밈 고르기"에서 카드를 골랐으면
  // pickMemeCard()가 이 칸들을 채운다 — 어느 쪽이든 채워져 있으면 접힌 채로 두지 않는다.
  const memeDraftFilled = !!(state.memeTitle || state.memeText);

  return (
    <div style={{ padding: '18px 20px 20px', display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'stretch' }}>
      <div style={{ flex: '1 1 260px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ ...card, padding: '4px 18px' }}>
          <Accordion first open={state.sbSetOpen} onToggle={actions.toggleSbSet} label="광고 설정" badge={sbSummary}>
            <span style={hintStyle}>종류와 느낌을 바꾸려면 이전 화면으로 돌아가세요.</span>
            <SecondaryButton onClick={actions.goAd} style={{ ...smallButton, alignSelf: 'flex-start' }}>
              설정 바꾸기
            </SecondaryButton>
          </Accordion>

          <Accordion
            open={state.sbProdOpen} onToggle={actions.toggleSbProd} label="최근 생산 기록"
            badgeTone={missingProds.length ? 'warn' : 'soft'}
            badge={state.prods.length === 0
              ? '없음'
              : missingProds.length ? `${state.prods.length}건 · 매진 미입력 ${missingProds.length}` : `${state.prods.length}건`}
          >
            {state.prods.length === 0 && (
              <span style={hintStyle}>
                아직 기록이 없어요 — 대화에서 “오늘 소금빵 20개 만들었어요”처럼 말하면 자동으로 남아요.
              </span>
            )}
            {state.prods.slice(0, 3).map(p => (
              <div key={p.id} style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', fontSize: 14 }}>
                <b style={{ color: colors.text }}>{p.name}</b>
                <span style={{ color: colors.textSub }}>{p.qty ? `${p.qty} · ` : ''}{p.date} {p.time}</span>
                <span style={{ flex: 1 }} />
                {p.soldOut ? (
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', height: 26, padding: '0 10px', borderRadius: 999,
                    fontSize: 12.5, fontWeight: 700, background: colors.primarySoft, color: colors.primarySoftText,
                  }}>매진 {p.soldOut}</span>
                ) : (
                  <button onClick={actions.openProdTab} style={{
                    height: 30, padding: '0 11px', borderRadius: 999, cursor: 'pointer',
                    border: `1px solid ${colors.warnBorder}`, background: colors.warnBg,
                    color: colors.warnText, fontSize: 12.5, fontWeight: 700, whiteSpace: 'nowrap',
                  }}>매진 시각 입력</button>
                )}
              </div>
            ))}
          </Accordion>
        </div>

        <div style={{ ...card, padding: '14px 16px', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={sectionTitle}>밈으로 스토리 제안받기</span>
            <span style={{ flex: 1 }} />
            <button onClick={actions.goTrend} style={{ border: 0, background: 'transparent', padding: 0, fontSize: 11.5, fontWeight: 700, color: colors.primarySoftText, cursor: 'pointer' }}>
              트렌드에서 더 보기 ›
            </button>
          </div>
          <span style={hintStyle}>
            밈을 고르면 가게 정보로 4컷 초안을 만들어 대화창에 제안해요. 마음에 들면 거기서 "이대로 바꾸기".
          </span>

          <Select value={state.memeId || ''} onChange={e => actions.pickMemeCard(e.target.value)} disabled={!!state.trendSel}>
            <option value="">밈 고르기</option>
            {(state.memes || []).map(m => <option key={m.id} value={m.id}>{m.title}</option>)}
          </Select>
          {state.trendSel && (
            <span style={{ fontSize: 11.5, color: colors.textFaint }}>
              트렌드에서 고른 밈으로 카드를 만드는 중이라 다른 카드는 고를 수 없어요. 다른 밈을 쓰려면 트렌드 화면에서 다시 골라주세요.
            </span>
          )}

          {selectedMemeCard && (
            <div style={{ background: colors.softBg, borderRadius: 11, padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 7, animation: 'pop .18s ease' }}>
              {memeCard.definition && (
                <span style={{ fontSize: 12.5, lineHeight: '19px', color: colors.text }}>{memeCard.definition}</span>
              )}
              {memeCard.template && (
                <div style={{ display: 'flex', gap: 6, alignItems: 'baseline' }}>
                  <span style={{ fontSize: 10.5, fontWeight: 800, color: colors.textFaint, letterSpacing: .3, flex: 'none' }}>말 틀</span>
                  <span style={{ fontSize: 12.5, lineHeight: '18px', color: colors.textSub }}>{memeCard.template}</span>
                </div>
              )}
              {(memeCard.industries || []).length > 0 && (
                <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                  {memeCard.industries.map((ind) => (
                    <span key={ind} style={{ fontSize: 10.5, fontWeight: 700, color: colors.primarySoftText, background: colors.primarySoft, borderRadius: 999, padding: '3px 8px' }}>
                      {ind}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          <SoftButton onClick={actions.proposeStory} disabled={!state.memeId || state.sbThinking}
            style={{ height: 42, fontSize: 14, background: colors.primarySoft, color: colors.primarySoftText }}>
            {state.sbThinking ? '만드는 중…' : '스토리 제안받기'}
          </SoftButton>

          {/* 채워져 있으면(트렌드에서든, 밈 고르기에서든) 접힌 채로 숨어있지 않게 기본으로 펼쳐 둔다. */}
          <details open={memeDraftFilled} style={{ borderTop: `1px solid ${colors.cardBorder}`, paddingTop: 9 }}>
            <summary style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 700, color: colors.textSub, cursor: 'pointer' }}>
              <span style={{ color: colors.textFaint }}>＋</span>
              밈 카드 직접 추가 (원문 붙여넣기)
              {state.memeDraftFromTrend && (
                <span style={{ fontSize: 10, fontWeight: 700, color: colors.primarySoftText, background: colors.primarySoft, borderRadius: 999, padding: '2px 7px' }}>
                  트렌드에서 가져옴
                </span>
              )}
            </summary>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 7, marginTop: 8 }}>
              <TextInput value={state.memeTitle || ''} onChange={e => actions.set('memeTitle', e.target.value)} placeholder="밈 이름" style={{ height: 42, fontSize: 14 }} />
              <TextInput value={state.memeSource || ''} onChange={e => actions.set('memeSource', e.target.value)} placeholder="출처(사이트·링크)" style={{ height: 42, fontSize: 14 }} />
              <TextArea value={state.memeText || ''} onChange={e => actions.set('memeText', e.target.value)} placeholder="밈 원문 본문을 그대로 붙여넣기 (요약만으로는 카드가 안 나와요)" style={{ height: 90, fontSize: 14 }} />
              <SoftButton onClick={actions.addMeme} disabled={!(state.memeTitle || '').trim() || (state.memeText || '').trim().length < 40 || state.sbThinking} style={{ height: 38, fontSize: 13 }}>
                카드 만들기
              </SoftButton>
            </div>
          </details>
        </div>

        <div style={{ ...card, padding: '14px 16px', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={sectionTitle}>지금 정해진 내용</span>
            <span style={{ flex: 1 }} />
            <span style={{
              fontSize: 12.5, fontWeight: 700, borderRadius: 999, padding: '4px 10px',
              background: state.plan.length ? colors.primarySoft : colors.softBg,
              color: state.plan.length ? colors.primarySoftText : colors.textFaint,
            }}>
              {state.plan.length ? `${state.plan.length}컷` : '비어 있음'}
            </span>
          </div>

          {state.plan.length === 0 ? (
            <span style={hintStyle}>
              아직 비어 있어요 — 오른쪽 대화창에 하고 싶은 말을 적으면 컷으로 나눠 여기에 쌓여요.
            </span>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {state.plan.map((c, i) => (
                <div key={c.n} style={{
                  display: 'grid', gridTemplateColumns: '32px minmax(0, 1fr)', gap: 12, padding: '12px 0',
                  borderTop: i === 0 ? 0 : `1px solid ${colors.cardBorder}`,
                }}>
                  <span style={{
                    width: 32, height: 32, borderRadius: 10, background: colors.primarySoft,
                    color: colors.primarySoftText, display: 'inline-flex', alignItems: 'center',
                    justifyContent: 'center', fontWeight: 700, fontSize: 14,
                  }}>{c.n}</span>
                  <span style={{ fontSize: 14.5, lineHeight: '22px', color: colors.text }}>{c.line}</span>
                </div>
              ))}
            </div>
          )}

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <SoftButton
              onClick={actions.makeComic}
              disabled={!state.plan.length || !state.charConfirmed || state.sbGenerating}
              style={{ flex: '0 1 auto', fontSize: 15, background: colors.primarySoft, color: colors.primarySoftText }}
            >
              {!state.charConfirmed ? '캐릭터를 먼저 확정해주세요'
                : state.sbGenerating ? '그리는 중…'
                  : (state.comicCuts || []).length ? '네컷 다시 그리기' : '네컷 그리기'}
            </SoftButton>
            <PrimaryButton onClick={actions.openResult} disabled={!state.plan.length} style={{ flex: '1 1 160px' }}>
              {state.plan.length ? '이 내용으로 광고 만들기' : '대화로 내용을 먼저 정해주세요'}
            </PrimaryButton>
          </div>
        </div>
      </div>

      <ChatPanel
        title="무엇을 알리고 싶으세요? — AI와 대화"
        messages={state.sbMsgs}
        thinking={state.sbThinking}
        thinkingLabel="정리하는 중…"
        emptyHint={EMPTY_HINT}
        placeholder="오늘 알리고 싶은 내용을 적어주세요"
        input={state.sbInput}
        onInputChange={(v) => actions.set('sbInput', v)}
        onSend={actions.sendSb}
        plan={state.plan}
        comic={state.comicCuts}
        comicEta={state.sbEta}
        onRerollCut={actions.rerollCut}
        prods={state.prods}
        onPatchProd={actions.patchProd}
        pending={state.pending}
        onConfirm={actions.confirmPending}
        onDecline={actions.declinePending}
        height={470}
      />
    </div>
  );
}

const card = {
  flex: 'none', background: '#fff', border: `1px solid ${colors.cardBorder}`,
  borderRadius: 16, display: 'flex', flexDirection: 'column',
};
const sectionTitle = { fontSize: 15, fontWeight: 700, color: colors.text };
const hintStyle = { fontSize: 12.5, lineHeight: '19px', color: colors.textFaint };
const smallButton = { height: 40, padding: '0 14px', fontSize: 14, borderRadius: 10 };
