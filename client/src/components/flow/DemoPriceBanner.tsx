import Ionicons from '@expo/vector-icons/Ionicons';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { AppText } from '@/components/ui';
import { useT } from '@/i18n';
import { useTheme } from '@/theme';

/** Notice required whenever generated prices are shown (`prices_are_demo`, ARCHITECTURE §1.11). */
export function DemoPriceBanner({ style }: { style?: StyleProp<ViewStyle> }) {
  const theme = useTheme();
  const t = useT();

  return (
    <View
      accessibilityRole="text"
      style={[
        styles.row,
        {
          gap: theme.spacing.sm,
          padding: theme.spacing.md,
          borderRadius: theme.radius.md,
          backgroundColor: theme.colors.surface,
          borderColor: theme.colors.warning,
        },
        style,
      ]}
    >
      <Ionicons name="information-circle" size={20} color={theme.colors.warning} />
      <AppText variant="caption" color="text" style={styles.text}>
        {t('common.demo_prices')}
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    borderWidth: 1,
  },
  text: {
    flex: 1,
  },
});
