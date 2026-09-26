import { useEffect, useState } from 'react';
import { colors } from '../theme.js';
import { PrimaryButton, SecondaryButton, SoftButton } from '../components/ui/Button.jsx';
import { TextInput, Label } from '../components/ui/Field.jsx';
import { StoryboardAPI } from '../api/client.js';

/** 인스타그램 계정 연결 안내 — 사장님이 혼자 따라 할 수 있게 만드는 게 목적이다.
 *
 *  왜 이렇게 길게 쓰나: 인스타 자동 게시는 Meta 개발자 콘솔에서 앱을 만들고 토큰을 받아야
 *  한다. 개발자용 화면이라 처음 보는 사장님은 어디를 눌러야 할지 알 수 없다. 그래서
 *  ① 한 화면에 한 단계씩, ② 무엇을 찾아야 하는지(버튼 글자)까지 적고, ③ 스크린샷 자리를
 *  비워 뒀다. 실제 스크린샷은 public/instagram-guide/step1.png … step5.png 로 넣으면
 *  자동으로 여기 붙는다(없으면 안내 상자만 보인다).
 *
 *  값을 저장하기 전에 인스타에 한 번 물어본다(POST /instagram/connect) — 잘못된 값을
 *  저장해 두면 사장님은 나중에 게시를 눌러 보고서야 알게 된다. */

const STEPS = [
  {
    title: '인스타그램을 비즈니스 계정으로 바꾸기',
    body: '인스타그램 앱에서 설정 → 계정 유형 및 도구 → 프로페셔널 계정으로 전환 → 비즈니스를 고르세요.',
    tips: [
      '중간에 "페이스북 페이지 연결" 안내가 나오면 건너뛰기를 눌러도 됩니다.',
      '사업자등록증은 필요 없어요.',
      '이미 비즈니스 계정이면 이 단계는 넘어가세요.',
    ],
    time: '2분',
  },
  {
    title: 'Meta 개발자 사이트에서 앱 만들기',
    body: 'developers.facebook.com 에 로그인하고 내 앱 → 앱 만들기를 누르세요. 앱 유형은 비즈니스를 고르고, 이름은 가게 이름처럼 아무거나 적으면 됩니다.',
    tips: ['페이스북 계정이 필요해요. 없으면 새로 만들면 됩니다.'],
    time: '3분',
    link: { href: 'https://developers.facebook.com', text: 'developers.facebook.com 열기' },
  },
  {
    title: '앱에 인스타그램 기능 추가하기',
    body: '만든 앱 화면에서 제품 추가 → Instagram 을 찾아 설정을 누르세요. 방식은 "Instagram API with Instagram Login" 입니다.',
    tips: ['비슷한 이름이 여러 개 보이면 Instagram Login 이 들어간 쪽을 고르세요.'],
    time: '2분',
  },
  {
    title: '내 계정을 테스터로 등록하기',
    body: '앱 역할 → 역할 추가 → Instagram 테스터로 1단계의 계정을 추가하세요. 그다음 인스타그램 앱의 설정 → 웹사이트 권한에서 초대를 수락하면 됩니다.',
    tips: ['초대 수락을 안 하면 다음 단계에서 토큰이 안 나와요.'],
    time: '3분',
  },
  {
    title: '연결에 쓸 두 값 받기',
    body: 'Instagram → API 설정 화면에서 액세스 토큰 생성(또는 계정 추가)을 누르고 인스타그램으로 로그인하세요. 나온 토큰을 복사해 아래에 붙여 넣으면 됩니다.',
    tips: [
      '사용자 ID는 같은 화면에 함께 표시돼요. 안 보이면 토큰만 넣고 연결하기를 눌러도 됩니다.',
      '토큰은 약 1시간이 지나면 만료돼요. 만료되면 이 화면에서 다시 연결하면 됩니다.',
      '토큰은 이 계정에 글을 올릴 수 있는 열쇠예요. 다른 사람에게 보여주지 마세요.',
    ],
    time: '3분',
  },
];

/** 스크린샷 자리. 파일이 없으면 무엇을 넣어야 하는지 적힌 상자를 보여준다 —
 *  빈 화면보다 낫고, 스크린샷을 채워 넣을 사람도 뭘 찍어야 할지 알 수 있다. */
function Shot({ n, alt }) {
  const [ok, setOk] = useState(true);
  const src = `${import.meta.env.BASE_URL}instagram-guide/step${n}.png`;
  if (!ok) {
    return (
      <div style={{
        border: `1.5px dashed ${colors.cardBorder}`, borderRadius: 12, padding: '18px 14px',
        fontSize: 12.5, lineHeight: '19px', color: colors.textFaint, background: colors.softBg, textAlign: 'center',
      }}>
        화면 그림 자리 — {alt}
        <br />
        <span style={{ fontSize: 11.5 }}>public/instagram-guide/step{n}.png 를 넣으면 여기에 보여요</span>
      </div>
    );
  }
  return (
    <img src={src} alt={alt} onError={() => setOk(false)}
         style={{ width: '100%', borderRadius: 12, border: `1px solid ${colors.cardBorder}`, display: 'block' }} />
  );
}

export default function InstagramSetup({ state, actions }) {
  const [status, setStatus] = useState(null);   // {connected, username, reason, saved}
  const [userId, setUserId] = useState('');
  const [token, setToken] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState([]);          // 사장님이 직접 체크한 단계

  const load = () => StoryboardAPI.instagramStatus().then(setStatus).catch(() => setStatus(null));
  useEffect(() => { load(); }, []);

  const toggle = (i) => setDone((d) => (d.includes(i) ? d.filter((x) => x !== i) : [...d, i]));

  const connect = async () => {
    setBusy(true);
    try {
      const r = await StoryboardAPI.connectInstagram(userId.trim(), token.trim());
      setStatus(r);
      setToken('');
      actions.toast(r.connected ? `@${r.username} 계정을 연결했어요` : '연결하지 못했어요');
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

      {STEPS.map((s, i) => (
        <div key={s.title} style={{
          border: `1px solid ${colors.cardBorder}`, borderRadius: 14, padding: '16px 16px 18px',
          display: 'flex', flexDirection: 'column', gap: 10, background: '#fff',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{
              flex: 'none', width: 26, height: 26, borderRadius: 999, background: colors.primarySoft,
              color: colors.primarySoftText, fontSize: 13, fontWeight: 800,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>{i + 1}</span>
            <span style={{ fontSize: 15.5, fontWeight: 800, flex: 1 }}>{s.title}</span>
            <span style={{ fontSize: 11.5, color: colors.textFaint, flex: 'none' }}>{s.time}</span>
          </div>
          <span style={{ fontSize: 13.5, lineHeight: '22px', color: colors.text }}>{s.body}</span>
          {s.link && (
            <a href={s.link.href} target="_blank" rel="noreferrer"
               style={{ fontSize: 13, fontWeight: 700, color: colors.primaryHover, textDecoration: 'none' }}>
              {s.link.text} →
            </a>
          )}
          <Shot n={i + 1} alt={s.title} />
          <ul style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 4 }}>
            {s.tips.map((t) => (
              <li key={t} style={{ fontSize: 12.5, lineHeight: '20px', color: colors.textSub }}>{t}</li>
            ))}
          </ul>
          <label style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 13, color: colors.textSub, cursor: 'pointer' }}>
            <input type="checkbox" checked={done.includes(i)} onChange={() => toggle(i)} />
            여기까지 했어요
          </label>
        </div>
      ))}

      {/* 값 넣기 — 마지막 단계와 이어지도록 맨 아래에 둔다. */}
      <div style={{
        border: `1px solid ${colors.cardBorder}`, borderRadius: 14, padding: '16px 16px 18px',
        display: 'flex', flexDirection: 'column', gap: 10, background: '#fff',
      }}>
        <span style={{ fontSize: 15.5, fontWeight: 800 }}>받은 값 넣기</span>
        <Label>인스타그램 사용자 ID</Label>
        <TextInput value={userId} onChange={(e) => setUserId(e.target.value)}
                   placeholder="예: 17841000000000000" inputMode="numeric" />
        <Label>액세스 토큰</Label>
        <TextInput value={token} onChange={(e) => setToken(e.target.value)}
                   placeholder="IGAA… 로 시작하는 긴 문자열" />
        <span style={{ fontSize: 12, lineHeight: '19px', color: colors.textFaint }}>
          넣은 값이 맞는지 인스타그램에 먼저 물어보고 저장해요. 틀리면 저장하지 않고 이유를 알려드려요.
        </span>
        <PrimaryButton onClick={connect} disabled={busy || !userId.trim() || !token.trim()} style={{ height: 48 }}>
          {busy ? '확인하는 중이에요…' : '연결하기'}
        </PrimaryButton>
      </div>

      <SoftButton onClick={load} style={{ height: 44 }}>연결 상태 다시 확인</SoftButton>
      <SecondaryButton onClick={actions.back} style={{ height: 48 }}>돌아가기</SecondaryButton>
    </div>
  );
}
