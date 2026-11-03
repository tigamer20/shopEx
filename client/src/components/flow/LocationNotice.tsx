import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { AppText, ErrorBanner } from '@/components/ui';
import type { LocationStatus } from '@/hooks/useLocation';
import { useT, type TranslationKey } from '@/i18n';
import { useTheme } from '@/theme';

export interface LocationNoticeProps {
  status: LocationStatus;
  /** Screen-specific reason the position is needed (shown when it is missing). */
  reasonKey: TranslationKey;
  onRetry: () => void;
}

const STATUS_KEYS: Partial<Record<LocationStatus, TranslationKey>> = {
  denied: 'common.location.denied',
  unavailable: 'common.location.unavailable',
  error: 'common.location.error',
};

/** Shows "locating…" or why the position is missing, with a retry; renders nothing once granted. */
export function LocationNotice({ status, reasonKey, onRetry }: LocationNoticeProps) {
  const theme = useTheme();
  const t = useT();

  if (status === 'granted') {
    return null;
  }
  if (status === 'locating') {
    return (
      <View style={[styles.row, { gap: theme.spacing.sm }]} accessibilityLiveRegion="polite">
        <ActivityIndicator color={theme.colors.primary} />
        <AppText variant="caption">{t('common.location.locating')}</AppText>
      </View>
    );
  }
  const statusKey = STATUS_KEYS[status];
  const message = statusKey ? `${t(reasonKey)} ${t(statusKey)}` : t(reasonKey);
  return <ErrorBanner message={message} onRetry={onRetry} retryLabel={t('common.location.allow')} />;
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
  },
});
