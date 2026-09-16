import { primaryButton, secondaryButton, softButton } from '../../theme.js';

/** 못 누르는 버튼은 눌러봐도 반응이 없으면 안 된다 — 흐리게 해서 못 누른다는 걸 먼저 보여준다. */
const dim = (disabled) => (disabled ? { opacity: 0.45, cursor: 'not-allowed' } : null);

export function PrimaryButton({ disabled, style, children, ...props }) {
  return (
    <button disabled={disabled} style={{ ...primaryButton(disabled), ...style }} {...props}>
      {children}
    </button>
  );
}

export function SecondaryButton({ disabled, style, children, ...props }) {
  return (
    <button disabled={disabled} style={{ ...secondaryButton, ...style, ...dim(disabled) }} {...props}>
      {children}
    </button>
  );
}

export function SoftButton({ disabled, style, children, ...props }) {
  return (
    <button disabled={disabled} style={{ ...softButton, ...style, ...dim(disabled) }} {...props}>
      {children}
    </button>
  );
}
