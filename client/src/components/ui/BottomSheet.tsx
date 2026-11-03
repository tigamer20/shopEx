import { useEffect, useState, type ReactNode } from 'react';
import { Animated, Modal, Platform, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useT } from '@/i18n';
import { useTheme } from '@/theme';

import { AppText } from './AppText';
import { IconButton } from './IconButton';

export interface BottomSheetProps {
  visible: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  /** Sticky area under the scrollable content (e.g. a confirm button). */
  footer?: ReactNode;
}

const SLIDE_DISTANCE = 320;

/**
 * Modal sheet sliding up from the bottom (works on iOS, Android and web).
 * Tapping the backdrop, the close button or the Android back button calls `onClose`.
 */
export function BottomSheet({ visible, onClose, title, children, footer }: BottomSheetProps) {
  const theme = useTheme();
  const t = useT();
  const insets = useSafeAreaInsets();
  const [translateY] = useState(() => new Animated.Value(SLIDE_DISTANCE));

  useEffect(() => {
    if (visible) {
      translateY.setValue(SLIDE_DISTANCE);
      Animated.spring(translateY, {
        toValue: 0,
        bounciness: 0,
        speed: 16,
        useNativeDriver: Platform.OS !== 'web',
      }).start();
    }
  }, [visible, translateY]);

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose} statusBarTranslucent>
      <View style={styles.root}>
        <Pressable
          style={[StyleSheet.absoluteFill, styles.backdrop]}
          onPress={onClose}
          accessibilityRole="button"
          accessibilityLabel={t('common.actions.close')}
        />
        <Animated.View
          accessibilityViewIsModal
          style={[
            styles.sheet,
            {
              transform: [{ translateY }],
              backgroundColor: theme.colors.card,
              borderTopLeftRadius: theme.radius.xl,
              borderTopRightRadius: theme.radius.xl,
              paddingBottom: insets.bottom + theme.spacing.lg,
            },
          ]}
        >
          <View style={[styles.handle, { backgroundColor: theme.colors.border, marginTop: theme.spacing.sm }]} />
          <View style={[styles.header, { paddingHorizontal: theme.spacing.lg, gap: theme.spacing.sm }]}>
            <AppText variant="heading" style={styles.title} numberOfLines={2}>
              {title ?? ''}
            </AppText>
            <IconButton icon="close" accessibilityLabel={t('common.actions.close')} onPress={onClose} variant="tonal" />
          </View>
          <ScrollView
            contentContainerStyle={{ padding: theme.spacing.lg, gap: theme.spacing.md }}
            keyboardShouldPersistTaps="handled"
          >
            {children}
          </ScrollView>
          {footer ? <View style={{ paddingHorizontal: theme.spacing.lg, gap: theme.spacing.sm }}>{footer}</View> : null}
        </Animated.View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    justifyContent: 'flex-end',
  },
  backdrop: {
    backgroundColor: 'rgba(0, 0, 0, 0.45)',
  },
  sheet: {
    maxHeight: '85%',
    width: '100%',
    maxWidth: 640,
    alignSelf: 'center',
  },
  handle: {
    alignSelf: 'center',
    width: 40,
    height: 4,
    borderRadius: 2,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 56,
  },
  title: {
    flex: 1,
  },
});
