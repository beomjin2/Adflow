import { colors, inputStyle, readOnlyInputStyle, textareaStyle, readOnlyTextareaStyle } from '../../theme.js';

export function Label({ children }) {
  return <span style={{ fontSize: 13, fontWeight: 700, color: colors.textSub }}>{children}</span>;
}

export function TextInput({ readOnly, style, ...props }) {
  return <input readOnly={readOnly} style={{ ...(readOnly ? readOnlyInputStyle : inputStyle), ...style }} {...props} />;
}

export function TextArea({ readOnly, style, ...props }) {
  return <textarea readOnly={readOnly} style={{ ...(readOnly ? readOnlyTextareaStyle : textareaStyle), ...style }} {...props} />;
}

export function Select({ style, children, ...props }) {
  return <select style={{ ...inputStyle, ...style }} {...props}>{children}</select>;
}
