import Ionicons from '@expo/vector-icons/Ionicons';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { useT } from '@/i18n';
import { useTheme } from '@/theme';

import { AppText } from './AppText';
import { Button } from './Button';

export interface ErrorBannerProps {
  /** Already-translated message, e.g. `t(errorMessageKey(error))`. */
  message: string;
  onRetry?: () => void;
  /** Defaults to "Try again". */
  retryLabel?: string;
  style?: StyleProp<ViewStyle>;
}

/** Inline error with an optional retry action; announced to screen readers. */
export function ErrorBanner({ message, onRetry, retryLabel, style }: ErrorBannerProps) {
  const theme = useTheme();
  const t = useT();

  return (
    <View
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
      style={[
        styles.container,
        {
          gap: theme.spacing.md,
          padding: theme.spacing.md,
          borderRadius: theme.radius.md,
          borderColor: theme.colors.danger,
          backgroundColor: theme.colors.surface,
        },
        style,
      ]}
    >
      <View style={[styles.row, { gap: theme.spacing.sm }]}>
        <Ionicons name="alert-circle" size={20} color={theme.colors.danger} />
        <AppText variant="caption" color="text" style={styles.message}>
          {message}
        </AppText>
      </View>
      {onRetry ? (
        <Button
          label={retryLabel ?? t('common.actions.retry')}
          variant="secondary"
          icon="refresh"
          onPress={onRetry}
          style={styles.retry}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderWidth: 1,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  message: {
    flex: 1,
  },
  retry: {
    alignSelf: 'flex-start',
  },
});
