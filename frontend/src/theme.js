export const colors = {
  bg: '#F6F8F9',
  panelBg: '#fff',
  text: '#2B2F36',
  textSub: '#6A7077',
  textFaint: '#979CA2',
  primary: '#16A06B',
  primaryHover: '#138A5C',
  primarySoft: '#E6F7EF',
  primarySoftText: '#2E6B4E',
  onboardBg: '#F1FBF6',
  onboardBorder: '#CFEFE0',
  cardBorder: '#E8EAEC',
  inputBorder: '#DBDEE1',
  softBg: '#EFF2F4',
  warnBg: '#FFF6E6',
  warnBorder: '#F0DCB4',
  warnText: '#7A5C15',
  warnText2: '#8A6A20',
  warnAccent: '#C9912B',
  chatMeBg: '#16A06B',
  dark: '#2B2F36'
};

// 가짜 이미지를 만들던 hue 그라디언트(bgGradient/randomHue)는 제거했다. 그림이 없으면
// 없다고 보여준다 — 색깔 사각형을 대신 놓으면 사장님은 그게 자기 그림인 줄 안다.

/** 손가락으로 누르는 최소 크기. 사장님은 가게에서 폰으로 쓴다. */
export const TAP = 48;

export const font = {
  body: 16,      // 본문은 16 아래로 내리지 않는다 (iOS에서 입력 시 화면이 확대된다)
  caption: 14,
  label: 13,
};

export const inputStyle = {
  height: TAP,
  borderRadius: 12,
  border: `1.5px solid ${colors.inputBorder}`,
  background: '#fff',
  color: colors.text,
  fontSize: font.body,
  padding: '0 14px',
  width: '100%',
  minWidth: 0
};

export const readOnlyInputStyle = {
  ...inputStyle,
  background: colors.bg,
  color: colors.textSub
};

export const textareaStyle = {
  minHeight: 84,
  borderRadius: 12,
  border: `1.5px solid ${colors.inputBorder}`,
  background: '#fff',
  color: colors.text,
  fontSize: font.body,
  padding: '11px 14px',
  width: '100%',
  resize: 'vertical',
  lineHeight: '21px'
};

export const readOnlyTextareaStyle = {
  ...textareaStyle,
  background: colors.bg,
  color: colors.textSub
};

export const primaryButton = (disabled) => ({
  height: 52,
  borderRadius: 12,
  border: 0,
  background: colors.primary,
  color: '#fff',
  fontSize: 16,
  fontWeight: 700,
  cursor: disabled ? 'not-allowed' : 'pointer',
  boxShadow: disabled ? 'none' : '0 6px 12px rgba(22,160,107,.32)',
  opacity: disabled ? 0.45 : 1
});

export const secondaryButton = {
  height: 52,
  borderRadius: 12,
  border: `1.5px solid ${colors.inputBorder}`,
  background: '#fff',
  color: colors.text,
  fontSize: 16,
  fontWeight: 700,
  cursor: 'pointer'
};

export const softButton = {
  height: 52,
  borderRadius: 12,
  border: 0,
  background: colors.softBg,
  color: colors.text,
  fontSize: 15,
  fontWeight: 700,
  cursor: 'pointer'
};

export const cardBase = {
  textAlign: 'left',
  background: '#fff',
  border: `1px solid ${colors.cardBorder}`,
  borderRadius: 16,
  padding: 18,
  display: 'flex',
  flexDirection: 'column',
  gap: 7,
  boxShadow: '0 2px 6px rgba(20,28,36,.05)'
};

export const rerollButtonStyle = {
  position: 'absolute',
  top: 5,
  right: 5,
  width: 28,        // 24px는 손가락으로 못 누른다
  height: 28,
  borderRadius: 9,
  border: 0,
  background: 'rgba(255,255,255,.95)',
  color: colors.text,
  fontSize: 15,
  lineHeight: '28px',
  textAlign: 'center',
  cursor: 'pointer',
  boxShadow: '0 1px 4px rgba(0,0,0,.16)'
};
