import type { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import { AppText, Logo, Screen } from '@/components/ui';
import { useTheme } from '@/theme';

import { LanguageToggle } from './LanguageToggle';

export interface AuthScaffoldProps {
  title: string;
  subtitle: string;
  children: ReactNode;
  /** Sticky area: submit button and the link to the other auth screen. */
  footer: ReactNode;
}

/** Shared frame of the login and sign-up screens: language switch, logo + slogan, heading. */
export function AuthScaffold({ title, subtitle, children, footer }: AuthScaffoldProps) {
  const theme = useTheme();

  return (
    <Screen edges={['top', 'left', 'right', 'bottom']} footer={<View style={styles.column}>{footer}</View>}>
      <View style={[styles.column, { gap: theme.spacing.xl }]}>
        <LanguageToggle />
        <Logo size="lg" showSlogan style={{ marginVertical: theme.spacing.md }} />
        <View style={{ gap: theme.spacing.xs }}>
          <AppText variant="title">{title}</AppText>
          <AppText variant="caption">{subtitle}</AppText>
        </View>
        <View style={{ gap: theme.spacing.lg }}>{children}</View>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  column: {
    width: '100%',
    maxWidth: 480,
    alignSelf: 'center',
    gap: 8,
  },
});
