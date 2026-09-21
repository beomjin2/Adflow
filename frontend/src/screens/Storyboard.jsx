import ChatPanel from '../components/ChatPanel.jsx';

const EMPTY_HINT = `오늘 무엇을 만드셨나요?
답해주시면 생산 기록으로 남기고, 그다음 어떤 장면이 좋을지 적어주시거나
'스토리 제안받기'를 누르면 바로 만들어 드려요.

예) 오늘 소금빵 30개 구웠어요
예) 이번 주말에 새 메뉴를 내요`;

/** 접었다 펴는 줄. 설정과 생산 기록은 광고를 만드는 동안 늘 펼쳐둘 내용이 아니라
 *  "지금 뭐로 되어 있더라" 하고 한 번 확인하는 것이라 접어 둔다. */
function Accordion({ open, onToggle, label, pill, pillTone = '', children }) {
  return (
    <div className="ad-acc">
      <button className="ad-acc-sum" aria-expanded={open} onClick={onToggle}>
        <span>{label}</span>
        {pill && <span className={`ad-pill ${pillTone}`.trim()}>{pill}</span>}
        <span className="arr">⌄</span>
      </button>
      {open && <div className="ad-acc-body">{children}</div>}
    </div>
  );
}

/** 3단계 — 대화로 컷 구성을 만든다.
 *
 *  개선안(claude.ai/design 프로젝트 bdf26dfe, `app/screens-flow.js` 의 `/storyboard`)
 *  대로다. 왼쪽은 카드 두 장(설정·생산 기록 / 정해진 내용), 오른쪽이 대화창.
 *  네컷 그림은 왼쪽 미리보기가 아니라 **대화창 안**에서 채워진다(ComicBubble).
 *
 *  밈은 따로 고르는 화면이 없다 — 트렌드 화면에서 미리 골라 왔으면(트렌드 참고해서
 *  만들기) 대화가 그 밈을 자동으로 반영하고, 안 골라 왔으면 GPT가 크롤링된 밈 중
 *  자연스럽게 붙는 게 있는지 스스로 살펴보고 있으면 "이런 밈도 있어요"라고 알려준다
 *  (backend/app/services/story_llm.py 참고).
 */
export default function Storyboard({ state, actions }) {
  const missingProds = state.prods.filter((p) => !p.soldOut);
  const sbSummary = [state.adType, state.adConcept, state.charName].filter(Boolean).join(' · ') || '아직 안 정함';

  return (
    <div className="ad-split match">
      <section className="ad-col" style={{ gap: 16 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div className="ad-card" style={{ padding: '4px 20px' }}>
            <Accordion open={state.sbSetOpen} onToggle={actions.toggleSbSet} label="광고 설정" pill={sbSummary}>
              <span className="ad-hint">종류와 느낌을 바꾸려면 이전 화면으로 돌아가세요.</span>
              <button className="ad-btn sec sm" style={{ alignSelf: 'flex-start' }} onClick={actions.goAd}>
                설정 바꾸기
              </button>
            </Accordion>

            <Accordion
              open={state.sbProdOpen} onToggle={actions.toggleSbProd} label="최근 생산 기록"
              pillTone={missingProds.length ? 'warn' : ''}
              pill={state.prods.length === 0
                ? '없음'
                : missingProds.length ? `${state.prods.length}건 · 매진 미입력 ${missingProds.length}` : `${state.prods.length}건`}
            >
              {state.prods.length === 0 && (
                <span className="ad-hint">
                  아직 기록이 없어요 — 대화에서 “오늘 소금빵 20개 만들었어요”처럼 말하면 자동으로 남아요.
                </span>
              )}
              {state.prods.slice(0, 3).map((p) => (
                <div className="ad-row" key={p.id} style={{ fontSize: 14.5, flexWrap: 'wrap' }}>
                  <b>{p.name}</b>
                  <span style={{ color: 'var(--sub)' }}>{p.qty ? `${p.qty} · ` : ''}{p.date} {p.time}</span>
                  <span className="ad-grow" />
                  {p.soldOut
                    ? <span className="ad-pill green">매진 {p.soldOut}</span>
                    : <button className="ad-pill warn" onClick={actions.openProdTab} style={{ cursor: 'pointer' }}>매진 시각 입력</button>}
                </div>
              ))}
            </Accordion>
          </div>

          {state.sbTrendMemeName && (
            <div className="ad-card ad-pad ad-row" style={{ gap: 10, alignItems: 'center' }}>
              <span style={{ flex: 'none', fontSize: 15, fontWeight: 700, color: 'var(--ink)' }}>트렌드</span>
              <span className="ad-pill green">{state.sbTrendMemeName}</span>
            </div>
          )}
        </div>

        <div className="ad-card ad-pad ad-col" style={{ gap: 12 }}>
          <div className="ad-sec-t">
            <h3>지금 정해진 내용</h3>
            <span className="ad-grow" />
            <span className={`ad-pill ${state.plan.length ? 'green' : ''}`.trim()}>
              {state.plan.length ? `${state.plan.length}컷` : '비어 있음'}
            </span>
          </div>

          {state.plan.length === 0 ? (
            <span className="ad-hint">
              아직 비어 있어요 — 오른쪽 대화창에 하고 싶은 말을 적으면 컷으로 나눠 여기에 쌓여요.
            </span>
          ) : (
            <div>
              {state.plan.map((c) => (
                <div className="ad-cut" key={c.n}>
                  <span className="n">{c.n}</span>
                  <span>{c.line}</span>
                </div>
              ))}
            </div>
          )}

          <div className="ad-row" style={{ flexWrap: 'wrap' }}>
            <button className="ad-btn tint" onClick={actions.makeComic}
              disabled={!state.plan.length || !state.charConfirmed || state.sbGenerating}>
              {!state.charConfirmed ? '캐릭터를 먼저 확정해주세요'
                : state.sbGenerating ? '그리는 중…'
                  : (state.comicCuts || []).length ? '네컷 다시 그리기' : '네컷 그리기'}
            </button>
            <button className="ad-btn pri" style={{ flex: 1, minWidth: 160 }}
              onClick={actions.openResult} disabled={!state.plan.length}>
              {state.plan.length ? '이 내용으로 광고 만들기' : '대화로 내용을 먼저 정해주세요'}
            </button>
          </div>
        </div>
      </section>

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
        onSuggest={actions.suggestStory}
        plan={state.plan}
        comic={state.comicCuts}
        comicEta={state.sbEta}
        onRerollCut={actions.rerollCut}
        prods={state.prods}
        onPatchProd={actions.patchProd}
        pending={state.pending}
        onConfirm={actions.confirmPending}
        onDecline={actions.declinePending}
      />
    </div>
  );
}
