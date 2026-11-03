/**
 * iOS/Android map: the Leaflet page in a locked-down WebView.
 * - `originWhitelist` only allows the inline page itself: any link (e.g. the OSM copyright
 *   notice) is not loaded in the WebView but handed to the system browser;
 * - no file access, no extra windows, no mixed content; the auth token is never injected.
 */
import { useMemo } from 'react';
import { View } from 'react-native';
import { WebView } from 'react-native-webview';

import { useTheme } from '@/theme';

import { DEFAULT_MAP_HEIGHT, type ItineraryMapComponent } from './types';
import { useLeafletHtml } from './useLeafletHtml';

const ORIGIN_WHITELIST = ['about:blank'];
const USER_AGENT_SUFFIX = 'ShopEx/1.0';

export const ItineraryMap: ItineraryMapComponent = function ItineraryMap(props) {
  const theme = useTheme();
  const { html, accessibilityLabel } = useLeafletHtml(props);
  const height = props.height ?? DEFAULT_MAP_HEIGHT;
  // A new source object would make the WebView reload the page.
  const source = useMemo(() => ({ html, baseUrl: 'about:blank' }), [html]);

  return (
    <View
      accessible
      accessibilityRole="image"
      accessibilityLabel={accessibilityLabel}
      style={{
        height,
        borderRadius: theme.radius.lg,
        overflow: 'hidden',
        backgroundColor: theme.colors.surface,
      }}
    >
      <WebView
        source={source}
        originWhitelist={ORIGIN_WHITELIST}
        applicationNameForUserAgent={USER_AGENT_SUFFIX}
        javaScriptEnabled
        domStorageEnabled={false}
        allowFileAccess={false}
        allowFileAccessFromFileURLs={false}
        allowUniversalAccessFromFileURLs={false}
        allowsLinkPreview={false}
        setSupportMultipleWindows={false}
        javaScriptCanOpenWindowsAutomatically={false}
        mixedContentMode="never"
        nestedScrollEnabled
        scrollEnabled={false}
        style={{ backgroundColor: theme.colors.surface }}
      />
    </View>
  );
};
