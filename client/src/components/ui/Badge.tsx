import Ionicons from '@expo/vector-icons/Ionicons';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { lightTheme, useTheme, type Theme } from '@/theme';

import { AppText } from './AppText';
import type { IconName } from './icons';

export type BadgeTone = 'primary' | 'sale' | 'success' | 'warning' | 'danger' | 'neutral';

export interface BadgeProps {
  label: string;
  tone?: BadgeTone;
  icon?: IconName;
  style?: StyleProp<ViewStyle>;
}

function toneColors(theme: Theme, tone: BadgeTone): { background: string; foreground: string } {
  const { colors } = theme;
  switch (tone) {
    case 'primary':
      return { background: colors.primary, foreground: colors.onPrimary };
    case 'sale':
      return { background: colors.badgeSale, foreground: colors.onPrimary };
    case 'success':
      return { background: colors.success, foreground: colors.onPrimary };
    case 'warning':
      // Dark text keeps contrast on the amber background in both schemes.
      return { background: colors.warning, foreground: lightTheme.colors.text };
    case 'danger':
      return { background: colors.danger, foreground: colors.onPrimary };
    case 'neutral':
      return { background: colors.surface, foreground: colors.textMuted };
  }
}

/** Small status label: "On sale", "Demo", "Organic"... */
export function Badge({ label, tone = 'neutral', icon, style }: BadgeProps) {
  const theme = useTheme();
  const { background, foreground } = toneColors(theme, tone);

  return (
    <View
      style={[
        styles.base,
        {
          backgroundColor: background,
          borderRadius: theme.radius.pill,
          paddingHorizontal: theme.spacing.sm,
          gap: theme.spacing.xs,
        },
        style,
      ]}
    >
      {icon ? <Ionicons name={icon} size={12} color={foreground} /> : null}
      <AppText variant="small" style={{ color: foreground, fontWeight: theme.fontWeight.semibold }} numberOfLines={1}>
        {label}
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  base: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 2,
  },
});
