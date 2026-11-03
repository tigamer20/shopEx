/**
 * First-launch tutorial (ARCHITECTURE §5): five swipeable slides with Skip / Next / Done.
 * Finishing or skipping marks the tutorial as seen on this device; `useTutorialSync` (root
 * layout) then records `tutorial_completed` on the account as soon as a session exists. The root
 * gate moves on by itself (login or tabs).
 * Replayable from Profile.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  FlatList,
  Pressable,
  StyleSheet,
  View,
  type LayoutChangeEvent,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { LanguageToggle } from '@/components/auth/LanguageToggle';
import { OnboardingSlide } from '@/components/onboarding/OnboardingSlide';
import { PagerDots } from '@/components/onboarding/PagerDots';
import { ONBOARDING_SLIDES, type OnboardingSlideData } from '@/components/onboarding/slides';
import { AppText, Button } from '@/components/ui';
import { useT } from '@/i18n';
import { useSettings } from '@/settings/SettingsProvider';
import { useTheme } from '@/theme';

const LAST_INDEX = ONBOARDING_SLIDES.length - 1;

export default function OnboardingScreen() {
  const theme = useTheme();
  const t = useT();
  const { completeOnboarding } = useSettings();
  const listRef = useRef<FlatList<OnboardingSlideData>>(null);
  const [pageWidth, setPageWidth] = useState(0);
  const [index, setIndex] = useState(0);
  const [finishing, setFinishing] = useState(false);

  const onLayout = useCallback((event: LayoutChangeEvent) => {
    setPageWidth(Math.round(event.nativeEvent.layout.width));
  }, []);

  // Keep the current page in view when the width changes (rotation, resized browser window).
  const indexRef = useRef(0);
  useEffect(() => {
    indexRef.current = index;
  }, [index]);
  useEffect(() => {
    if (pageWidth > 0) {
      listRef.current?.scrollToOffset({ offset: indexRef.current * pageWidth, animated: false });
    }
  }, [pageWidth]);

  // Page a Next / dot tap is animating to: intermediate scroll positions must not move the dots
  // back (a quick second tap would otherwise repeat the same page).
  const targetRef = useRef<number | null>(null);

  const onScroll = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      if (pageWidth <= 0) {
        return;
      }
      const page = Math.min(Math.max(Math.round(event.nativeEvent.contentOffset.x / pageWidth), 0), LAST_INDEX);
      if (targetRef.current !== null) {
        if (page !== targetRef.current) {
          return;
        }
        targetRef.current = null;
      }
      setIndex(page);
    },
    [pageWidth],
  );

  const goTo = useCallback(
    (page: number) => {
      const target = Math.min(Math.max(page, 0), LAST_INDEX);
      targetRef.current = target;
      setIndex(target);
      listRef.current?.scrollToOffset({ offset: target * pageWidth, animated: true });
    },
    [pageWidth],
  );

  // A swipe by hand cancels any pending programmatic target.
  const onScrollBeginDrag = useCallback(() => {
    targetRef.current = null;
  }, []);

  const finish = useCallback(async () => {
    if (finishing) {
      return;
    }
    setFinishing(true);
    await completeOnboarding();
  }, [finishing, completeOnboarding]);

  const isLast = index === LAST_INDEX;

  return (
    <SafeAreaView style={[styles.fill, { backgroundColor: theme.colors.background }]}>
      <View style={[styles.topBar, { paddingHorizontal: theme.spacing.lg, paddingTop: theme.spacing.sm }]}>
        <LanguageToggle style={styles.toggle} />
        {isLast ? null : (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t('common.actions.skip')}
            onPress={() => void finish()}
            hitSlop={12}
            style={styles.skip}
          >
            <AppText variant="label" color="textMuted">
              {t('common.actions.skip')}
            </AppText>
          </Pressable>
        )}
      </View>

      <View style={styles.fill} onLayout={onLayout}>
        {pageWidth > 0 ? (
          <FlatList
            ref={listRef}
            data={ONBOARDING_SLIDES}
            keyExtractor={(slide) => slide.id}
            renderItem={({ item }) => <OnboardingSlide slide={item} width={pageWidth} />}
            horizontal
            pagingEnabled
            bounces={false}
            showsHorizontalScrollIndicator={false}
            onScroll={onScroll}
            onScrollBeginDrag={onScrollBeginDrag}
            scrollEventThrottle={32}
            getItemLayout={(_, item) => ({ length: pageWidth, offset: pageWidth * item, index: item })}
          />
        ) : null}
      </View>

      <View style={[styles.footer, { padding: theme.spacing.lg, gap: theme.spacing.lg }]}>
        <PagerDots count={ONBOARDING_SLIDES.length} index={index} onSelect={goTo} />
        <Button
          label={isLast ? t('onboarding.start') : t('common.actions.next')}
          icon={isLast ? 'checkmark' : 'arrow-forward'}
          iconPosition="right"
          size="lg"
          fullWidth
          loading={finishing}
          onPress={() => (isLast ? void finish() : goTo(index + 1))}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  fill: {
    flex: 1,
  },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    minHeight: 48,
  },
  toggle: {
    alignSelf: 'center',
  },
  skip: {
    minHeight: 44,
    justifyContent: 'center',
    paddingHorizontal: 4,
  },
  footer: {
    width: '100%',
    maxWidth: 560,
    alignSelf: 'center',
  },
});
