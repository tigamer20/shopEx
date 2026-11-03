import Ionicons from '@expo/vector-icons/Ionicons';
import { Pressable, StyleSheet, View } from 'react-native';

import type { GroceryListSummary } from '@/api/types';
import { AppText } from '@/components/ui';
import { useT } from '@/i18n';
import { useTheme } from '@/theme';

export interface BookmarkCardProps {
  list: GroceryListSummary;
  onPress: (list: GroceryListSummary) => void;
}

export const BOOKMARK_CARD_WIDTH = 168;

/** Square-ish carousel tile for a bookmarked list (reusable template). */
export function BookmarkCard({ list, onPress }: BookmarkCardProps) {
  const theme = useTheme();
  const t = useT();
  const count = t('lists.items_count', { count: list.items_count });

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${list.name}. ${count}`}
      accessibilityHint={t('home.open_list_hint')}
      onPress={() => onPress(list)}
      style={({ pressed }) => [
        styles.card,
        {
          gap: theme.spacing.md,
          padding: theme.spacing.lg,
          borderRadius: theme.radius.lg,
          backgroundColor: theme.colors.card,
          borderColor: theme.colors.border,
          boxShadow: theme.scheme === 'light' ? '0px 2px 10px rgba(0, 0, 0, 0.06)' : undefined,
          opacity: pressed ? 0.85 : 1,
        },
      ]}
    >
      <View
        style={[styles.icon, { borderRadius: theme.radius.md, backgroundColor: theme.colors.surface }]}
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
      >
        <Ionicons name="star" size={20} color={theme.colors.warning} />
      </View>
      <View style={styles.text}>
        <AppText variant="subtitle" numberOfLines={2}>
          {list.name}
        </AppText>
        <AppText variant="caption" numberOfLines={1}>
          {count}
        </AppText>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    width: BOOKMARK_CARD_WIDTH,
    minHeight: 132,
    borderWidth: StyleSheet.hairlineWidth,
  },
  icon: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  text: {
    gap: 2,
  },
});
