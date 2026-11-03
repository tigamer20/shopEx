import { StyleSheet, View } from 'react-native';

import { AppText, IconButton } from '@/components/ui';
import { useT } from '@/i18n';
import { useTheme } from '@/theme';

import { MAX_QUANTITY, MIN_QUANTITY } from './listItems';

export interface QuantityStepperProps {
  value: number;
  onChange: (value: number) => void;
  /** Spoken label of the value, e.g. "Quantity of milk: 2". */
  accessibilityLabel: string;
}

/** − value + control, clamped to 1..99. Exposed as an adjustable control to screen readers. */
export function QuantityStepper({ value, onChange, accessibilityLabel }: QuantityStepperProps) {
  const theme = useTheme();
  const t = useT();
  const canDecrease = value > MIN_QUANTITY;
  const canIncrease = value < MAX_QUANTITY;

  return (
    <View
      accessible
      accessibilityRole="adjustable"
      accessibilityLabel={accessibilityLabel}
      accessibilityValue={{ min: MIN_QUANTITY, max: MAX_QUANTITY, now: value }}
      accessibilityActions={[{ name: 'increment' }, { name: 'decrement' }]}
      onAccessibilityAction={(event) => {
        if (event.nativeEvent.actionName === 'increment' && canIncrease) onChange(value + 1);
        if (event.nativeEvent.actionName === 'decrement' && canDecrease) onChange(value - 1);
      }}
      style={[styles.row, { backgroundColor: theme.colors.surface, borderRadius: theme.radius.pill }]}
    >
      <IconButton
        icon="remove"
        size={18}
        accessibilityLabel={t('editor.decrease')}
        disabled={!canDecrease}
        onPress={() => onChange(value - 1)}
      />
      <AppText variant="subtitle" align="center" style={styles.value}>
        {value}
      </AppText>
      <IconButton
        icon="add"
        size={18}
        accessibilityLabel={t('editor.increase')}
        disabled={!canIncrease}
        onPress={() => onChange(value + 1)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
  },
  value: {
    minWidth: 28,
  },
});
