import type Ionicons from '@expo/vector-icons/Ionicons';
import type { ComponentProps } from 'react';

/** Any Ionicons glyph name (MIT-licensed icon set bundled with @expo/vector-icons). */
export type IconName = ComponentProps<typeof Ionicons>['name'];
