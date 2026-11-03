import Ionicons from '@expo/vector-icons/Ionicons';
import { useState, type Ref } from 'react';
import { Pressable, StyleSheet, View, type TextInputInstance } from 'react-native';

import { AppText, TextField, type TextFieldProps } from '@/components/ui';
import { useT } from '@/i18n';
import { useTheme } from '@/theme';

export interface PasswordFieldProps extends Omit<TextFieldProps, 'secureTextEntry'> {
  ref?: Ref<TextInputInstance>;
}

/** Password input with a show / hide switch under it. */
export function PasswordField({ ref, ...rest }: PasswordFieldProps) {
  const theme = useTheme();
  const t = useT();
  const [visible, setVisible] = useState(false);
  const toggleLabel = visible ? t('auth.hide_password') : t('auth.show_password');

  return (
    <View style={{ gap: theme.spacing.xs }}>
      <TextField
        ref={ref}
        secureTextEntry={!visible}
        autoCapitalize="none"
        autoCorrect={false}
        spellCheck={false}
        {...rest}
      />
      <Pressable
        accessibilityRole="switch"
        accessibilityLabel={t('auth.show_password')}
        accessibilityState={{ checked: visible }}
        onPress={() => setVisible((value) => !value)}
        hitSlop={8}
        style={[styles.toggle, { gap: theme.spacing.xs }]}
      >
        <Ionicons name={visible ? 'eye-off-outline' : 'eye-outline'} size={16} color={theme.colors.primary} />
        <AppText variant="label" color="primary">
          {toggleLabel}
        </AppText>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  toggle: {
    alignSelf: 'flex-end',
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 32,
  },
});
