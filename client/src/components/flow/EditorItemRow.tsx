import { StyleSheet, View } from 'react-native';

import type { GroceryItemInput } from '@/api/types';
import { AppText, Card, IconButton } from '@/components/ui';
import { useT } from '@/i18n';
import { useTheme } from '@/theme';

import { QuantityStepper } from './QuantityStepper';

export interface EditorItemRowProps {
  item: GroceryItemInput;
  isFirst: boolean;
  isLast: boolean;
  onQuantityChange: (quantity: number) => void;
  onMove: (delta: -1 | 1) => void;
  onRemove: () => void;
}

/** One line of the grocery list: name, favourite brand, quantity stepper, reorder and remove. */
export function EditorItemRow({ item, isFirst, isLast, onQuantityChange, onMove, onRemove }: EditorItemRowProps) {
  const theme = useTheme();
  const t = useT();

  return (
    <Card style={{ paddingVertical: theme.spacing.md }}>
      <View style={[styles.row, { gap: theme.spacing.sm }]}>
        <View style={[styles.main, { gap: theme.spacing.xs }]}>
          <AppText variant="subtitle" numberOfLines={2}>
            {item.name}
          </AppText>
          <AppText variant="caption" numberOfLines={1}>
            {item.brand ?? t('editor.any_brand')}
          </AppText>
        </View>
        <IconButton
          icon="trash-outline"
          color="danger"
          accessibilityLabel={t('editor.remove_item', { name: item.name })}
          onPress={onRemove}
        />
      </View>
      <View style={[styles.row, { gap: theme.spacing.sm, marginTop: theme.spacing.sm }]}>
        <QuantityStepper
          value={item.quantity}
          onChange={onQuantityChange}
          accessibilityLabel={t('editor.quantity_for', { name: item.name, count: item.quantity })}
        />
        <View style={styles.main} />
        <IconButton
          icon="chevron-up"
          accessibilityLabel={t('editor.move_up', { name: item.name })}
          disabled={isFirst}
          onPress={() => onMove(-1)}
        />
        <IconButton
          icon="chevron-down"
          accessibilityLabel={t('editor.move_down', { name: item.name })}
          disabled={isLast}
          onPress={() => onMove(1)}
        />
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
});
