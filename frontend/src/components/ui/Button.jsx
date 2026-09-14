import { primaryButton, secondaryButton, softButton } from '../../theme.js';

export function PrimaryButton({ disabled, style, children, ...props }) {
  return (
    <button disabled={disabled} style={{ ...primaryButton(disabled), ...style }} {...props}>
      {children}
    </button>
  );
}

export function SecondaryButton({ style, children, ...props }) {
  return (
    <button style={{ ...secondaryButton, ...style }} {...props}>
      {children}
    </button>
  );
}

export function SoftButton({ style, children, ...props }) {
  return (
    <button style={{ ...softButton, ...style }} {...props}>
      {children}
    </button>
  );
}
