import Ionicons from '@expo/vector-icons/Ionicons';
import { StyleSheet, View } from 'react-native';

import { AppText, Logo } from '@/components/ui';
import { useT } from '@/i18n';
import { useTheme } from '@/theme';

import type { OnboardingSlideData } from './slides';

export interface OnboardingSlideProps {
  slide: OnboardingSlideData;
  width: number;
}

const STAGE = 240;
const DISC = 168;
const ACCENT_POSITIONS = [
  { top: 6, left: 18 },
  { top: 28, right: 6 },
  { bottom: 8, left: 40 },
] as const;

/** One tutorial page: a layered Ionicons illustration, a bold title and a short body. */
export function OnboardingSlide({ slide, width }: OnboardingSlideProps) {
  const theme = useTheme();
  const t = useT();

  return (
    <View style={[styles.page, { width, paddingHorizontal: theme.spacing.xl, gap: theme.spacing.xl }]}>
      <View style={styles.stage} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        <View style={[styles.halo, { backgroundColor: theme.colors.primary, borderRadius: STAGE / 2 }]} />
        <View
          style={[
            styles.disc,
            {
              backgroundColor: theme.colors.primary,
              borderRadius: DISC * 0.32,
              boxShadow: '0px 12px 28px rgba(242, 84, 45, 0.35)',
            },
          ]}
        >
          <Ionicons name={slide.icon} size={88} color={theme.colors.onPrimary} />
        </View>
        {slide.accents.map((icon, index) => (
          <View
            key={icon}
            style={[
              styles.accent,
              ACCENT_POSITIONS[index],
              {
                backgroundColor: theme.colors.card,
                borderColor: theme.colors.border,
                borderRadius: theme.radius.pill,
                boxShadow: theme.scheme === 'light' ? '0px 4px 12px rgba(0, 0, 0, 0.10)' : undefined,
              },
            ]}
          >
            <Ionicons name={icon} size={22} color={theme.colors.primary} />
          </View>
        ))}
      </View>

      <View style={[styles.text, { gap: theme.spacing.md }]}>
        {slide.id === 'welcome' ? <Logo size="md" showSlogan /> : null}
        <AppText variant="title" align="center">
          {t(slide.title)}
        </AppText>
        <AppText variant="body" color="textMuted" align="center">
          {t(slide.body)}
        </AppText>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  page: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stage: {
    width: STAGE,
    height: STAGE,
    alignItems: 'center',
    justifyContent: 'center',
  },
  halo: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    opacity: 0.1,
  },
  disc: {
    width: DISC,
    height: DISC,
    alignItems: 'center',
    justifyContent: 'center',
    transform: [{ rotate: '-6deg' }],
  },
  accent: {
    position: 'absolute',
    width: 52,
    height: 52,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth,
  },
  text: {
    maxWidth: 420,
    alignItems: 'center',
  },
});
