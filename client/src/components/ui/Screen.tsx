import type { ReactElement, ReactNode } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  View,
  type RefreshControlProps,
  type StyleProp,
  type ViewStyle,
} from 'react-native';
import { SafeAreaView, type Edge } from 'react-native-safe-area-context';

import { useTheme } from '@/theme';

export interface ScreenProps {
  children: ReactNode;
  /** Wraps the content in a ScrollView (default true). Use false for FlatList screens. */
  scroll?: boolean;
  /** Horizontal/vertical page padding (default true). */
  padded?: boolean;
  /**
   * Safe-area edges to pad. The default `['top', 'left', 'right']` suits tab screens (the tab
   * bar handles the bottom inset); stack screens under a native header pass
   * `['left', 'right', 'bottom']`; full-screen pages without tabs pass all four.
   */
  edges?: readonly Edge[];
  /** Sticky area under the content, e.g. the full-width CTA. */
  footer?: ReactNode;
  refreshControl?: ReactElement<RefreshControlProps>;
  contentContainerStyle?: StyleProp<ViewStyle>;
  /** Page background token (default `background`). */
  background?: 'background' | 'surface';
}

const DEFAULT_EDGES: readonly Edge[] = ['top', 'left', 'right'];

/** Page scaffold: safe area, keyboard avoidance, optional scroll and sticky footer. */
export function Screen({
  children,
  scroll = true,
  padded = true,
  edges = DEFAULT_EDGES,
  footer,
  refreshControl,
  contentContainerStyle,
  background = 'background',
}: ScreenProps) {
  const theme = useTheme();
  const padding: ViewStyle = padded ? { padding: theme.spacing.lg, gap: theme.spacing.lg } : {};

  return (
    <SafeAreaView edges={edges} style={[styles.fill, { backgroundColor: theme.colors[background] }]}>
      <KeyboardAvoidingView style={styles.fill} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        {scroll ? (
          <ScrollView
            style={styles.fill}
            contentContainerStyle={[padding, contentContainerStyle]}
            keyboardShouldPersistTaps="handled"
            refreshControl={refreshControl}
          >
            {children}
          </ScrollView>
        ) : (
          <View style={[styles.fill, padding, contentContainerStyle]}>{children}</View>
        )}
        {footer ? (
          <View
            style={[
              styles.footer,
              {
                padding: theme.spacing.lg,
                gap: theme.spacing.sm,
                borderTopColor: theme.colors.border,
                backgroundColor: theme.colors[background],
              },
            ]}
          >
            {footer}
          </View>
        ) : null}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  fill: {
    flex: 1,
  },
  footer: {
    borderTopWidth: StyleSheet.hairlineWidth,
  },
});
