import Ionicons from '@expo/vector-icons/Ionicons';
import { Pressable, StyleSheet, type StyleProp, type ViewStyle } from 'react-native';

import { useTheme, type ColorName } from '@/theme';

import type { IconName } from './icons';

export type IconButtonVariant = 'plain' | 'tonal' | 'filled';

export interface IconButtonProps {
  icon: IconName;
  onPress: () => void;
  /** Required: icon-only controls need a spoken label. */
  accessibilityLabel: string;
  accessibilityHint?: string;
  variant?: IconButtonVariant;
  /** Icon colour for plain/tonal variants (default `text`). */
  color?: ColorName;
  size?: number;
  disabled?: boolean;
  selected?: boolean;
  style?: StyleProp<ViewStyle>;
}

/** Round icon-only button with a 44 pt minimum touch target (e.g. the "i" button). */
export function IconButton({
  icon,
  onPress,
  accessibilityLabel,
  accessibilityHint,
  variant = 'plain',
  color = 'text',
  size = 22,
  disabled = false,
  selected,
  style,
}: IconButtonProps) {
  const theme = useTheme();
  const background =
    variant === 'filled' ? theme.colors.primary : variant === 'tonal' ? theme.colors.surface : 'transparent';
  const foreground = variant === 'filled' ? theme.colors.onPrimary : theme.colors[color];

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityHint={accessibilityHint}
      accessibilityState={{ disabled, selected }}
      disabled={disabled}
      onPress={onPress}
      hitSlop={6}
      style={({ pressed }) => [
        styles.base,
        {
          backgroundColor: background,
          borderRadius: theme.radius.pill,
          opacity: disabled ? 0.4 : pressed ? 0.7 : 1,
        },
        style,
      ]}
    >
      <Ionicons name={icon} size={size} color={foreground} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minWidth: 44,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
