/**
 * Root layout: providers + the navigation gate (ARCHITECTURE §5).
 *
 * Gate, enforced with protected routes so deep links cannot bypass it:
 * - tutorial not seen yet (or replayed from Profile) → only `/onboarding` is reachable;
 * - signed out → only the auth screens (`/login`, `/register`);
 * - signed in → the tabs and the search flow (`/list/edit`, `/results`, `/itinerary`).
 * When the state changes (tutorial done, login, logout), the stack moves to the first
 * reachable screen by itself: screens never need to redirect after these actions.
 */
import { DarkTheme, DefaultTheme, Stack, ThemeProvider, type Theme as NavigationTheme } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useMemo } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { AuthProvider, useAuth } from '@/auth';
import { useTutorialSync } from '@/components/onboarding/useTutorialSync';
import { useUserLanguageSync } from '@/hooks/useUserLanguageSync';
import { I18nProvider, useI18nReady, useT } from '@/i18n';
import { SearchSessionProvider } from '@/search/SearchSession';
import { SettingsProvider, useSettings } from '@/settings/SettingsProvider';
import { useTheme, type Theme } from '@/theme';

function toNavigationTheme(theme: Theme): NavigationTheme {
  const base = theme.scheme === 'dark' ? DarkTheme : DefaultTheme;
  return {
    ...base,
    colors: {
      ...base.colors,
      primary: theme.colors.primary,
      background: theme.colors.background,
      card: theme.colors.card,
      text: theme.colors.text,
      border: theme.colors.border,
      notification: theme.colors.primary,
    },
  };
}

function RootNavigator() {
  const theme = useTheme();
  const t = useT();
  const i18nReady = useI18nReady();
  const settings = useSettings();
  const { status } = useAuth();
  useUserLanguageSync();
  useTutorialSync();

  const navigationTheme = useMemo(() => toNavigationTheme(theme), [theme]);

  if (!i18nReady || !settings.ready || status === 'loading') {
    return (
      <View style={[styles.loading, { backgroundColor: theme.colors.background }]}>
        <ActivityIndicator size="large" color={theme.colors.primary} accessibilityLabel={t('common.loading')} />
      </View>
    );
  }

  const showOnboarding = !settings.hasSeenOnboarding || settings.isReplayingOnboarding;
  const signedIn = status === 'signedIn';
  // Explicit targets: the default fallback would land on the bare `(auth)` group (no index).
  const homeRoute = signedIn ? '/' : '/login';
  const entryRoute = showOnboarding ? '/onboarding' : homeRoute;
  const stackHeader = {
    headerShown: true,
    headerTintColor: theme.colors.text,
    headerTitleStyle: { fontWeight: theme.fontWeight.heavy },
    headerShadowVisible: false,
  } as const;

  return (
    <ThemeProvider value={navigationTheme}>
      <StatusBar style={theme.scheme === 'dark' ? 'light' : 'dark'} />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: theme.colors.background } }}>
        <Stack.Protected guard={showOnboarding} redirectTo={homeRoute}>
          <Stack.Screen name="onboarding" options={{ gestureEnabled: false }} />
        </Stack.Protected>

        <Stack.Protected guard={!showOnboarding && signedIn} redirectTo={entryRoute}>
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="list/edit" options={{ ...stackHeader, title: t('editor.title') }} />
          <Stack.Screen name="results" options={{ ...stackHeader, title: t('results.title') }} />
          <Stack.Screen name="itinerary" options={{ ...stackHeader, title: t('itinerary.title') }} />
        </Stack.Protected>

        <Stack.Protected guard={!showOnboarding && !signedIn} redirectTo={entryRoute}>
          <Stack.Screen name="(auth)" />
        </Stack.Protected>

        <Stack.Screen name="+not-found" />
      </Stack>
    </ThemeProvider>
  );
}

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <I18nProvider>
        <SettingsProvider>
          <AuthProvider>
            <SearchSessionProvider>
              <RootNavigator />
            </SearchSessionProvider>
          </AuthProvider>
        </SettingsProvider>
      </I18nProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
