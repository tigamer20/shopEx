import { Stack, useRouter } from 'expo-router';

import { EmptyState, Screen } from '@/components/ui';
import { useT } from '@/i18n';

export default function NotFoundScreen() {
  const t = useT();
  const router = useRouter();

  return (
    <>
      <Stack.Screen options={{ title: t('common.not_found.title') }} />
      <Screen edges={['top', 'left', 'right', 'bottom']}>
        <EmptyState
          icon="help-circle-outline"
          title={t('common.not_found.title')}
          message={t('common.not_found.body')}
          actionLabel={t('common.not_found.go_home')}
          onAction={() => router.replace('/')}
        />
      </Screen>
    </>
  );
}
