import { colors, inputStyle, readOnlyInputStyle, textareaStyle, readOnlyTextareaStyle } from '../../theme.js';

export function Label({ children }) {
  return <span style={{ fontSize: 14, fontWeight: 700, color: colors.textSub, lineHeight: '20px' }}>{children}</span>;
}

export function TextInput({ readOnly, style, ...props }) {
  return <input readOnly={readOnly} style={{ ...(readOnly ? readOnlyInputStyle : inputStyle), ...style }} {...props} />;
}

export function TextArea({ readOnly, style, ...props }) {
  return <textarea readOnly={readOnly} style={{ ...(readOnly ? readOnlyTextareaStyle : textareaStyle), ...style }} {...props} />;
}

/** 고르지 않은 상태(value='')를 꼭 첫 항목으로 둔다. placeholder 없이 목록만 주면
 *  브라우저가 첫 항목을 보여줘서, 사장님은 고른 적 없는 값이 이미 골라진 걸로 본다. */
export function Select({ style, placeholder, children, ...props }) {
  const unset = !props.value;
  return (
    <select style={{ ...inputStyle, color: unset ? colors.textFaint : colors.text, ...style }} {...props}>
      {placeholder && <option value="">{placeholder}</option>}
      {children}
    </select>
  );
}
