import Ionicons from '@expo/vector-icons/Ionicons';
import { Pressable, StyleSheet, type StyleProp, type ViewStyle } from 'react-native';

import { useTheme } from '@/theme';

import { AppText } from './AppText';
import type { IconName } from './icons';

export interface ChipProps {
  label: string;
  selected?: boolean;
  onPress?: () => void;
  icon?: IconName;
  disabled?: boolean;
  accessibilityLabel?: string;
  style?: StyleProp<ViewStyle>;
}

/** Selectable pill (sections, filters, segmented choices). */
export function Chip({ label, selected = false, onPress, icon, disabled = false, accessibilityLabel, style }: ChipProps) {
  const theme = useTheme();
  const foreground = selected ? theme.colors.onPrimary : theme.colors.text;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? label}
      accessibilityState={{ selected, disabled }}
      disabled={disabled}
      onPress={onPress}
      hitSlop={4}
      style={({ pressed }) => [
        styles.base,
        {
          gap: theme.spacing.xs,
          borderRadius: theme.radius.pill,
          paddingHorizontal: theme.spacing.lg,
          backgroundColor: selected ? theme.colors.primary : theme.colors.surface,
          borderColor: selected ? theme.colors.primary : theme.colors.border,
          opacity: disabled ? 0.5 : pressed ? 0.85 : 1,
        },
        style,
      ]}
    >
      {icon ? <Ionicons name={icon} size={16} color={foreground} /> : null}
      <AppText variant="label" style={{ color: foreground }} numberOfLines={1}>
        {label}
      </AppText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight: 36,
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
  },
});
