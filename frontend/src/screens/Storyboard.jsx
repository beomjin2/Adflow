import { colors } from '../theme.js';
import { Select } from '../components/ui/Field.jsx';
import { PrimaryButton, SoftButton } from '../components/ui/Button.jsx';
import { formatEta } from '../components/ImageSlot.jsx';
import ComicPanels from '../components/ComicPanels.jsx';
import ChatPanel from '../components/ChatPanel.jsx';

const AD_TYPES = ['인스타 게시물', '포스터', '메뉴판'];
const AD_CONCEPTS = ['유쾌함', '감성', '정보형', '담백함'];

const EMPTY_HINT = `오늘 무엇을 알리고 싶으신가요?
편하게 말씀해주시면 컷으로 나눠 드려요.

예) 오늘 소금빵 30개 구웠어요
예) 이번 주말에 새 메뉴를 내요`;

export default function Storyboard({ state, actions }) {
  const missingProds = state.prods.filter(p => !p.soldOut);
  const sbSummary = [state.adType, state.adConcept, state.charName].filter(Boolean).join(' · ') || '아직 안 정함';

  return (
    <div style={{ padding: '18px 20px 20px', display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'stretch' }}>
      <div style={{ flex: '1 1 230px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ border: `1px solid ${state.sbSetOpen ? colors.onboardBorder : colors.cardBorder}`, background: state.sbSetOpen ? colors.onboardBg : '#fff', borderRadius: 14, overflow: 'hidden' }}>
          <button onClick={actions.toggleSbSet} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, background: 'transparent', border: 0, cursor: 'pointer', padding: '14px', textAlign: 'left', minHeight: 48 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: colors.textSub, flex: 'none' }}>광고 설정</span>
            <span style={{ fontSize: 12, color: colors.textFaint, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{sbSummary}</span>
            <span style={{ flex: 1 }} />
            <span style={{ fontSize: 14, color: colors.textFaint, transition: 'transform .18s ease', display: 'inline-block', transform: `rotate(${state.sbSetOpen ? 180 : 0}deg)` }}>⌄</span>
          </button>
          {state.sbSetOpen && (
            <div style={{ padding: '0 14px 13px', display: 'flex', flexDirection: 'column', gap: 10, animation: 'pop .18s ease' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <span style={subLabelStyle}>광고 종류</span>
                <Select value={state.adType} onChange={e => actions.set('adType', e.target.value)} placeholder="골라주세요">
                  {AD_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </Select>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <span style={subLabelStyle}>광고 느낌</span>
                <Select value={state.adConcept} onChange={e => actions.set('adConcept', e.target.value)} placeholder="골라주세요">
                  {AD_CONCEPTS.map(c => <option key={c} value={c}>{c}</option>)}
                </Select>
              </div>
            </div>
          )}
        </div>

        <div style={{ border: `1px solid ${state.sbProdOpen ? colors.onboardBorder : colors.cardBorder}`, background: state.sbProdOpen ? colors.onboardBg : '#fff', borderRadius: 14, overflow: 'hidden' }}>
          <button onClick={actions.toggleSbProd} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, background: 'transparent', border: 0, cursor: 'pointer', padding: '14px', textAlign: 'left', minHeight: 48 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: colors.textSub }}>최근 생산 기록</span>
            <span style={{ fontSize: 12, fontWeight: 700, borderRadius: 999, padding: '3px 8px', background: missingProds.length ? colors.warnBg : colors.softBg, color: missingProds.length ? colors.warnText : colors.textSub }}>
              {state.prods.length === 0
                ? '없음'
                : missingProds.length ? `${state.prods.length}건 · 매진 미입력 ${missingProds.length}` : `${state.prods.length}건`}
            </span>
            <span style={{ flex: 1 }} />
            <span style={{ fontSize: 14, color: colors.textFaint, transition: 'transform .18s ease', display: 'inline-block', transform: `rotate(${state.sbProdOpen ? 180 : 0}deg)` }}>⌄</span>
          </button>
          {state.sbProdOpen && (
            <div style={{ padding: '0 14px 13px', display: 'flex', flexDirection: 'column', gap: 8, animation: 'pop .18s ease' }}>
              {state.prods.length === 0 && (
                <span style={{ fontSize: 12.5, lineHeight: '19px', color: colors.textFaint }}>
                  아직 기록이 없어요 — 대화에서 “오늘 소금빵 20개 만들었어요”처럼 말하면 자동으로 남아요.
                </span>
              )}
              {state.prods.slice(0, 2).map(p => {
                const missing = !p.soldOut;
                return (
                  <div key={p.id} style={{ display: 'flex', flexDirection: 'column', gap: 7, background: missing ? colors.warnBg : colors.bg, border: `1px solid ${missing ? colors.warnBorder : colors.cardBorder}`, borderRadius: 11, padding: '10px 11px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                      <input value={p.name} onChange={e => actions.patchProd(p.id, { name: e.target.value })} aria-label="품목" style={{ flex: 1, minWidth: 0, height: 40, borderRadius: 8, border: `1px solid ${colors.inputBorder}`, background: '#fff', color: colors.text, fontSize: 15, fontWeight: 600, padding: '0 8px' }} />
                      <span style={{ fontSize: 12.5, fontWeight: 700, color: colors.textFaint, flex: 'none' }}>{p.qty}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                      <span style={rowLabelStyle}>생산</span>
                      <input type="date" value={p.date} onChange={e => actions.patchProd(p.id, { date: e.target.value })} aria-label="생산 날짜" style={miniFieldStyle} />
                      <input type="time" value={p.time} onChange={e => actions.patchProd(p.id, { time: e.target.value })} aria-label="생산 시각" style={miniFieldStyle} />
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                      <span style={rowLabelStyle}>매진</span>
                      <input type="time" value={p.soldOut} onChange={e => actions.setSoldOut(p.id, e.target.value)} aria-label="매진 시각" style={{ ...miniFieldStyle, borderColor: missing ? '#E0BE74' : colors.inputBorder }} />
                    </div>
                    <span style={{ fontSize: 12.5, fontWeight: 700, color: missing ? colors.warnText2 : colors.primary }}>{missing ? '매진 시각 미입력' : `매진 ${p.soldOut} 기록됨`}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div style={{ background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 14, padding: '13px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: colors.textSub }}>밈으로 스토리 제안받기</span>
          <span style={{ fontSize: 12, lineHeight: '18px', color: colors.textFaint }}>
            밈을 고르면 가게 정보로 4컷 초안을 만들어 대화창에 제안해요. 마음에 들면 거기서 "이대로 바꾸기".
          </span>
          <Select value={state.memeId || ''} onChange={e => actions.set('memeId', e.target.value)}>
            <option value="">밈 고르기</option>
            {(state.memes || []).map(m => <option key={m.id} value={m.id}>{m.title}</option>)}
          </Select>
          {state.memeId && (state.memes || []).find(m => String(m.id) === String(state.memeId)) && (
            <span style={{ fontSize: 12, lineHeight: '18px', color: colors.textSub }}>
              말 틀: {(state.memes || []).find(m => String(m.id) === String(state.memeId)).card.template || '—'}
            </span>
          )}
          <SoftButton onClick={actions.proposeStory} disabled={!state.memeId || state.sbThinking}
            style={{ height: 42, fontSize: 14, background: colors.primarySoft, color: colors.primarySoftText }}>
            {state.sbThinking ? '만드는 중…' : '스토리 제안받기'}
          </SoftButton>
          <details>
            <summary style={{ fontSize: 12, color: colors.textFaint, cursor: 'pointer' }}>밈 카드 추가 (원문 붙여넣기)</summary>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 6 }}>
              <input value={state.memeTitle || ''} onChange={e => actions.set('memeTitle', e.target.value)} placeholder="밈 이름" style={miniFieldStyle} />
              <input value={state.memeSource || ''} onChange={e => actions.set('memeSource', e.target.value)} placeholder="출처(사이트·링크)" style={miniFieldStyle} />
              <textarea value={state.memeText || ''} onChange={e => actions.set('memeText', e.target.value)} placeholder="밈 원문 본문을 그대로 붙여넣기 (요약만으로는 카드가 안 나와요)" style={{ ...miniFieldStyle, height: 90, padding: 8, resize: 'vertical' }} />
              <SoftButton onClick={actions.addMeme} disabled={!(state.memeTitle || '').trim() || (state.memeText || '').trim().length < 40 || state.sbThinking} style={{ height: 38, fontSize: 13 }}>
                카드 만들기
              </SoftButton>
            </div>
          </details>
        </div>

        <div style={{ background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 14, padding: '13px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: colors.textSub }}>지금 정해진 내용</span>
            <span style={{ flex: 1 }} />
            <span style={{ fontSize: 11.5, fontWeight: 700, borderRadius: 999, padding: '3px 8px', background: state.plan.length ? colors.primarySoft : colors.softBg, color: state.plan.length ? colors.primarySoftText : colors.textFaint }}>
              {state.plan.length ? `${state.plan.length}컷` : '비어 있음'}
            </span>
          </div>
          {state.plan.length === 0 && (
            <span style={{ fontSize: 12.5, lineHeight: '19px', color: colors.textFaint }}>
              아직 비어 있어요 — 오른쪽 대화창에 하고 싶은 말을 적으면 컷으로 나눠 여기에 쌓여요.
            </span>
          )}
          {state.plan.map(c => (
            <div key={c.n} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
              <span style={{ fontSize: 11.5, fontWeight: 800, color: colors.primarySoftText, background: colors.primarySoft, borderRadius: 6, padding: '3px 6px', flex: 'none' }}>{c.n}컷</span>
              <span style={{ fontSize: 13.5, lineHeight: '20px', color: colors.text }}>{c.line}</span>
            </div>
          ))}
        </div>

        {(state.comicCuts || []).length > 0 && (
          <div style={{ background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 14, padding: '13px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: colors.textSub }}>
              {state.sbGenerating ? `네컷을 그리는 중 — 약 ${formatEta(state.sbEta)}` : '네컷 그림'}
            </span>
            {/* 여기선 작은 미리보기라 말풍선을 얹지 않는다 — 말풍선 달린 큰 네컷은 결과 화면. */}
            <ComicPanels cuts={state.comicCuts || []} eta={state.sbEta} onReroll={actions.rerollCut} bubbles={false} gap={6} />
          </div>
        )}
        <SoftButton
          onClick={actions.makeComic}
          disabled={!state.plan.length || !state.charConfirmed || state.sbGenerating}
          style={{ height: 46, fontSize: 15, background: colors.primarySoft, color: colors.primarySoftText }}
        >
          {!state.charConfirmed ? '캐릭터를 먼저 확정해주세요'
            : state.sbGenerating ? '그리는 중…'
              : (state.comicCuts || []).length ? '네컷 다시 그리기' : '네컷 그리기'}
        </SoftButton>

        <div style={{ flex: 1 }} />
        <PrimaryButton onClick={actions.openResult} disabled={!state.plan.length}>
          {state.plan.length ? '완성된 광고 보기' : '대화로 내용을 먼저 정해주세요'}
        </PrimaryButton>
      </div>

      <div style={{ flex: '2 1 430px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span style={{ fontSize: 14, fontWeight: 700, color: colors.textSub }}>무엇을 알리고 싶으세요? — AI와 대화</span>
        <ChatPanel
          messages={state.sbMsgs}
          thinking={state.sbThinking}
          thinkingLabel="정리하는 중…"
          emptyHint={EMPTY_HINT}
          placeholder="오늘 알리고 싶은 내용을 적어주세요"
          input={state.sbInput}
          onInputChange={(v) => actions.set('sbInput', v)}
          onSend={actions.sendSb}
          plan={state.plan}
          prods={state.prods}
          onPatchProd={actions.patchProd}
          pending={state.pending}
          onConfirm={actions.confirmPending}
          onDecline={actions.declinePending}
          height={430}
        />
      </div>
    </div>
  );
}

const subLabelStyle = { fontSize: 12, fontWeight: 700, color: colors.textFaint };
const rowLabelStyle = { fontSize: 11.5, fontWeight: 700, color: colors.textFaint, flex: 'none', width: 28 };
const miniFieldStyle = {
  flex: '1 1 138px', minWidth: 138, height: 42, borderRadius: 8,
  border: `1px solid ${colors.inputBorder}`, background: '#fff', color: colors.text,
  fontSize: 15, padding: '0 8px', cursor: 'pointer'
};
