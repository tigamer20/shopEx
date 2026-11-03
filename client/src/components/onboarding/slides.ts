import type { IconName } from '@/components/ui';
import type { TranslationKey } from '@/i18n';

export interface OnboardingSlideData {
  id: 'welcome' | 'list' | 'cheapest' | 'more_options' | 'route';
  /** Main illustration glyph (Ionicons, MIT). */
  icon: IconName;
  /** Small glyphs orbiting the main one. */
  accents: readonly [IconName, IconName, IconName];
  title: TranslationKey;
  body: TranslationKey;
}

/** The five first-launch slides, in order (ARCHITECTURE §5). */
export const ONBOARDING_SLIDES: readonly OnboardingSlideData[] = [
  {
    id: 'welcome',
    icon: 'basket',
    accents: ['nutrition', 'cash-outline', 'storefront-outline'],
    title: 'onboarding.slides.welcome.title',
    body: 'onboarding.slides.welcome.body',
  },
  {
    id: 'list',
    icon: 'create',
    accents: ['add-circle', 'pricetag-outline', 'list-outline'],
    title: 'onboarding.slides.list.title',
    body: 'onboarding.slides.list.body',
  },
  {
    id: 'cheapest',
    icon: 'pricetags',
    accents: ['trending-down', 'storefront-outline', 'checkmark-circle'],
    title: 'onboarding.slides.cheapest.title',
    body: 'onboarding.slides.cheapest.body',
  },
  {
    id: 'more_options',
    icon: 'information-circle',
    accents: ['swap-horizontal', 'layers-outline', 'hand-left-outline'],
    title: 'onboarding.slides.more_options.title',
    body: 'onboarding.slides.more_options.body',
  },
  {
    id: 'route',
    icon: 'navigate',
    accents: ['map-outline', 'time-outline', 'flag'],
    title: 'onboarding.slides.route.title',
    body: 'onboarding.slides.route.body',
  },
];
