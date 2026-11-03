/**
 * Design tokens (ARCHITECTURE §5 "Design system").
 * Food-delivery feel: white surfaces, bold black type, one warm accent, large rounded cards.
 */
import { useColorScheme } from 'react-native';

export interface ThemeColors {
  primary: string;
  primaryDark: string;
  onPrimary: string;
  background: string;
  surface: string;
  card: string;
  text: string;
  textMuted: string;
  border: string;
  success: string;
  warning: string;
  danger: string;
  badgeSale: string;
}

const lightColors: ThemeColors = {
  primary: '#F2542D',
  primaryDark: '#C8401E',
  onPrimary: '#FFFFFF',
  background: '#FFFFFF',
  surface: '#F5F5F5',
  card: '#FFFFFF',
  text: '#191919',
  textMuted: '#6B6B6B',
  border: '#E6E6E6',
  success: '#10A35A',
  warning: '#E8A317',
  danger: '#D93025',
  badgeSale: '#F2542D',
};

// Dark mode only overrides what the spec lists; every other token is shared with light mode.
const darkColors: ThemeColors = {
  ...lightColors,
  primary: '#FF6A43',
  background: '#121212',
  surface: '#1E1E1E',
  card: '#1A1A1A',
  text: '#F5F5F5',
  textMuted: '#A3A3A3',
  border: '#2E2E2E',
};

export const radius = { sm: 8, md: 12, lg: 16, xl: 24, pill: 999 } as const;

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;

export const fontSize = { xs: 12, sm: 14, md: 16, lg: 20, xl: 28, xxl: 34 } as const;

export const fontWeight = { regular: '400', semibold: '600', heavy: '800' } as const;

export interface TypographyStyle {
  fontSize: number;
  lineHeight: number;
  fontWeight: (typeof fontWeight)[keyof typeof fontWeight];
}

/** Text variants used by `AppText`. The system font is used everywhere. */
export const typography = {
  display: { fontSize: fontSize.xxl, lineHeight: 40, fontWeight: fontWeight.heavy },
  title: { fontSize: fontSize.xl, lineHeight: 34, fontWeight: fontWeight.heavy },
  heading: { fontSize: fontSize.lg, lineHeight: 26, fontWeight: fontWeight.heavy },
  subtitle: { fontSize: fontSize.md, lineHeight: 22, fontWeight: fontWeight.semibold },
  body: { fontSize: fontSize.md, lineHeight: 22, fontWeight: fontWeight.regular },
  label: { fontSize: fontSize.sm, lineHeight: 20, fontWeight: fontWeight.semibold },
  caption: { fontSize: fontSize.sm, lineHeight: 20, fontWeight: fontWeight.regular },
  small: { fontSize: fontSize.xs, lineHeight: 16, fontWeight: fontWeight.regular },
} as const satisfies Record<string, TypographyStyle>;

export type TextVariant = keyof typeof typography;
export type ColorName = keyof ThemeColors;
export type ColorSchemeName = 'light' | 'dark';

export interface Theme {
  scheme: ColorSchemeName;
  colors: ThemeColors;
  radius: typeof radius;
  spacing: typeof spacing;
  fontSize: typeof fontSize;
  fontWeight: typeof fontWeight;
  typography: typeof typography;
}

export const lightTheme: Theme = {
  scheme: 'light',
  colors: lightColors,
  radius,
  spacing,
  fontSize,
  fontWeight,
  typography,
};

export const darkTheme: Theme = { ...lightTheme, scheme: 'dark', colors: darkColors };

/** Current theme, following the OS appearance (app.json `userInterfaceStyle: automatic`). */
export function useTheme(): Theme {
  return useColorScheme() === 'dark' ? darkTheme : lightTheme;
}
