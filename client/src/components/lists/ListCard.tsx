import Ionicons from '@expo/vector-icons/Ionicons';
import { Pressable, StyleSheet, View } from 'react-native';

import type { GroceryListSummary } from '@/api/types';
import { AppText, Card, IconButton } from '@/components/ui';
import { useLanguage, useT } from '@/i18n';
import { useTheme } from '@/theme';
import { formatDate } from '@/utils/format';

export interface ListCardProps {
  list: GroceryListSummary;
  onOpen: (list: GroceryListSummary) => void;
  onToggleBookmark: (list: GroceryListSummary) => void;
  /** Shows a trash button when provided. */
  onDelete?: (list: GroceryListSummary) => void;
}

/** One saved list: icon tile, name, item count + last use, star and optional delete. */
export function ListCard({ list, onOpen, onToggleBookmark, onDelete }: ListCardProps) {
  const theme = useTheme();
  const t = useT();
  const { language } = useLanguage();
  const meta = `${t('lists.items_count', { count: list.items_count })} · ${t('lists.last_used', {
    date: formatDate(list.last_used_at, language),
  })}`;

  return (
    <Card padded={false}>
      <View style={[styles.row, { gap: theme.spacing.sm, paddingRight: theme.spacing.sm }]}>
        <View style={styles.main}>
          <Pressable
            accessibilityRole="button"
            onPress={() => onOpen(list)}
            accessibilityLabel={`${list.name}. ${meta}`}
            accessibilityHint={t('lists.open_hint')}
            style={({ pressed }) => (pressed ? styles.pressed : null)}
          >
            <View style={[styles.row, { gap: theme.spacing.md, padding: theme.spacing.md }]}>
              <View
                style={[styles.tile, { backgroundColor: theme.colors.surface, borderRadius: theme.radius.md }]}
                accessibilityElementsHidden
                importantForAccessibility="no-hide-descendants"
              >
                <Ionicons name="receipt-outline" size={22} color={theme.colors.primary} />
              </View>
              <View style={styles.text}>
                <AppText variant="subtitle" numberOfLines={1}>
                  {list.name}
                </AppText>
                <AppText variant="caption" numberOfLines={1}>
                  {meta}
                </AppText>
              </View>
            </View>
          </Pressable>
        </View>
        <IconButton
          icon={list.bookmarked ? 'star' : 'star-outline'}
          color={list.bookmarked ? 'warning' : 'textMuted'}
          selected={list.bookmarked}
          accessibilityLabel={t(list.bookmarked ? 'lists.bookmark_remove' : 'lists.bookmark_add', { name: list.name })}
          onPress={() => onToggleBookmark(list)}
        />
        {onDelete ? (
          <IconButton
            icon="trash-outline"
            color="danger"
            accessibilityLabel={t('lists.delete', { name: list.name })}
            onPress={() => onDelete(list)}
          />
        ) : null}
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  main: {
    flex: 1,
  },
  pressed: {
    opacity: 0.7,
  },
  tile: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  text: {
    flex: 1,
    gap: 2,
  },
});
