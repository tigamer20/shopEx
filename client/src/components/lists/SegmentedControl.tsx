import { Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { AppText } from '@/components/ui';
import { useTheme } from '@/theme';

export interface Segment<T extends string> {
  value: T;
  label: string;
}

export interface SegmentedControlProps<T extends string> {
  segments: readonly Segment<T>[];
  value: T;
  onChange: (value: T) => void;
  /** Spoken name of the whole control. */
  accessibilityLabel: string;
  style?: StyleProp<ViewStyle>;
}

/** Pill-shaped two-or-more-way switch (History / Bookmarks). */
export function SegmentedControl<T extends string>({
  segments,
  value,
  onChange,
  accessibilityLabel,
  style,
}: SegmentedControlProps<T>) {
  const theme = useTheme();

  return (
    <View
      accessibilityRole="tablist"
      accessibilityLabel={accessibilityLabel}
      style={[
        styles.track,
        { backgroundColor: theme.colors.surface, borderRadius: theme.radius.pill, padding: theme.spacing.xs },
        style,
      ]}
    >
      {segments.map((segment) => {
        const selected = segment.value === value;
        return (
          <Pressable
            key={segment.value}
            accessibilityRole="tab"
            accessibilityLabel={segment.label}
            accessibilityState={{ selected }}
            onPress={() => onChange(segment.value)}
            style={[
              styles.segment,
              {
                borderRadius: theme.radius.pill,
                backgroundColor: selected ? theme.colors.card : 'transparent',
                boxShadow: selected && theme.scheme === 'light' ? '0px 1px 4px rgba(0, 0, 0, 0.12)' : undefined,
              },
            ]}
          >
            <AppText variant="label" color={selected ? 'text' : 'textMuted'} numberOfLines={1}>
              {segment.label}
            </AppText>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  track: {
    flexDirection: 'row',
  },
  segment: {
    flex: 1,
    minHeight: 40,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 12,
  },
});
