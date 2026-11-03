import { Stack } from 'expo-router';

import { useTheme } from '@/theme';

export const unstable_settings = {
  initialRouteName: 'login',
};

export default function AuthLayout() {
  const theme = useTheme();
  return (
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: theme.colors.background } }}>
      <Stack.Screen name="login" />
      <Stack.Screen name="register" />
    </Stack>
  );
}
