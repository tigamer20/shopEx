import type { ReactNode } from 'react';
import { Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { useTheme } from '@/theme';

export interface CardProps {
  children: ReactNode;
  /** Makes the whole card a button. */
  onPress?: () => void;
  accessibilityLabel?: string;
  accessibilityHint?: string;
  /** Inner padding (default true). */
  padded?: boolean;
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

/** Large rounded surface used for list items, offers and summaries. */
export function Card({ children, onPress, accessibilityLabel, accessibilityHint, padded = true, style, testID }: CardProps) {
  const theme = useTheme();
  const cardStyle: ViewStyle = {
    backgroundColor: theme.colors.card,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    padding: padded ? theme.spacing.lg : 0,
    boxShadow: theme.scheme === 'light' ? '0px 2px 10px rgba(0, 0, 0, 0.06)' : undefined,
  };

  if (!onPress) {
    return (
      <View style={[styles.base, cardStyle, style]} testID={testID}>
        {children}
      </View>
    );
  }

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityHint={accessibilityHint}
      onPress={onPress}
      testID={testID}
      style={({ pressed }) => [styles.base, cardStyle, pressed ? styles.pressed : null, style]}
    >
      {children}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    borderWidth: StyleSheet.hairlineWidth,
    overflow: 'hidden',
  },
  pressed: {
    opacity: 0.85,
  },
});
