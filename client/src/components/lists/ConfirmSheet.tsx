import { AppText, BottomSheet, Button } from '@/components/ui';
import { useT } from '@/i18n';

export interface ConfirmSheetProps {
  visible: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  /** Shows a spinner on the confirm button while the action runs. */
  busy?: boolean;
  /** Already-translated error from the last attempt, if any. */
  error?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Destructive-action confirmation as a bottom sheet. Used instead of `Alert.alert`, whose
 * buttons do nothing on web.
 */
export function ConfirmSheet({
  visible,
  title,
  message,
  confirmLabel,
  busy = false,
  error,
  onConfirm,
  onCancel,
}: ConfirmSheetProps) {
  const t = useT();

  return (
    <BottomSheet
      visible={visible}
      onClose={busy ? () => undefined : onCancel}
      title={title}
      footer={
        <>
          <Button label={confirmLabel} variant="danger" icon="trash-outline" fullWidth loading={busy} onPress={onConfirm} />
          <Button label={t('common.actions.cancel')} variant="ghost" fullWidth disabled={busy} onPress={onCancel} />
        </>
      }
    >
      <AppText variant="body">{message}</AppText>
      {error ? (
        <AppText variant="caption" color="danger" accessibilityRole="alert">
          {error}
        </AppText>
      ) : null}
    </BottomSheet>
  );
}
