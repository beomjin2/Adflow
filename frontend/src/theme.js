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

export function bgGradient(hue) {
  return `linear-gradient(135deg,hsl(${hue} 58% 92%),hsl(${(hue + 42) % 360} 52% 84%))`;
}

export function randomHue() {
  return Math.floor(Math.random() * 360);
}

export const inputStyle = {
  height: 44,
  borderRadius: 12,
  border: `1.5px solid ${colors.inputBorder}`,
  background: '#fff',
  color: colors.text,
  fontSize: 14.5,
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
  fontSize: 14.5,
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
  top: 6,
  right: 6,
  width: 24,
  height: 24,
  borderRadius: 8,
  border: 0,
  background: 'rgba(255,255,255,.92)',
  color: colors.text,
  fontSize: 13,
  cursor: 'pointer',
  boxShadow: '0 1px 3px rgba(0,0,0,.12)'
};
