import { Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { LANGUAGES, type Language } from '@/api/types';
import { AppText } from '@/components/ui';
import { useLanguage, useT } from '@/i18n';
import { useTheme } from '@/theme';

export interface LanguageToggleProps {
  style?: StyleProp<ViewStyle>;
}

/** Compact "FR | EN" pill switch, shown on the tutorial and the auth screens. */
export function LanguageToggle({ style }: LanguageToggleProps) {
  const theme = useTheme();
  const t = useT();
  const { language, setLanguage } = useLanguage();

  return (
    <View
      accessibilityRole="radiogroup"
      accessibilityLabel={t('common.language_switch')}
      style={[
        styles.track,
        { backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderRadius: theme.radius.pill },
        style,
      ]}
    >
      {LANGUAGES.map((code: Language) => {
        const selected = code === language;
        return (
          <Pressable
            key={code}
            accessibilityRole="radio"
            accessibilityLabel={t(`common.languages.${code}`)}
            accessibilityState={{ selected, checked: selected }}
            onPress={() => {
              if (!selected) {
                void setLanguage(code);
              }
            }}
            hitSlop={4}
            style={[
              styles.option,
              { borderRadius: theme.radius.pill, backgroundColor: selected ? theme.colors.primary : 'transparent' },
            ]}
          >
            <AppText variant="label" style={{ color: selected ? theme.colors.onPrimary : theme.colors.textMuted }}>
              {code.toUpperCase()}
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
    alignSelf: 'flex-end',
    borderWidth: 1,
    padding: 3,
  },
  option: {
    minWidth: 44,
    minHeight: 32,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 10,
  },
});
