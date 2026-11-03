import Ionicons from '@expo/vector-icons/Ionicons';
import { Tabs } from 'expo-router/js-tabs';
import type { ColorValue } from 'react-native';

import type { IconName } from '@/components/ui';
import { useT } from '@/i18n';
import { useTheme } from '@/theme';

interface TabIconProps {
  color: ColorValue;
  size: number;
  focused: boolean;
}

/** Filled glyph for the active tab, outline otherwise. */
function tabIcon(active: IconName, inactive: IconName) {
  function TabIcon({ color, size, focused }: TabIconProps) {
    // The navigator passes the theme's tint colours, which are always plain strings.
    return <Ionicons name={focused ? active : inactive} size={size} color={typeof color === 'string' ? color : undefined} />;
  }
  return TabIcon;
}

export default function TabsLayout() {
  const theme = useTheme();
  const t = useT();

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: theme.colors.primary,
        tabBarInactiveTintColor: theme.colors.textMuted,
        tabBarStyle: { backgroundColor: theme.colors.card, borderTopColor: theme.colors.border },
        tabBarLabelStyle: { fontWeight: theme.fontWeight.semibold },
      }}
    >
      <Tabs.Screen name="index" options={{ title: t('common.tabs.home'), tabBarIcon: tabIcon('home', 'home-outline') }} />
      <Tabs.Screen
        name="browse"
        options={{ title: t('common.tabs.browse'), tabBarIcon: tabIcon('search', 'search-outline') }}
      />
      <Tabs.Screen name="lists" options={{ title: t('common.tabs.lists'), tabBarIcon: tabIcon('list', 'list-outline') }} />
      <Tabs.Screen
        name="profile"
        options={{ title: t('common.tabs.profile'), tabBarIcon: tabIcon('person', 'person-outline') }}
      />
    </Tabs>
  );
}
