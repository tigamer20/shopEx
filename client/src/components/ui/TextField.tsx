import { useState, type Ref } from 'react';
import {
  StyleSheet,
  TextInput,
  View,
  type StyleProp,
  type TextInputInstance,
  type TextInputProps,
  type ViewStyle,
} from 'react-native';

import { useTheme } from '@/theme';

import { AppText } from './AppText';

export interface TextFieldProps extends TextInputProps {
  label: string;
  /** Validation message; also turns the border red. */
  error?: string | null;
  hint?: string;
  containerStyle?: StyleProp<ViewStyle>;
  /** Lets forms focus the next field (`ref.current?.focus()`). */
  ref?: Ref<TextInputInstance>;
}

/** Labelled text input with error and hint text. */
export function TextField({
  label,
  error,
  hint,
  containerStyle,
  style,
  onFocus,
  onBlur,
  editable = true,
  ref,
  ...rest
}: TextFieldProps) {
  const theme = useTheme();
  const [focused, setFocused] = useState(false);
  const borderColor = error ? theme.colors.danger : focused ? theme.colors.primary : theme.colors.border;

  return (
    <View style={[{ gap: theme.spacing.xs }, containerStyle]}>
      <AppText variant="label">{label}</AppText>
      <TextInput
        ref={ref}
        accessibilityLabel={label}
        accessibilityHint={error ?? hint}
        accessibilityState={{ disabled: !editable }}
        editable={editable}
        placeholderTextColor={theme.colors.textMuted}
        onFocus={(event) => {
          setFocused(true);
          onFocus?.(event);
        }}
        onBlur={(event) => {
          setFocused(false);
          onBlur?.(event);
        }}
        style={[
          styles.input,
          theme.typography.body,
          {
            color: theme.colors.text,
            backgroundColor: theme.colors.surface,
            borderColor,
            borderRadius: theme.radius.md,
            paddingHorizontal: theme.spacing.lg,
            opacity: editable ? 1 : 0.6,
          },
          style,
        ]}
        {...rest}
      />
      {error ? (
        <AppText variant="caption" color="danger" accessibilityRole="alert" accessibilityLiveRegion="polite">
          {error}
        </AppText>
      ) : hint ? (
        <AppText variant="caption">{hint}</AppText>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  input: {
    minHeight: 48,
    borderWidth: 1,
  },
});
