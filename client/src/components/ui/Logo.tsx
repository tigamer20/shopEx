import Ionicons from '@expo/vector-icons/Ionicons';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { useT } from '@/i18n';
import { useTheme, type TextVariant } from '@/theme';

import { AppText } from './AppText';

export type LogoSize = 'sm' | 'md' | 'lg';

export interface LogoProps {
  size?: LogoSize;
  showSlogan?: boolean;
  style?: StyleProp<ViewStyle>;
}

const SIZES: Record<LogoSize, { mark: number; glyph: number; wordmark: TextVariant }> = {
  sm: { mark: 32, glyph: 18, wordmark: 'heading' },
  md: { mark: 48, glyph: 28, wordmark: 'title' },
  lg: { mark: 72, glyph: 42, wordmark: 'display' },
};

/** Original ShopEx mark: Ionicons basket glyph on the accent tile + "ShopEx" wordmark. */
export function Logo({ size = 'md', showSlogan = false, style }: LogoProps) {
  const theme = useTheme();
  const t = useT();
  const dims = SIZES[size];
  const appName = t('common.app_name');
  const slogan = t('common.slogan');

  return (
    <View
      accessible
      accessibilityRole="image"
      accessibilityLabel={showSlogan ? `${appName}. ${slogan}` : appName}
      style={[styles.container, { gap: theme.spacing.sm }, style]}
    >
      <View style={[styles.row, { gap: theme.spacing.sm }]}>
        <View
          style={[
            styles.mark,
            {
              width: dims.mark,
              height: dims.mark,
              borderRadius: dims.mark * 0.3,
              backgroundColor: theme.colors.primary,
            },
          ]}
        >
          <Ionicons name="basket" size={dims.glyph} color={theme.colors.onPrimary} />
        </View>
        <AppText variant={dims.wordmark} accessibilityRole="none">
          Shop
          <AppText variant={dims.wordmark} color="primary" accessibilityRole="none">
            Ex
          </AppText>
        </AppText>
      </View>
      {showSlogan ? (
        <AppText variant="subtitle" color="textMuted" accessibilityRole="none">
          {slogan}
        </AppText>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  mark: {
    alignItems: 'center',
    justifyContent: 'center',
  },
});
