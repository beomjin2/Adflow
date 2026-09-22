import ChatPanel from '../components/ChatPanel.jsx';

const EMPTY_HINT = `오늘 알리고 싶은 내용을 편하게 적어주세요.
적어주시면 그 이야기로 스토리를 만들어 드려요.
아무것도 안 적고 '스토리 제안받기'를 눌러도 만들어 드리지만,
가게·생산 기록 정보가 적으면 구성이 부실할 수 있어요 — 되도록 직접 적어주세요.

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
 *  밈은 따로 고르는 화면이 없다 — 트렌드 화면에서 미리 골라 왔을 때만(트렌드 참고해서
 *  만들기) 대화가 그 밈을 반영한다. 안 골라 왔으면 밈 얘기 자체를 안 꺼낸다 — GPT가
 *  스스로 골라 끼워 넣으면 사장님이 고른 적 없는 밈이 섞이기 때문이다
 *  (backend/app/services/story_llm.py 참고).
 */
export default function Storyboard({ state, actions }) {
  const missingProds = state.prods.filter((p) => !p.soldOut);
  const sbSummary = [state.adType, state.adConcept, state.charName].filter(Boolean).join(' · ') || '아직 안 정함';
  // 4컷만화는 그림이 광고의 핵심이라 "네컷 그리기"를 먼저 끝내야 다음으로 넘어갈 수 있다.
  // 인스타 게시물은 문구만으로도 올릴 수 있는 형식이라 그림을 요구하지 않는다(openResult와 같은 규칙).
  const needsComic = state.adType === '4컷만화';
  const comicReady = !needsComic
    || (state.comicCuts.length >= state.plan.length && state.comicCuts.every((c) => c.status === 'done'));

  return (
    <div className="ad-split match">
      <section className="ad-col" style={{ gap: 16 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div className="ad-card" style={{ padding: '4px 20px' }}>
            <Accordion open={state.sbSetOpen} onToggle={actions.toggleSbSet} label="광고 설정" pill={sbSummary}>
              <div className="ad-row" style={{ alignItems: 'center' }}>
                <span className="ad-hint">종류와 느낌은 버튼을 눌러 바꿀 수 있어요.</span>
                <span className="ad-grow" />
                <button className="ad-btn ghost xs" onClick={actions.goAd}>
                  설정 바꾸기 ›
                </button>
              </div>
            </Accordion>

            <Accordion
              open={state.sbProdOpen} onToggle={actions.toggleSbProd} label="최근 생산 기록"
              pillTone={missingProds.length ? 'warn' : ''}
              pill={state.prods.length === 0
                ? '없음'
                : missingProds.length ? `${state.prods.length}건 · 매진 미입력 ${missingProds.length}` : `${state.prods.length}건`}
            >
              <div className="ad-row" style={{ alignItems: 'center' }}>
                <span className="ad-hint">
                  {state.prods.length === 0 ? '아직 기록이 없어요.' : '기록을 더 넣거나 고칠 수 있어요.'}
                </span>
                <span className="ad-grow" />
                <button className="ad-btn ghost xs" onClick={actions.openProdTab}>
                  생산 기록 관리 ›
                </button>
              </div>
              {state.prods.slice(0, 3).map((p) => (
                <div className="ad-row" key={p.id} style={{ fontSize: 14.5, flexWrap: 'wrap' }}>
                  <b>{p.name}</b>
                  <span style={{ color: 'var(--sub)' }}>{p.qty ? `${p.qty}개 · ` : ''}{p.date} {p.time}</span>
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
              onClick={actions.openResult} disabled={!state.plan.length || !comicReady}>
              {!state.plan.length ? '대화로 내용을 먼저 정해주세요'
                : !comicReady ? '네컷 그리기를 먼저 해주세요'
                  : '이 내용으로 광고 만들기'}
            </button>
          </div>
        </div>
      </section>

      <ChatPanel
        title="무엇을 알리고 싶으세요? — AI와 대화"
        disclaimer="AI가 만든 내용이에요 — GPT도 실수할 수 있으니 올리기 전에 한 번 확인해주세요."
        messages={state.sbMsgs}
        thinking={state.sbThinking}
        thinkingLabel="정리하는 중…"
        emptyHint={EMPTY_HINT}
        placeholder="오늘 알리고 싶은 내용을 적어주세요"
        input={state.sbInput}
        onInputChange={(v) => actions.set('sbInput', v)}
        onSend={actions.sendSb}
        onSuggest={actions.suggestStory}
        onRecommendMeme={actions.recommendMeme}
        plan={state.plan}
        comic={state.comicCuts}
        comicEta={state.sbEta}
        prods={state.prods}
        onPatchProd={actions.patchProd}
        pending={state.pending}
        onConfirm={actions.confirmPending}
        onDecline={actions.declinePending}
      />
    </div>
  );
}
