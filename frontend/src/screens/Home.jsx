import { colors } from '../theme.js';
import { PrimaryButton, SecondaryButton } from '../components/ui/Button.jsx';

/** 홈 — 카드 5장을 격자로 늘어놓는 대신 "순서가 있는 3단계"와 "언제든지 여는 도구"를 갈랐다.
 *  사장님이 다음에 눌러야 할 칸이 한 개만 초록으로 크게 뜬다. */
export default function Home({ state, actions, charLocked, adLocked }) {
  const missingProds = state.prods.filter((p) => !p.soldOut);
  const done = (state.storeSaved ? 1 : 0) + (state.charConfirmed ? 1 : 0);

  // 이미 만들어 둔 그림이 있으면 단계 동그라미에 그대로 쓴다 — 자기 가게 사진과 캐릭터가 보인다.
  const storePic = (state.storeImages || []).find((im) => im.image)?.image || '';
  const charPic = (state.charCands || [])[state.charSelected ?? 0]?.image || '';

  const head = done === 2
    ? <>이제 <em>광고를 만들</em> 차례예요</>
    : done === 1
      ? <>다음은 <em>마스코트 캐릭터</em>예요</>
      : <>가게 정보만 넣으면 <em>광고</em>가 나와요</>;

  const nextIs = !state.storeSaved ? 1 : !state.charConfirmed ? 2 : 3;

  return (
    <>
      <section className="ad-hero"><h2>{head}</h2></section>

      <div className="ad-cols">
        <section className="ad-card ad-flow" aria-label="광고 만들기 순서">
          <div className="ad-flow-h">
            <h3>광고 만들기</h3>
            <span className="ad-grow" />
            <span className="ad-prog">
              <span className="bar"><i style={{ width: `${(done / 3) * 100}%` }} /></span>{done}/3
            </span>
          </div>

          <div className="ad-steps">
            <Step
              n={state.storeSaved && storePic ? <img src={storePic} alt="" /> : (state.storeSaved ? '✓' : '1')}
              cls={nextIs === 1 ? 'next' : ''}
              title="가게 등록" desc="업종 · 상품 사진 · 영업시간"
              status={state.storeSaved ? (state.storeCategory || '입력 완료') : '시작 →'}
              onClick={actions.goStore}
            />
            <Step
              n={state.charConfirmed && charPic ? <img src={charPic} alt="" /> : (state.charConfirmed ? '✓' : '2')}
              cls={nextIs === 2 ? 'next' : charLocked ? 'todo' : ''}
              title="마스코트 캐릭터" desc="대화로 우리 가게 캐릭터를 만들어요"
              status={state.charConfirmed ? (state.charName || '확정함') : charLocked ? '가게 정보 먼저' : '시작 →'}
              onClick={actions.goChar} disabled={charLocked}
            />
            <Step
              n="3" cls={nextIs === 3 ? 'next' : 'todo'}
              title="광고 만들기" desc="종류와 느낌을 고르고 내용을 정해요"
              status={adLocked ? '캐릭터 먼저' : '시작 →'}
              onClick={actions.openAdEntry} disabled={adLocked}
            />
          </div>
        </section>

        <aside className="ad-side">
          <div className="ad-side-h">언제든지</div>

          <div className="ad-card ad-tool rec">
            <button className="ad-tool-row" onClick={actions.openProdTab}>
              <span className="ic">기록</span>
              <span className="txt">
                <span className="title">생산 기록</span>
                <span className="desc">{state.prods.length ? `${state.prods.length}건` : '아직 없어요'}{state.items?.length ? ` · 품목 ${state.items.length}개` : ''}</span>
              </span>
              <span className="arr">→</span>
            </button>
            {missingProds.length > 0 && (
              <button className="ad-warnrow" onClick={actions.openProdTab}>
                <span className="txt">
                  <b>매진 시각 미입력 {missingProds.length}건</b>
                  <span>{missingProds[0].name} {missingProds[0].date}</span>
                </span>
                <span className="go">입력</span>
              </button>
            )}
          </div>

          <button className="ad-card ad-tool-row trend" onClick={actions.goTrend}>
            <span className="ic">밈</span>
            <span className="txt">
              <span className="title">트렌드 보고서</span>
              <span className="desc">{state.trendItems.length ? `밈 ${state.trendItems.length}개` : '아직 수집 전이에요'}</span>
            </span>
            <span className="arr">→</span>
          </button>

          <button className="ad-card ad-tool-row me" onClick={actions.goMy}>
            <span className="ic">{charPic ? <img src={charPic} alt="" /> : '나'}</span>
            <span className="txt">
              <span className="title">내 정보</span>
              <span className="desc">{state.history.length ? `보관한 광고 ${state.history.length}개` : '보관함 · 가게 · 캐릭터 · 백업'}</span>
            </span>
            <span className="arr">→</span>
          </button>
        </aside>
      </div>

      {state.adEntryOpen && (
        <div
          onClick={(e) => { if (e.target === e.currentTarget) actions.closeAdEntry(); }}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(15,17,19,.42)', zIndex: 100,
            display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
          }}
        >
          <div style={{
            width: '100%', maxWidth: 420, background: '#fff', borderRadius: 20, padding: 26,
            display: 'flex', flexDirection: 'column', gap: 18, animation: 'pop .18s ease',
            boxShadow: '0 20px 50px rgba(0,0,0,.22)',
          }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span style={{ fontSize: 20, fontWeight: 700, letterSpacing: -.4 }}>광고를 어떻게 만들까요?</span>
              <span style={{ fontSize: 14.5, lineHeight: '22px', color: colors.textSub }}>
                요즘 뜨는 밈을 참고해서 만들 수도 있고, 바로 내용을 정할 수도 있어요.
              </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <PrimaryButton onClick={actions.pickAdEntryTrend}>트렌드 참고해서 만들기</PrimaryButton>
              <SecondaryButton onClick={actions.pickAdEntryDirect}>트렌드 없이 바로 만들기</SecondaryButton>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Step({ n, cls = '', title, desc, status, onClick, disabled }) {
  return (
    <button className={`ad-step ${cls}`} onClick={onClick} disabled={disabled}>
      <span className="n">{n}</span>
      <span className="t">
        <span className="title">{title}</span>
        {cls === 'next' && <span className="desc">{desc}</span>}
      </span>
      <span className="st">{status}</span>
    </button>
  );
}
