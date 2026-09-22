const AD_TYPES = ['인스타 게시물', '4컷만화'];
const AD_CONCEPTS = ['유쾌함', '감성', '정보형', '담백함'];

// 대화(story_llm.cut_count)가 실제로 나누는 컷 수 그대로 — 아직 예시 그림이 없어서
// 실제 그림 대신 칸 목업으로 "몇 컷으로 나뉘는지"만 미리 보여준다.
const CUT_COUNTS = { '4컷만화': 4, '인스타 게시물': 3 };

/** 3단계 — 광고 종류와 느낌을 고른다.
 *
 *  개선안(claude.ai/design 프로젝트 bdf26dfe, `app/screens-flow.js` 의 `/ad`)을 그대로
 *  옮긴 것이다. 두 가지가 그 전과 다르다:
 *  - 느낌은 select 가 아니라 칩이다. 넷뿐이라 펼쳐 두면 무엇 중에서 고르는지 보인다.
 *  - "이 광고에 쓰일 내용"이 오른쪽 카드로 나왔다. 고르는 곳과 쓰이는 재료를 나란히 둔다.
 */
export default function Ad({ state, actions }) {
  const ready = !!state.adType && !!state.adConcept;
  const trendMeme = state.trendItems.find((m) => m.id === state.trendSel);
  // 비어 있는 칸은 비었다고 쓴다. 이 목록은 광고 문구에 그대로 들어갈 재료라,
  // 무엇이 비었는지 여기서 안 보이면 사장님은 결과를 보고서야 안다.
  const none = <span className="none">아직 없음</span>;

  return (
    <div className="ad-split l">
      <form
        className="ad-card ad-pad ad-col"
        style={{ gap: 22 }}
        onSubmit={(e) => { e.preventDefault(); if (ready) actions.applyAd(); }}
      >
        <div className="ad-field">
          <label htmlFor="adType">어디에 쓸 광고인가요?</label>
          <select
            id="adType"
            className={`ad-select${state.adType ? '' : ' unset'}`}
            value={state.adType}
            onChange={(e) => actions.set('adType', e.target.value)}
          >
            <option value="">광고 종류를 골라주세요</option>
            {AD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>

        <div className="ad-field">
          <span className="ad-lbl">어떤 느낌으로 만들까요?</span>
          <div className="ad-wrapc">
            {AD_CONCEPTS.map((c) => (
              <button
                key={c}
                type="button"
                className={`ad-chipbtn${state.adConcept === c ? ' on' : ''}`}
                aria-pressed={state.adConcept === c}
                onClick={() => actions.set('adConcept', c)}
              >{c}</button>
            ))}
          </div>
        </div>

        {state.adType && CUT_COUNTS[state.adType] && (
          <div className="ad-field">
            <span className="ad-lbl">이렇게 만들어져요 — {CUT_COUNTS[state.adType]}컷</span>
            <div
              className="ad-mockgrid"
              style={{ gridTemplateColumns: `repeat(${CUT_COUNTS[state.adType]}, 52px)` }}
            >
              {Array.from({ length: CUT_COUNTS[state.adType] }, (_, i) => (
                <span className="ad-mockcut" key={i}>{i + 1}</span>
              ))}
            </div>
            <span className="ad-hint">진짜 그림은 대화로 내용을 정한 뒤에 캐릭터로 그려져요. 이건 컷이 몇 개로 나뉘는지 보여주는 예시예요.</span>
          </div>
        )}

        <button type="submit" className="ad-btn pri block" disabled={!ready}>
          {ready ? '다음 — 광고 내용 정하기' : '종류와 느낌을 골라주세요'}
        </button>

        <span className="ad-hint" style={{ textAlign: 'center' }}>
          다음 화면에서 대화로 컷 구성을 만듭니다. 여기서 고른 건 나중에도 바꿀 수 있어요.
        </span>
      </form>

      <aside
        className="ad-card ad-pad ad-col"
        style={{ gap: 14, background: 'var(--soft)', borderColor: 'transparent', boxShadow: 'none' }}
      >
        <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, letterSpacing: '-.3px' }}>
          이 광고에 쓰일 내용
        </h3>

        <dl className="ad-kv">
          <dt>가게</dt>
          <dd>
            {state.storeCategory
              ? <><b>{state.storeCategory}</b>{state.storeAddress ? ` · ${state.storeAddress}` : ''}</>
              : none}
          </dd>
          <dt>캐릭터</dt>
          <dd>
            {state.charConfirmed
              ? <><b>{state.charName || '이름 없음'}</b>{state.charLook ? ` · ${state.charLook}` : ''}</>
              : none}
          </dd>
          <dt>소개</dt>
          <dd>{state.storeDesc || none}</dd>
          {trendMeme && (<><dt>트렌드</dt><dd><b>{trendMeme.name}</b></dd></>)}
        </dl>

        <div className="ad-wrapc">
          <button type="button" className="ad-btn sec xs" onClick={actions.goStore}>가게 정보 보기</button>
          <button type="button" className="ad-btn sec xs" onClick={actions.myChar}>캐릭터 보기</button>
        </div>
      </aside>
    </div>
  );
}
