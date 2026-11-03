import { Text, type TextProps } from 'react-native';

import { useTheme, type ColorName, type TextVariant } from '@/theme';

export interface AppTextProps extends TextProps {
  variant?: TextVariant;
  /** Theme colour token; defaults to `textMuted` for captions and small print, else `text`. */
  color?: ColorName;
  align?: 'auto' | 'left' | 'center' | 'right';
}

const HEADER_VARIANTS: readonly TextVariant[] = ['display', 'title', 'heading'];
const MUTED_VARIANTS: readonly TextVariant[] = ['caption', 'small'];

/** Themed text. Display/title/heading variants are announced as headers by screen readers. */
export function AppText({ variant = 'body', color, align, style, accessibilityRole, ...rest }: AppTextProps) {
  const theme = useTheme();
  const colorName = color ?? (MUTED_VARIANTS.includes(variant) ? 'textMuted' : 'text');
  return (
    <Text
      accessibilityRole={accessibilityRole ?? (HEADER_VARIANTS.includes(variant) ? 'header' : undefined)}
      style={[theme.typography[variant], { color: theme.colors[colorName] }, align ? { textAlign: align } : null, style]}
      {...rest}
    />
  );
}
