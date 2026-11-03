import { Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { useTheme } from '@/theme';

import { AppText } from './AppText';

export interface SectionHeaderProps {
  title: string;
  /** Optional trailing action, e.g. "See all". */
  actionLabel?: string;
  onAction?: () => void;
  style?: StyleProp<ViewStyle>;
}

/** Bold section title with an optional trailing link (carousels, grouped lists). */
export function SectionHeader({ title, actionLabel, onAction, style }: SectionHeaderProps) {
  const theme = useTheme();
  return (
    <View style={[styles.row, { gap: theme.spacing.md }, style]}>
      <AppText variant="heading" style={styles.title} numberOfLines={1}>
        {title}
      </AppText>
      {actionLabel && onAction ? (
        <Pressable accessibilityRole="link" accessibilityLabel={actionLabel} onPress={onAction} hitSlop={8}>
          <AppText variant="label" color="primary">
            {actionLabel}
          </AppText>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  title: {
    flexShrink: 1,
  },
});
