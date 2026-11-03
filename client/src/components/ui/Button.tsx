import Ionicons from '@expo/vector-icons/Ionicons';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  View,
  type PressableProps,
  type StyleProp,
  type ViewStyle,
} from 'react-native';

import { useTheme, type Theme } from '@/theme';

import { AppText } from './AppText';
import type { IconName } from './icons';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'md' | 'lg';

export interface ButtonProps extends Omit<PressableProps, 'children' | 'style' | 'disabled'> {
  label: string;
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  disabled?: boolean;
  icon?: IconName;
  iconPosition?: 'left' | 'right';
  fullWidth?: boolean;
  style?: StyleProp<ViewStyle>;
}

interface VariantColors {
  background: string;
  pressed: string;
  foreground: string;
  border: string;
}

function variantColors(theme: Theme, variant: ButtonVariant): VariantColors {
  const { colors } = theme;
  switch (variant) {
    case 'primary':
      return { background: colors.primary, pressed: colors.primaryDark, foreground: colors.onPrimary, border: colors.primary };
    case 'secondary':
      return { background: colors.surface, pressed: colors.border, foreground: colors.text, border: colors.border };
    case 'ghost':
      return { background: 'transparent', pressed: colors.surface, foreground: colors.primary, border: 'transparent' };
    case 'danger':
      return { background: colors.danger, pressed: colors.danger, foreground: colors.onPrimary, border: colors.danger };
  }
}

const HEIGHTS: Record<ButtonSize, number> = { md: 48, lg: 56 };

/** Pill-shaped button: primary (sticky CTAs), secondary, ghost (inline actions) or danger. */
export function Button({
  label,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  icon,
  iconPosition = 'left',
  fullWidth = false,
  style,
  accessibilityLabel,
  ...rest
}: ButtonProps) {
  const theme = useTheme();
  const palette = variantColors(theme, variant);
  const inactive = disabled || loading;
  const iconElement = icon ? <Ionicons name={icon} size={20} color={palette.foreground} /> : null;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? label}
      accessibilityState={{ disabled: inactive, busy: loading }}
      disabled={inactive}
      style={({ pressed }) => [
        styles.base,
        {
          minHeight: HEIGHTS[size],
          borderRadius: theme.radius.pill,
          paddingHorizontal: size === 'lg' ? theme.spacing.xl : theme.spacing.lg,
          backgroundColor: pressed && !inactive ? palette.pressed : palette.background,
          borderColor: palette.border,
          opacity: disabled ? 0.5 : 1,
        },
        fullWidth ? styles.fullWidth : null,
        style,
      ]}
      {...rest}
    >
      {loading ? (
        <ActivityIndicator color={palette.foreground} />
      ) : (
        <View style={[styles.content, { gap: theme.spacing.sm }]}>
          {iconPosition === 'left' ? iconElement : null}
          <AppText
            variant="subtitle"
            numberOfLines={1}
            style={{ color: palette.foreground, fontWeight: theme.fontWeight.heavy }}
          >
            {label}
          </AppText>
          {iconPosition === 'right' ? iconElement : null}
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
  },
  fullWidth: {
    alignSelf: 'stretch',
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
});
