import Ionicons from '@expo/vector-icons/Ionicons';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { useTheme } from '@/theme';

import { AppText } from './AppText';
import { Button } from './Button';
import type { IconName } from './icons';

export interface EmptyStateProps {
  title: string;
  message?: string;
  icon?: IconName;
  actionLabel?: string;
  onAction?: () => void;
  style?: StyleProp<ViewStyle>;
}

/** Centered placeholder for empty lists and not-yet-available content. */
export function EmptyState({ title, message, icon = 'basket-outline', actionLabel, onAction, style }: EmptyStateProps) {
  const theme = useTheme();
  return (
    <View style={[styles.container, { gap: theme.spacing.md, padding: theme.spacing.xl }, style]}>
      <View
        style={[styles.iconCircle, { backgroundColor: theme.colors.surface, borderRadius: theme.radius.pill }]}
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
      >
        <Ionicons name={icon} size={36} color={theme.colors.primary} />
      </View>
      <AppText variant="heading" align="center">
        {title}
      </AppText>
      {message ? (
        <AppText variant="caption" align="center">
          {message}
        </AppText>
      ) : null}
      {actionLabel && onAction ? <Button label={actionLabel} onPress={onAction} /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconCircle: {
    width: 72,
    height: 72,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
