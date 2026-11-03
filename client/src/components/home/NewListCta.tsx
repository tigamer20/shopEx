import Ionicons from '@expo/vector-icons/Ionicons';
import { Pressable, StyleSheet, View } from 'react-native';

import { AppText } from '@/components/ui';
import { useT } from '@/i18n';
import { useTheme } from '@/theme';

export interface NewListCtaProps {
  onPress: () => void;
}

/** Big accent banner that starts a new grocery list (the Home screen's main action). */
export function NewListCta({ onPress }: NewListCtaProps) {
  const theme = useTheme();
  const t = useT();
  const title = t('home.new_list_cta');
  const subtitle = t('home.new_list_subtitle');

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${title}. ${subtitle}`}
      onPress={onPress}
      style={({ pressed }) => [
        styles.banner,
        {
          gap: theme.spacing.lg,
          padding: theme.spacing.xl,
          borderRadius: theme.radius.xl,
          backgroundColor: pressed ? theme.colors.primaryDark : theme.colors.primary,
        },
      ]}
    >
      <View style={[styles.text, { gap: theme.spacing.xs }]}>
        <AppText variant="heading" style={{ color: theme.colors.onPrimary }}>
          {title}
        </AppText>
        <AppText variant="caption" style={{ color: theme.colors.onPrimary, opacity: 0.9 }}>
          {subtitle}
        </AppText>
      </View>
      <View
        style={[styles.bubble, { borderRadius: theme.radius.pill, backgroundColor: theme.colors.onPrimary }]}
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
      >
        <Ionicons name="add" size={32} color={theme.colors.primary} />
      </View>
      {/* Decorative oversized glyph, clipped by the rounded banner. */}
      <Ionicons
        name="basket"
        size={140}
        color={theme.colors.onPrimary}
        style={styles.watermark}
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    overflow: 'hidden',
    minHeight: 120,
  },
  text: {
    flex: 1,
    zIndex: 1,
  },
  bubble: {
    width: 56,
    height: 56,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1,
  },
  watermark: {
    position: 'absolute',
    right: -24,
    bottom: -36,
    opacity: 0.12,
  },
});
