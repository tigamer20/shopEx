import Ionicons from '@expo/vector-icons/Ionicons';
import { ActivityIndicator, Pressable, StyleSheet } from 'react-native';

import { AppText } from '@/components/ui';
import type { UseLocationResult } from '@/hooks/useLocation';
import type { TranslationKey } from '@/i18n';
import { useT } from '@/i18n';
import { useTheme } from '@/theme';

export interface LocationChipProps {
  location: Pick<UseLocationResult, 'status' | 'refresh'>;
  radiusKm: number | null;
}

const STATUS_KEYS: Record<UseLocationResult['status'], TranslationKey> = {
  idle: 'common.location.allow',
  locating: 'common.location.locating',
  granted: 'common.location.current',
  denied: 'common.location.allow',
  unavailable: 'common.location.unavailable',
  error: 'common.location.error',
};

/** "Current location · 10 km radius" pill; tapping it asks for / refreshes the position. */
export function LocationChip({ location, radiusKm }: LocationChipProps) {
  const theme = useTheme();
  const t = useT();
  const { status, refresh } = location;
  const ok = status === 'granted';
  const label =
    ok && radiusKm !== null
      ? `${t(STATUS_KEYS[status])} · ${t('home.radius', { km: radiusKm })}`
      : t(STATUS_KEYS[status]);
  const accent = ok ? theme.colors.primary : theme.colors.danger;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityHint={t('home.location_hint')}
      accessibilityState={{ busy: status === 'locating' }}
      disabled={status === 'locating'}
      onPress={() => void refresh()}
      hitSlop={4}
      style={({ pressed }) => [
        styles.chip,
        {
          gap: theme.spacing.xs,
          paddingHorizontal: theme.spacing.md,
          borderRadius: theme.radius.pill,
          backgroundColor: theme.colors.surface,
          opacity: pressed ? 0.8 : 1,
        },
      ]}
    >
      {status === 'locating' ? (
        <ActivityIndicator size="small" color={theme.colors.primary} />
      ) : (
        <Ionicons name={ok ? 'location' : 'location-outline'} size={16} color={accent} />
      )}
      <AppText variant="label" numberOfLines={1} style={styles.label}>
        {label}
      </AppText>
      <Ionicons name={ok ? 'chevron-down' : 'refresh'} size={14} color={theme.colors.textMuted} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chip: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 36,
    maxWidth: '100%',
  },
  label: {
    flexShrink: 1,
  },
});
