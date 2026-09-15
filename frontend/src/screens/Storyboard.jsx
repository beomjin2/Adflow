import { colors } from '../theme.js';
import { Select } from '../components/ui/Field.jsx';
import { PrimaryButton } from '../components/ui/Button.jsx';
import ChatPanel from '../components/ChatPanel.jsx';

const AD_TYPES = ['인스타 게시물', '포스터', '메뉴판'];
const AD_CONCEPTS = ['유쾌함', '감성', '정보형', '담백함'];

export default function Storyboard({ state, actions }) {
  const missingProds = state.prods.filter(p => !p.soldOut);
  const sbSummary = `${state.adType} · ${state.adConcept}${state.trendApplied ? ` · ${state.trendPick}` : ''}${state.charName ? ` · ${state.charName}` : ''}`;
  const storyBadge = state.plan.length ? (state.comicCuts.length ? '네컷만화 반영됨' : '4컷 확정') : '비어 있음';

  return (
    <div style={{ padding: '18px 20px 20px', display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'stretch' }}>
      <div style={{ flex: '1 1 230px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ border: `1px solid ${state.sbSetOpen ? colors.onboardBorder : colors.cardBorder}`, background: state.sbSetOpen ? colors.onboardBg : '#fff', borderRadius: 14, overflow: 'hidden' }}>
          <button onClick={actions.toggleSbSet} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, background: 'transparent', border: 0, cursor: 'pointer', padding: '13px 14px', textAlign: 'left' }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: colors.textSub, flex: 'none' }}>광고 설정</span>
            <span style={{ fontSize: 11, color: colors.textFaint, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{sbSummary}</span>
            <span style={{ flex: 1 }} />
            <span style={{ fontSize: 14, color: colors.textFaint, transition: 'transform .18s ease', display: 'inline-block', transform: `rotate(${state.sbSetOpen ? 180 : 0}deg)` }}>⌄</span>
          </button>
          {state.sbSetOpen && (
            <div style={{ padding: '0 14px 13px', display: 'flex', flexDirection: 'column', gap: 10, animation: 'pop .18s ease' }}>
              {state.trendApplied && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: colors.textFaint }}>트렌드 선택</span>
                  <Select value={state.trendPick} onChange={e => actions.set('trendPick', e.target.value)}>
                    {state.trendDetail.map(t => <option key={t.name}>{t.name}</option>)}
                  </Select>
                </div>
              )}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: colors.textFaint }}>광고 종류</span>
                <Select value={state.adType} onChange={e => actions.set('adType', e.target.value)}>
                  {AD_TYPES.map(t => <option key={t}>{t}</option>)}
                </Select>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: colors.textFaint }}>광고 컨셉</span>
                <Select value={state.adConcept} onChange={e => actions.set('adConcept', e.target.value)}>
                  {AD_CONCEPTS.map(c => <option key={c}>{c}</option>)}
                </Select>
              </div>
            </div>
          )}
        </div>

        <div style={{ border: `1px solid ${state.sbProdOpen ? colors.onboardBorder : colors.cardBorder}`, background: state.sbProdOpen ? colors.onboardBg : '#fff', borderRadius: 14, overflow: 'hidden' }}>
          <button onClick={actions.toggleSbProd} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, background: 'transparent', border: 0, cursor: 'pointer', padding: '13px 14px', textAlign: 'left' }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: colors.textSub }}>최근 생산 기록</span>
            <span style={{ fontSize: 11, fontWeight: 700, borderRadius: 999, padding: '3px 8px', background: missingProds.length ? colors.warnBg : colors.softBg, color: missingProds.length ? colors.warnText : colors.textSub }}>
              {missingProds.length ? `${state.prods.length}건 · 매진 미입력 ${missingProds.length}` : `${state.prods.length}건`}
            </span>
            <span style={{ flex: 1 }} />
            <span style={{ fontSize: 14, color: colors.textFaint, transition: 'transform .18s ease', display: 'inline-block', transform: `rotate(${state.sbProdOpen ? 180 : 0}deg)` }}>⌄</span>
          </button>
          {state.sbProdOpen && (
            <div style={{ padding: '0 14px 13px', display: 'flex', flexDirection: 'column', gap: 8, animation: 'pop .18s ease' }}>
              {state.prods.length === 0 && (
                <span style={{ fontSize: 11.5, lineHeight: '18px', color: colors.textFaint }}>아직 기록이 없어요 — 대화에서 생산한 품목을 말하면 자동으로 남아요.</span>
              )}
              {state.prods.slice(0, 2).map(p => {
                const missing = !p.soldOut;
                return (
                  <div key={p.id} style={{ display: 'flex', flexDirection: 'column', gap: 7, background: missing ? colors.warnBg : colors.bg, border: `1px solid ${missing ? colors.warnBorder : colors.cardBorder}`, borderRadius: 11, padding: '10px 11px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                      <input value={p.name} onChange={e => actions.patchProd(p.id, { name: e.target.value })} style={{ flex: 1, minWidth: 0, height: 30, borderRadius: 8, border: `1px solid ${colors.inputBorder}`, background: '#fff', color: colors.text, fontSize: 12.5, fontWeight: 600, padding: '0 8px' }} />
                      <span style={{ fontSize: 11, fontWeight: 700, color: colors.textFaint, flex: 'none' }}>{p.qty}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 10.5, fontWeight: 700, color: colors.textFaint, flex: 'none', width: 26 }}>생산</span>
                      <input type="date" value={p.date} onChange={e => actions.patchProd(p.id, { date: e.target.value })} style={miniFieldStyle} />
                      <input type="time" value={p.time} onChange={e => actions.patchProd(p.id, { time: e.target.value })} style={miniFieldStyle} />
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 10.5, fontWeight: 700, color: colors.textFaint, flex: 'none', width: 26 }}>매진</span>
                      <input type="time" value={p.soldOut} onChange={e => actions.setSoldOut(p.id, e.target.value)} style={{ ...miniFieldStyle, borderColor: missing ? '#E0BE74' : colors.inputBorder }} />
                    </div>
                    <span style={{ fontSize: 11.5, fontWeight: 700, color: missing ? colors.warnText2 : colors.primary }}>{missing ? '매진 시각 미입력' : `매진 ${p.soldOut} 기록됨`}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div style={{ background: '#fff', border: `1px solid ${colors.cardBorder}`, borderRadius: 14, padding: '13px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: colors.textSub }}>지금 정해진 스토리</span>
            <span style={{ flex: 1 }} />
            <span style={{ fontSize: 10.5, fontWeight: 700, borderRadius: 999, padding: '3px 8px', background: state.plan.length ? colors.primarySoft : colors.softBg, color: state.plan.length ? colors.primarySoftText : colors.textFaint }}>{storyBadge}</span>
          </div>
          {state.plan.length === 0 && (
            <span style={{ fontSize: 11.5, lineHeight: '18px', color: colors.textFaint }}>아직 비어 있어요 — 대화로 정하고 확인을 누르면 컷별로 여기에 쌓여요.</span>
          )}
          {state.plan.map(c => (
            <div key={c.n} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
              <span style={{ fontSize: 10.5, fontWeight: 800, color: colors.primarySoftText, background: colors.primarySoft, borderRadius: 6, padding: '3px 6px', flex: 'none' }}>{c.n}컷</span>
              <span style={{ fontSize: 12, lineHeight: '18px', color: colors.text }}>{c.line}</span>
            </div>
          ))}
        </div>
        <div style={{ flex: 1 }} />
        <PrimaryButton onClick={actions.makeComic} disabled={!state.plan.length}>
          {state.comicCuts.length ? '네컷만화 재생성' : '네컷만화 생성'}
        </PrimaryButton>
      </div>

      <div style={{ flex: '2 1 430px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: colors.textSub }}>원하는 스토리 — AI와 대화</span>
        <ChatPanel
          messages={state.sbMsgs}
          thinking={state.sbThinking}
          thinkingLabel="그리는 중…"
          input={state.sbInput}
          onInputChange={(v) => actions.set('sbInput', v)}
          onSend={actions.sendSb}
          plan={state.plan}
          comicCuts={state.comicCuts.map(c => ({ n: c.n, hue: c.hue }))}
          onOpenComic={actions.openResult}
          onRerollCut={actions.rerollCut}
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

const miniFieldStyle = {
  flex: '1 1 138px', minWidth: 138, height: 34, borderRadius: 8,
  border: `1px solid ${colors.inputBorder}`, background: '#fff', color: colors.text,
  fontSize: 12.5, padding: '0 8px', cursor: 'pointer'
};
