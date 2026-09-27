import { useEffect, useRef, useState } from 'react';
import { colors } from '../theme.js';
import { PrimaryButton, SecondaryButton, SoftButton } from '../components/ui/Button.jsx';
import { TextInput, Label } from '../components/ui/Field.jsx';
import { StoryboardAPI } from '../api/client.js';

/** 인스타그램 계정 연결 안내 — 사장님이 혼자 따라 할 수 있게 만드는 게 목적이다.
 *
 *  왜 이렇게 길게 쓰나: 인스타 자동 게시는 Meta 개발자 콘솔에서 앱을 만들고 토큰을 받아야
 *  한다. 개발자용 화면이라 처음 보는 사장님은 어디를 눌러야 할지 알 수 없다. 그래서
 *  ① 한 화면에 한 단계씩, ② 무엇을 찾아야 하는지(버튼 글자)까지 적고, ③ 실제 화면을
 *  찍어 빨간 네모로 누를 곳을 표시해 붙였다. 그림은 public/instagram-guide/*.png 이고
 *  단계마다 여러 장을 순서대로 보여준다(파일이 없으면 그 자리만 조용히 비운다).
 *  글씨가 작아 안 보일 수 있으니 누르면 크게 열린다.
 *
 *  2026-09-27 새 계정(adflow.bakery)으로 처음부터 끝까지 다시 밟으며 찍은 화면이다.
 *  그때 실제로 막혔던 자리(권한 하나 누락, 저장 오류, 개인 계정, 드롭다운 미선택)가
 *  곧 사장님이 막힐 자리라, 그 넷은 팁이 아니라 본문·경고로 올려 뒀다.
 *
 *  값을 저장하기 전에 인스타에 한 번 물어본다(POST /instagram/connect) — 잘못된 값을
 *  저장해 두면 사장님은 나중에 게시를 눌러 보고서야 알게 된다. */

const STEPS = [
  {
    title: '인스타그램을 비즈니스 계정으로 바꾸기',
    shots: [
      { f: 's1a0_home', cap: '로그인하면 나오는 첫 화면이에요. 왼쪽 아래 "더 보기"를 누르면 이 메뉴가 열립니다 → 설정' },
      { f: 's1a_settings', cap: '설정 화면입니다. 왼쪽 목록을 아래로 내리면 "프로페셔널" 아래에 계정 유형 및 도구가 있어요' },
      { f: 's1b0_convert', cap: '"프로페셔널 계정으로 전환"을 누르세요' },
      { f: 's1b_business', cap: '"비즈니스"를 고르고 다음 (크리에이터 아님)' },
      { f: 's1c_category', cap: '카테고리는 가게에 맞는 것으로 고르고 완료' },
      { f: 's1d0_confirm', cap: '다시 물어보면 "계속하기"' },
      { f: 's1d_done', cap: '이 화면이 나오면 1단계 끝이에요' },
    ],
    body: '홍보에 쓸 인스타그램 계정을 프로페셔널(비즈니스) 계정으로 바꿉니다. 이렇게 해야 다른 프로그램이 사장님 대신 사진을 올릴 수 있어요.',
    tips: [
      '전환은 무료예요. 팔로워와 지금까지 올린 게시물은 그대로 남습니다.',
      '이미 비즈니스 계정이면 이 단계는 넘어가세요.',
    ],
    time: '2분',
    link: { href: 'https://www.instagram.com/accounts/convert_to_professional_account/', text: '전환 화면 바로 열기' },
  },
  {
    title: 'Meta 개발자 사이트에서 앱 만들기',
    shots: [
      { f: 's2a_myapps', cap: '내 앱 → 앱 만들기' },
      { f: 's2b_appname', cap: '앱 이름과 연락받을 이메일을 넣고 다음. 앱 이름은 인스타그램 계정과 아무 상관이 없으니 원하는 대로 지으셔도 됩니다' },
      { f: 's2c_filter', cap: '왼쪽 목록에서 "콘텐츠 관리"를 누르세요' },
      { f: 's2d_usecase', cap: '"Instagram에서 메시지 및 콘텐츠 관리"를 누른 다음, 아래 "다음"을 누르세요' },
      { f: 's2e_portfolio', cap: '"아직 비즈니스 포트폴리오를 연결하고 싶지 않음"을 누른 다음, "다음"을 누르세요' },
      { f: 's2f_req', cap: '요구 사항도 확인할 것이 없어요 — 다음' },
      { f: 's2g_overview', cap: '마지막 개요 화면입니다. 적어 넣은 앱 이름과 이메일, 그리고 이용 사례가 "Instagram에서 메시지 및 콘텐츠 관리"로 되어 있는지 확인하세요' },
      { f: 's2h_create', cap: '맞으면 아래로 내려서 "앱 만들기"' },
      { f: 's2i_password', cap: '페이스북 비밀번호를 한 번 더 물어봅니다. 그대로 입력하고 제출' },
      { f: 's2j_dashboard', cap: '이 대시보드가 나오면 앱이 만들어진 거예요' },
    ],
    body: 'Meta 개발자 사이트에서 앱을 하나 만듭니다. Adflow가 사장님 인스타그램에 사진을 올릴 때 지나가는 통로예요. 페이스북 계정으로 로그인해서 만듭니다.',
    tips: [
      '"비즈니스 포트폴리오" 화면에서 "다음"이 눌리지 않는다면, 그 위의 "아직 비즈니스 포트폴리오를 연결하고 싶지 않음"을 아직 안 고르신 거예요.',
    ],
    time: '4분',
    link: { href: 'https://developers.facebook.com/apps', text: 'Meta 개발자 사이트 바로가기' },
  },
  {
    title: '사진을 올릴 수 있는 권한 켜기',
    shots: [
      { f: 's3_0_nav', cap: '앱을 만들면 나오는 대시보드입니다. 왼쪽 "이용 사례"를 누르세요' },
      { f: 's3_1_customize', cap: '오른쪽 "맞춤 설정"을 누르면 다음 화면으로 넘어가요' },
      { f: 's3a_addall', cap: '아래로 조금 내려서 "Add all required permissions" 버튼을 누르세요' },
      { f: 's3a2_permnav', cap: '위쪽 "1. 필수 메시지 권한 추가"가 초록색 체크로 바뀌면 성공. 이제 왼쪽 "권한 및 기능"으로 가세요' },
      { f: 's3b_publish', cap: '목록에서 "instagram_business_content_publish"를 찾아 오른쪽 "추가"를 누르세요' },
      { f: 's3c_error', cap: '이런 오류가 떠도 잘못하신 게 아니에요. 새로고침하고 다시 누르면 됩니다' },
      { f: 's3d_ready', cap: '"테스트 준비 완료"로 바뀌면 성공' },
    ],
    body: '방금 만든 앱에 사진을 올릴 수 있는 권한을 켭니다. 이 단계를 건너뛰면 마지막에 사진이 올라가지 않아요.',
    tips: [
      '⚠️ instagram_business_content_publish 는 버튼으로 자동 추가되지 않아요. 직접 찾아서 추가해야 합니다. 이게 빠지면 마지막에 사진이 올라가지 않아요.',
      '"문제가 발생했습니다"가 떠도 잘못하신 게 아니에요. 확인 → 새로고침(F5) → 다시 "추가"를 누르면 대개 됩니다.',
    ],
    time: '4분',
  },
  {
    title: '내 계정을 연결하고 토큰 받기',
    shots: [
      { f: 's4_0_apisetup', cap: '앞 단계와 같은 화면입니다. 맨 위로 올려서 왼쪽 "Instagram 로그인이 포함된 API ..."를 누르세요' },
      { f: 's4_1_addaccount', cap: '아래로 내려 "2. 액세스 토큰 생성"의 "계정 추가"를 누르세요' },
      { f: 's4_2_continue', cap: '안내를 읽고 "계속"' },
      { f: 's4_3_role', cap: '맨 아래 "Instagram 테스터"를 고르세요' },
      { f: 's4_4_input', cap: '아래에 생긴 칸에 비즈니스로 바꾼 인스타그램 계정 이름을 치세요' },
      { f: 's4_5_pick', cap: '아래에 뜨는 프로필을 눌러서 고르세요. 글자만 쳐 놓으면 추가되지 않아요' },
      { f: 's4_6_add', cap: '이렇게 이름표가 생기면 "추가"를 누르세요' },
      { f: 's4_7_igsettings', cap: '이제 인스타그램으로 가서 방금 추가한 그 계정으로 로그인하고 설정을 엽니다. 왼쪽 목록을 아래로 내리세요' },
      { f: 's4_8_webperm', cap: '"앱 웹사이트 권한"을 누르세요' },
      { f: 's4_9_appsites', cap: '"앱 및 웹사이트"를 누르세요' },
      { f: 's4_10_tab', cap: '오른쪽 끝 "테스터 초대" 탭을 누르세요' },
      { f: 's4_11_accept', cap: '"수락"을 누르면 연결이 끝납니다' },
      { f: 's4_12_expand', cap: '다시 메타 개발자 사이트로 돌아와서, "2. 액세스 토큰 생성" 오른쪽 ∨를 누르세요' },
      { f: 's4_13_gentoken', cap: '내 계정이 보이면 그 옆 "토큰 생성"을 누르세요' },
      { f: 's4_14_login', cap: '인스타그램 로그인 창이 뜹니다. 비즈니스로 바꾼 인스타그램 계정으로 로그인하세요' },
      { f: 's4_15_allow', cap: '권한 화면은 그대로 두고 "허용"' },
      { f: 's4_16_token', cap: '"이해합니다"에 체크하면 토큰이 보여요. 오른쪽 "복사"를 누르고, 아래 "받은 토큰 넣기" 칸에 붙여 넣은 뒤 연결하기 버튼을 눌러주세요!' },
    ],
    body: '내 인스타그램 계정을 앱에 연결하고, 연결에 쓸 토큰을 받습니다. Meta 개발자 사이트와 인스타그램을 오가야 해서 조금 깁니다.',
    tips: [
      '초대를 수락하지 않으면 토큰 화면에 계정이 나오지 않아요.',
      '⚠️ 토큰은 한 번만 보여요. 창을 닫기 전에 복사해 두세요. 놓쳤으면 "토큰 생성"을 다시 눌러 새로 만들면 됩니다.',
      '권한 화면에서 Adflow 가 실제로 쓰는 건 "콘텐츠 액세스 및 게시" 하나예요. 댓글·메시지·인사이트는 꺼도 정상 작동하지만, 게시는 반드시 켜져 있어야 합니다.',
      '토큰은 60일 동안 쓸 수 있고, Adflow 가 만료 전에 알아서 갱신해요. 사장님이 다시 하실 일은 없습니다.',
      '토큰은 이 계정에 글을 올릴 수 있는 열쇠예요. 다른 사람에게 보여주지 마세요.',
    ],
    time: '10분',
  },
];

/** 한 단계의 화면 그림들. 파일이 없으면 그 자리만 조용히 비운다 —
 *  안내 문구만으로도 단계는 따라갈 수 있어서, 빈 상자를 남기는 것보다 낫다.
 *
 *  누르면 크게 열리는 이유: 메타 콘솔은 글씨가 작고 비슷한 항목이 많아, 줄어든 그림으로는
 *  어느 줄을 눌러야 하는지 보이지 않는다. */
function Shots({ shots, onZoom }) {
  const [gone, setGone] = useState([]);
  if (!shots?.length) return null;
  const live = shots.filter((s) => !gone.includes(s.f));
  if (!live.length) return null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {live.map((s) => {
        const src = `${import.meta.env.BASE_URL}instagram-guide/${s.f}.png`;
        return (
          <figure key={s.f} style={{ margin: 0, display: 'flex', flexDirection: 'column', gap: 5 }}>
            <img src={src} alt={s.cap} loading="lazy"
                 onError={() => setGone((g) => [...g, s.f])}
                 onClick={() => onZoom({ src, cap: s.cap })}
                 style={{
                   width: '100%', borderRadius: 10, border: `1px solid ${colors.cardBorder}`,
                   display: 'block', cursor: 'zoom-in',
                 }} />
            <figcaption style={{ fontSize: 12, lineHeight: '19px', color: colors.textSub }}>{s.cap}</figcaption>
          </figure>
        );
      })}
    </div>
  );
}


/** 크게 보기. 그림 밖이나 닫기를 누르면 닫힌다. */
function Zoom({ item, onClose }) {
  if (!item) return null;
  return (
    <div onClick={onClose}
         style={{
           position: 'fixed', inset: 0, zIndex: 50, background: 'rgba(17,19,21,.72)',
           display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
           gap: 10, padding: 16, cursor: 'zoom-out',
         }}>
      <img src={item.src} alt={item.cap}
           style={{ maxWidth: '100%', maxHeight: '82vh', borderRadius: 10, background: '#fff' }} />
      <span style={{ fontSize: 13, color: '#fff', textAlign: 'center', maxWidth: 680 }}>{item.cap}</span>
      <span style={{ fontSize: 12, color: 'rgba(255,255,255,.65)' }}>아무 곳이나 누르면 닫혀요</span>
    </div>
  );
}


/** 연결 성공. 화면 한가운데에서 분명하게 알린다.
 *
 *  확인을 누르면 왔던 화면(대개 완성된 광고)으로 돌려보낸다 — 여기서 할 일은 끝났는데
 *  안내 화면에 남겨 두면 "그래서 이제 뭘 하지" 하고 또 헤매게 된다. */
function Done({ msg, onClose, onConfirm }) {
  if (!msg) return null;
  return (
    <div onClick={onClose}
         style={{
           position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(17,19,21,.5)',
           display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20,
         }}>
      <div onClick={(e) => e.stopPropagation()}
           style={{
             background: '#fff', borderRadius: 18, padding: '30px 26px 22px', maxWidth: 360, width: '100%',
             display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10, textAlign: 'center',
           }}>
        <span style={{
          width: 56, height: 56, borderRadius: 999, background: colors.primary, color: '#fff',
          fontSize: 28, fontWeight: 800, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>✓</span>
        <span style={{ fontSize: 17, fontWeight: 800, letterSpacing: -.3 }}>{msg}</span>
        <span style={{ fontSize: 13.5, lineHeight: '21px', color: colors.textSub }}>
          이제 광고를 만든 뒤 <b>인스타에 올리기</b>를 누르면 바로 올라가요.
        </span>
        <PrimaryButton onClick={onConfirm} style={{ height: 46, width: '100%', marginTop: 6 }}>확인</PrimaryButton>
      </div>
    </div>
  );
}


const DONE_KEY = 'adflow.instagram.done';

/** 끝낸 단계 번호. 브라우저가 막아 두었거나 값이 깨졌으면 그냥 처음부터 보여준다 —
 *  진행 표시가 없다고 안내를 못 볼 이유는 없다. */
function loadDone() {
  try {
    const v = JSON.parse(localStorage.getItem(DONE_KEY) || '[]');
    return Array.isArray(v) ? v.filter((n) => Number.isInteger(n)) : [];
  } catch { return []; }
}

function saveDone(done) {
  try { localStorage.setItem(DONE_KEY, JSON.stringify(done)); } catch { /* 저장이 막혀도 그만 */ }
}


export default function InstagramSetup({ state, actions }) {
  const [status, setStatus] = useState(null);   // {connected, username, reason, saved}
  const [token, setToken] = useState('');
  const [busy, setBusy] = useState(false);
  const [zoom, setZoom] = useState(null);        // 크게 보는 화면 그림
  const [okMsg, setOkMsg] = useState('');        // 연결 성공 알림
  // 끝낸 단계와 지금 펼친 단계. 사장님은 이 화면과 메타·인스타 탭을 계속 오가고, 한 번에
  // 끝내지 못하고 나중에 이어 하기도 한다. 그래서 진행 상태를 브라우저에 남긴다 —
  // 서버에 둘 만한 값은 아니고(사장님 한 명의 화면 사정일 뿐), 지워져도 안내만 다시 펼쳐진다.
  const [done, setDone] = useState(() => loadDone());
  const [open, setOpen] = useState(() => {
    const d = loadDone();
    const next = STEPS.findIndex((_, i) => !d.includes(i));
    return next === -1 ? -1 : next;      // 다 했으면 전부 접어 둔다
  });

  const cards = useRef([]);        // 단계 카드 — 펼쳐진 곳으로 화면을 옮기려고 잡아 둔다
  const tokenBox = useRef(null);   // 마지막에 도착할 토큰 입력칸
  const firstPaint = useRef(true);

  const load = () => StoryboardAPI.instagramStatus().then(setStatus).catch(() => setStatus(null));
  useEffect(() => { load(); }, []);
  useEffect(() => { saveDone(done); }, [done]);

  /** 펼쳐진 단계로 화면을 옮긴다.
   *
   *  왜 필요한가 — 앞 단계가 접히면 그만큼 위쪽이 짧아져서, 가만히 있어도 페이지가 위로
   *  밀린다. 그대로 두면 "다 했어요"를 누를 때마다 사장님이 손으로 스크롤을 되감아야 한다.
   *  처음 화면을 열 때는 움직이지 않는다 — 이어 하는 사람에게도 맨 위 연결 상태부터
   *  보여주는 편이 덜 놀랍다. */
  useEffect(() => {
    if (firstPaint.current) { firstPaint.current = false; return; }
    const el = open < 0 ? tokenBox.current : cards.current[open];
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [open]);

  /** 이 단계를 끝내고 다음으로. 끝낸 단계는 접혀서 화면이 짧아진다.
   *
   *  **꼭 바로 다음 번호로 간다.** 한때 "아직 안 한 다음 단계"를 찾아가게 했더니, 끝낸
   *  1단계를 다시 펼쳐 보고 버튼을 누른 사장님이 4단계로 튕겨 나갔다. 버튼에 "다음
   *  단계로"라고 적혀 있으면 다음 번호가 나와야 한다. 이어 할 곳을 찾아 주는 일은 화면을
   *  처음 열 때 한 번이면 충분하다. */
  const finish = (i) => {
    setDone((d) => (d.includes(i) ? d : [...d, i]));
    setOpen(i + 1 < STEPS.length ? i + 1 : -1);
  };

  const connect = async () => {
    setBusy(true);
    try {
      const r = await StoryboardAPI.connectInstagram(token.trim());
      setStatus(r);
      setToken('');
      // 성공은 화면 한가운데에 크게 알린다 — 10분 걸린 일이 끝난 순간이라,
      // 아래쪽에 잠깐 떴다 사라지는 알림으로는 끝난 줄 모르고 계속 기다리게 된다.
      if (r.connected) setOkMsg(`@${r.username} 계정을 연결했어요`);
      else actions.toast('연결하지 못했어요');
    } catch (e) {
      actions.toast(String(e?.message || e) || '연결하지 못했어요');
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true);
    try {
      setStatus(await StoryboardAPI.disconnectInstagram());
      actions.toast('연결을 끊었어요');
    } catch (e) {
      actions.toast(String(e?.message || e) || '연결을 끊지 못했어요');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ padding: '18px 16px 40px', display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 560, margin: '0 auto' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={{ fontSize: 20, fontWeight: 800, letterSpacing: -.3 }}>인스타그램 계정 연결</span>
        <span style={{ fontSize: 13.5, lineHeight: '21px', color: colors.textSub }}>
          연결해 두면 만든 광고를 여기서 바로 인스타그램에 올릴 수 있어요. 처음 한 번만 하면 되고, 10분쯤 걸려요.
        </span>
      </div>

      {/* 지금 상태 — 맨 위에 둔다. 사장님이 가장 먼저 궁금한 건 "연결됐나"다. */}
      <div style={{
        border: `1px solid ${status?.connected ? colors.primary : colors.cardBorder}`, borderRadius: 14,
        background: status?.connected ? colors.onboardBg : '#fff', padding: '14px 16px',
        display: 'flex', flexDirection: 'column', gap: 6,
      }}>
        <span style={{ fontSize: 14, fontWeight: 800 }}>
          {status?.connected ? `연결됨 — @${status.username}` : '아직 연결되지 않았어요'}
        </span>
        {!status?.connected && status?.reason && (
          <span style={{ fontSize: 12.5, lineHeight: '19px', color: colors.textSub }}>{status.reason}</span>
        )}
        {status?.connected && status.days_left >= 0 && (
          <span style={{ fontSize: 12.5, lineHeight: '19px', color: colors.textSub }}>
            토큰은 {status.expires_at}까지 쓸 수 있어요(약 {status.days_left}일 남음). 만료가 가까워지면 서비스가 알아서 연장해요.
          </span>
        )}
        {status?.connected && (
          <SecondaryButton onClick={disconnect} disabled={busy} style={{ height: 40, marginTop: 6 }}>연결 끊기</SecondaryButton>
        )}
        {!status?.connected && status?.saved && (
          <span style={{ fontSize: 12.5, lineHeight: '19px', color: colors.textSub }}>
            전에 연결한 계정이 있지만 토큰이 만료된 것 같아요. 아래 5단계에서 토큰만 새로 받아 다시 연결해 주세요.
          </span>
        )}
      </div>

      {STEPS.map((s, i) => {
        const isDone = done.includes(i);
        const isOpen = open === i;
        return (
          <div key={s.title} ref={(el) => { cards.current[i] = el; }} style={{
            scrollMarginTop: 14,
            border: `1px solid ${isOpen ? colors.primary : colors.cardBorder}`, borderRadius: 14,
            padding: isOpen ? '16px 16px 18px' : '13px 16px',
            display: 'flex', flexDirection: 'column', gap: 10, background: '#fff',
          }}>
            {/* 제목 줄은 언제나 누를 수 있다 — 접은 단계를 다시 보고 싶을 때가 꼭 생긴다. */}
            <button type="button" onClick={() => setOpen(isOpen ? -1 : i)}
                    style={{
                      border: 0, background: 'none', padding: 0, cursor: 'pointer', textAlign: 'left',
                      display: 'flex', alignItems: 'center', gap: 8, width: '100%',
                    }}>
              <span style={{
                flex: 'none', width: 26, height: 26, borderRadius: 999,
                background: isDone ? colors.primary : colors.primarySoft,
                color: isDone ? '#fff' : colors.primarySoftText, fontSize: 13, fontWeight: 800,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>{isDone ? '✓' : i + 1}</span>
              {/* 제목 위에 "2단계 / 5" — 끝낸 단계는 동그라미가 ✓ 로 바뀌어 번호가 사라진다.
                  사장님이 지금 어디쯤인지는 늘 보여야 한다. */}
              <span style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: colors.textFaint, letterSpacing: .2 }}>
                  {i + 1}단계 / {STEPS.length}
                </span>
                <span style={{
                  fontSize: 15.5, fontWeight: 800,
                  color: isDone && !isOpen ? colors.textSub : colors.text,
                }}>{s.title}</span>
              </span>
              <span style={{ fontSize: 11.5, color: colors.textFaint, flex: 'none' }}>
                {isDone && !isOpen ? '다시 보기' : s.time}
              </span>
            </button>

            {isOpen && (
              <>
                <span style={{ fontSize: 13.5, lineHeight: '22px', color: colors.text }}>{s.body}</span>
                {s.link && (
                  <a href={s.link.href} target="_blank" rel="noreferrer"
                     style={{ fontSize: 13, fontWeight: 700, color: colors.primaryHover, textDecoration: 'none' }}>
                    {s.link.text} →
                  </a>
                )}
                <Shots shots={s.shots} onZoom={setZoom} />
                {/* 맨 아래는 유의사항만. 무엇을 누르는지는 그림 설명이 다 말했으니
                    여기서 또 말하면 두 번 읽게 된다. */}
                <span style={{ fontSize: 11.5, fontWeight: 700, color: colors.textFaint, letterSpacing: .2, marginTop: 2 }}>
                  알아두면 좋아요
                </span>
                <ul style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {s.tips.map((t) => (
                    <li key={t} style={{ fontSize: 12.5, lineHeight: '20px', color: colors.textSub }}>{t}</li>
                  ))}
                </ul>
                <SoftButton onClick={() => finish(i)} style={{ height: 44, marginTop: 2 }}>
                  {i === STEPS.length - 1
                    ? (isDone ? '토큰 넣으러 가기' : '다 했어요 — 토큰 넣으러 가기')
                    : (isDone ? '다음 단계 보기' : '다 했어요 — 다음 단계로')}
                </SoftButton>
              </>
            )}
          </div>
        );
      })}

      {/* 값 넣기 — 마지막 단계와 이어지도록 맨 아래에 둔다. */}
      <div ref={tokenBox} style={{
        scrollMarginTop: 14,
        border: `1px solid ${colors.cardBorder}`, borderRadius: 14, padding: '16px 16px 18px',
        display: 'flex', flexDirection: 'column', gap: 10, background: '#fff',
      }}>
        <span style={{ fontSize: 15.5, fontWeight: 800 }}>받은 토큰 넣기</span>
        <Label>액세스 토큰</Label>
        <TextInput value={token} onChange={(e) => setToken(e.target.value)}
                   placeholder="IGAA… 로 시작하는 긴 문자열" />
        <span style={{ fontSize: 12, lineHeight: '19px', color: colors.textFaint }}>
          토큰만 넣으면 돼요. 계정 번호는 저희가 인스타그램에 물어봐서 찾습니다.
          넣은 값이 맞는지 먼저 확인하고 저장해요 — 틀리면 저장하지 않고 이유를 알려드려요.
        </span>
        <PrimaryButton onClick={connect} disabled={busy || !token.trim()} style={{ height: 48 }}>
          {busy ? '확인하는 중이에요…' : '연결하기'}
        </PrimaryButton>
      </div>

      <SecondaryButton onClick={actions.back} style={{ height: 48 }}>돌아가기</SecondaryButton>
      <Zoom item={zoom} onClose={() => setZoom(null)} />
      <Done msg={okMsg} onClose={() => setOkMsg('')}
            onConfirm={() => { setOkMsg(''); actions.back(); }} />
    </div>
  );
}
