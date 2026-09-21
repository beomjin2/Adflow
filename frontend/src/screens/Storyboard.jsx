import ChatPanel from '../components/ChatPanel.jsx';

const EMPTY_HINT = `오늘 무엇을 알리고 싶으신가요?
편하게 말씀해주시면 컷으로 나눠 드려요.

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
 *  대로다. 왼쪽은 카드 세 장(설정·생산 기록 / 밈 / 정해진 내용), 오른쪽이 대화창.
 *  네컷 그림은 왼쪽 미리보기가 아니라 **대화창 안**에서 채워진다(ComicBubble).
 */
export default function Storyboard({ state, actions }) {
  const missingProds = state.prods.filter((p) => !p.soldOut);
  const sbSummary = [state.adType, state.adConcept, state.charName].filter(Boolean).join(' · ') || '아직 안 정함';
  const selectedMemeCard = (state.memes || []).find((m) => String(m.id) === String(state.memeId));
  const memeCard = selectedMemeCard?.card || {};
  // 트렌드 확인 화면에서 밈을 고르고 왔으면 applyAd()가, "밈 고르기"에서 카드를 골랐으면
  // pickMemeCard()가 이 칸들을 채운다 — 어느 쪽이든 채워져 있으면 접힌 채로 두지 않는다.
  const memeDraftFilled = !!(state.memeTitle || state.memeText);

  return (
    <div className="ad-split match">
      <section className="ad-col" style={{ gap: 16 }}>
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

        <div className="ad-card ad-pad ad-col" style={{ gap: 12 }}>
          <div className="ad-sec-t">
            <h3>밈으로 스토리 제안받기</h3>
            <span className="ad-grow" />
            <button className="ad-btn ghost xs" onClick={actions.goTrend}>트렌드에서 더 보기 ›</button>
          </div>
          <span className="ad-hint">
            밈을 고르면 가게 정보로 4컷 초안을 만들어 대화창에 제안해요. 마음에 들면 거기서 “이대로 바꾸기”.
          </span>

          <div className="ad-row" style={{ flexWrap: 'wrap' }}>
            <select
              className={`ad-select${state.memeId ? '' : ' unset'}`}
              style={{ flex: 1, minWidth: 190 }}
              value={state.memeId || ''}
              disabled={!!state.trendSel}
              onChange={(e) => actions.pickMemeCard(e.target.value)}
            >
              <option value="">밈 고르기</option>
              {(state.memes || []).map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
            </select>
            <button className="ad-btn tint" onClick={actions.proposeStory} disabled={!state.memeId || state.sbThinking}>
              {state.sbThinking ? '만드는 중…' : '스토리 제안받기'}
            </button>
          </div>

          {state.trendSel && (
            <span className="ad-hint">
              트렌드에서 고른 밈으로 카드를 만드는 중이라 다른 카드는 고를 수 없어요. 다른 밈을 쓰려면 트렌드 화면에서 다시 골라주세요.
            </span>
          )}

          {selectedMemeCard && (
            <div className="ad-col" style={{ gap: 7, background: 'var(--soft)', borderRadius: 11, padding: '10px 12px', animation: 'pop .18s ease' }}>
              {memeCard.definition && <span style={{ fontSize: 13, lineHeight: '19px' }}>{memeCard.definition}</span>}
              {memeCard.template && (
                <div style={{ display: 'flex', gap: 6, alignItems: 'baseline' }}>
                  <span style={{ fontSize: 10.5, fontWeight: 800, color: 'var(--mute)', letterSpacing: .3, flex: 'none' }}>말 틀</span>
                  <span style={{ fontSize: 12.5, lineHeight: '18px', color: 'var(--sub)' }}>{memeCard.template}</span>
                </div>
              )}
              {(memeCard.industries || []).length > 0 && (
                <div className="ad-wrapc" style={{ gap: 5 }}>
                  {memeCard.industries.map((ind) => (
                    <span key={ind} className="ad-pill green" style={{ height: 24, fontSize: 11.5 }}>{ind}</span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 채워져 있으면(트렌드에서든, 밈 고르기에서든) 접힌 채로 숨어있지 않게 기본으로 펼쳐 둔다. */}
          <details open={memeDraftFilled} className="ad-acc">
            <summary className="ad-acc-sum" style={{ fontSize: 14, color: 'var(--sub)' }}>
              ＋ 밈 카드 직접 추가 (원문 붙여넣기)
              {state.memeDraftFromTrend && <span className="ad-pill green" style={{ height: 24, fontSize: 11.5 }}>트렌드에서 가져옴</span>}
            </summary>
            <div className="ad-acc-body">
              <input className="ad-input" value={state.memeTitle || ''} placeholder="밈 이름"
                onChange={(e) => actions.set('memeTitle', e.target.value)} />
              <input className="ad-input" value={state.memeSource || ''} placeholder="출처(사이트·링크)"
                onChange={(e) => actions.set('memeSource', e.target.value)} />
              <textarea className="ad-textarea" value={state.memeText || ''}
                placeholder="밈 원문 본문을 그대로 붙여넣기 (요약만으로는 카드가 안 나와요)"
                onChange={(e) => actions.set('memeText', e.target.value)} />
              <button className="ad-btn soft sm" style={{ alignSelf: 'flex-start' }} onClick={actions.addMeme}
                disabled={!(state.memeTitle || '').trim() || (state.memeText || '').trim().length < 40 || state.sbThinking}>
                카드 만들기
              </button>
            </div>
          </details>
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
