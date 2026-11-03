/**
 * Web map: the Leaflet page rendered in a sandboxed `<iframe srcdoc>`.
 * The sandbox has no `allow-same-origin`, so the frame cannot read the app's storage (token).
 */
import { createElement } from 'react';
import { View } from 'react-native';

import { useTheme } from '@/theme';

import { DEFAULT_MAP_HEIGHT, type ItineraryMapComponent } from './types';
import { useLeafletHtml } from './useLeafletHtml';

export const ItineraryMap: ItineraryMapComponent = function ItineraryMap(props) {
  const theme = useTheme();
  const { html, accessibilityLabel } = useLeafletHtml(props);
  const height = props.height ?? DEFAULT_MAP_HEIGHT;

  return (
    <View
      style={{
        height,
        borderRadius: theme.radius.lg,
        overflow: 'hidden',
        backgroundColor: theme.colors.surface,
      }}
    >
      {createElement('iframe', {
        srcDoc: html,
        title: accessibilityLabel,
        sandbox: 'allow-scripts allow-popups allow-popups-to-escape-sandbox',
        referrerPolicy: 'strict-origin-when-cross-origin',
        style: { border: 0, width: '100%', height: '100%', display: 'block' },
      })}
    </View>
  );
};
