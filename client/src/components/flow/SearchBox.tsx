import Ionicons from '@expo/vector-icons/Ionicons';
import { StyleSheet, TextInput, View, type StyleProp, type ViewStyle } from 'react-native';

import { IconButton } from '@/components/ui';
import { useT } from '@/i18n';
import { useTheme } from '@/theme';

export interface SearchBoxProps {
  value: string;
  onChangeText: (text: string) => void;
  placeholder: string;
  accessibilityLabel: string;
  style?: StyleProp<ViewStyle>;
}

/** Pill-shaped search input with a leading glyph and a clear button. */
export function SearchBox({ value, onChangeText, placeholder, accessibilityLabel, style }: SearchBoxProps) {
  const theme = useTheme();
  const t = useT();

  return (
    <View
      style={[
        styles.box,
        {
          gap: theme.spacing.sm,
          paddingLeft: theme.spacing.lg,
          borderRadius: theme.radius.pill,
          backgroundColor: theme.colors.surface,
          borderColor: theme.colors.border,
        },
        style,
      ]}
    >
      <Ionicons name="search" size={20} color={theme.colors.textMuted} />
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={theme.colors.textMuted}
        accessibilityLabel={accessibilityLabel}
        autoCorrect={false}
        autoCapitalize="none"
        returnKeyType="search"
        maxLength={100}
        style={[styles.input, theme.typography.body, { color: theme.colors.text }]}
      />
      {value ? (
        <IconButton icon="close-circle" color="textMuted" accessibilityLabel={t('browse.clear_search')} onPress={() => onChangeText('')} />
      ) : (
        <View style={styles.spacer} />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 48,
    borderWidth: 1,
  },
  input: {
    flex: 1,
    minHeight: 44,
  },
  spacer: {
    width: 12,
  },
});
