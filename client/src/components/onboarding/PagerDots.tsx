import { Pressable, StyleSheet, View } from 'react-native';

import { useT } from '@/i18n';
import { useTheme } from '@/theme';

export interface PagerDotsProps {
  count: number;
  index: number;
  /** Jump to a page when a dot is tapped. */
  onSelect?: (index: number) => void;
}

/** Page indicator: the active dot stretches into a pill. */
export function PagerDots({ count, index, onSelect }: PagerDotsProps) {
  const theme = useTheme();
  const t = useT();

  return (
    <View
      style={[styles.row, { gap: theme.spacing.sm }]}
      accessible
      accessibilityLabel={t('onboarding.progress', { current: index + 1, total: count })}
    >
      {Array.from({ length: count }, (_, dot) => {
        const active = dot === index;
        return (
          <Pressable
            key={dot}
            onPress={onSelect ? () => onSelect(dot) : undefined}
            hitSlop={8}
            accessibilityElementsHidden
            importantForAccessibility="no"
            style={[
              styles.dot,
              {
                width: active ? 24 : 8,
                borderRadius: theme.radius.pill,
                backgroundColor: active ? theme.colors.primary : theme.colors.border,
              },
            ]}
          />
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  dot: {
    height: 8,
  },
});
