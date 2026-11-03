/**
 * Profile: display name, language, search radius, travel mode, tutorial replay, about
 * (licences, OSM attribution, demo-price notice), sign out and account deletion (ARCHITECTURE §5).
 */
import Ionicons from '@expo/vector-icons/Ionicons';
import Constants from 'expo-constants';
import { useCallback, useState, type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import { LANGUAGES, TRAVEL_MODES, type TravelMode, type UserUpdate } from '@/api/types';
import { useAuth } from '@/auth';
import { validateDisplayName } from '@/auth/validation';
import { ConfirmSheet } from '@/components/lists/ConfirmSheet';
import { AppText, Badge, Button, Card, Chip, ErrorBanner, Screen, TextField, type IconName } from '@/components/ui';
import { useLanguage, useT } from '@/i18n';
import { useSettings } from '@/settings/SettingsProvider';
import { useTheme } from '@/theme';
import { errorMessageKey } from '@/utils/errors';

const RADIUS_OPTIONS_KM = [2, 5, 10, 20, 50] as const;

const TRAVEL_MODE_ICONS: Record<TravelMode, IconName> = {
  driving: 'car-outline',
  walking: 'walk-outline',
  cycling: 'bicycle-outline',
};

function Section({ title, children }: { title: string; children: ReactNode }) {
  const theme = useTheme();
  return (
    <View style={{ gap: theme.spacing.sm }}>
      <AppText variant="heading">{title}</AppText>
      <Card style={{ gap: theme.spacing.lg }}>{children}</Card>
    </View>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  const theme = useTheme();
  return (
    <View style={{ gap: theme.spacing.sm }}>
      <AppText variant="label">{label}</AppText>
      <View style={[styles.chips, { gap: theme.spacing.sm }]}>{children}</View>
      {hint ? <AppText variant="small">{hint}</AppText> : null}
    </View>
  );
}

export default function ProfileScreen() {
  const theme = useTheme();
  const t = useT();
  const { language, setLanguage } = useLanguage();
  const { user, logout, updateUser, refreshUser, deleteAccount } = useAuth();
  const { replayOnboarding } = useSettings();

  // Null while not editing: the field then follows the account's name.
  const [nameDraft, setNameDraft] = useState<string | null>(null);
  const [savingName, setSavingName] = useState(false);
  const [nameSaved, setNameSaved] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<unknown>(null);

  const accountName = user?.display_name ?? '';
  const name = nameDraft ?? accountName;

  const save = useCallback(
    async (patch: UserUpdate) => {
      setSaveError(null);
      try {
        await updateUser(patch);
        return true;
      } catch (error) {
        setSaveError(error);
        return false;
      }
    },
    [updateUser],
  );

  const nameError = validateDisplayName(name);
  const trimmedName = name.trim();
  const nameChanged = trimmedName !== accountName;

  async function saveName(): Promise<void> {
    if (nameError || !nameChanged) {
      return;
    }
    setSavingName(true);
    setNameSaved(false);
    const ok = await save({ display_name: trimmedName });
    setSavingName(false);
    if (ok) {
      setNameDraft(null);
      setNameSaved(true);
    }
  }

  async function retryLoad(): Promise<void> {
    setLoadError(null);
    try {
      await refreshUser();
    } catch (error) {
      setLoadError(error);
    }
  }

  async function removeAccount(): Promise<void> {
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteAccount();
      // Signed out: the root gate shows the login screen.
    } catch (error) {
      setDeleteError(error);
      setDeleting(false);
    }
  }

  const version = Constants.expoConfig?.version ?? '1.0.0';
  const initial = (user?.display_name.trim().charAt(0) || '?').toUpperCase();

  return (
    <Screen contentContainerStyle={{ gap: theme.spacing.xl }}>
      <AppText variant="title">{t('profile.title')}</AppText>

      {user ? (
        <View style={[styles.identity, { gap: theme.spacing.md }]}>
          <View
            style={[styles.avatar, { backgroundColor: theme.colors.primary, borderRadius: theme.radius.pill }]}
            accessibilityElementsHidden
            importantForAccessibility="no-hide-descendants"
          >
            <AppText variant="title" style={{ color: theme.colors.onPrimary }}>
              {initial}
            </AppText>
          </View>
          <View style={styles.identityText}>
            <AppText variant="heading" numberOfLines={1}>
              {user.display_name}
            </AppText>
            <AppText variant="caption" numberOfLines={1}>
              {user.email}
            </AppText>
          </View>
        </View>
      ) : (
        <ErrorBanner
          message={loadError ? t(errorMessageKey(loadError)) : t('profile.profile_unavailable')}
          onRetry={() => void retryLoad()}
        />
      )}

      {saveError ? <ErrorBanner message={t(errorMessageKey(saveError))} /> : null}

      {user ? (
        <Section title={t('profile.account')}>
          <TextField
            label={t('profile.display_name')}
            value={name}
            onChangeText={(value) => {
              setNameDraft(value);
              setNameSaved(false);
            }}
            error={nameDraft !== null && nameError ? t(nameError.key, nameError.params) : null}
            autoComplete="name"
            textContentType="name"
            returnKeyType="done"
            onSubmitEditing={() => void saveName()}
            maxLength={80}
          />
          <View style={[styles.row, { gap: theme.spacing.md }]}>
            <Button
              label={t('profile.save_name')}
              icon="checkmark"
              variant="secondary"
              loading={savingName}
              disabled={!nameChanged || nameError !== null}
              onPress={() => void saveName()}
            />
            {nameSaved ? <Badge label={t('profile.saved')} tone="success" icon="checkmark" /> : null}
          </View>
        </Section>
      ) : null}

      <Section title={t('profile.preferences')}>
        <Field label={t('profile.language')}>
          {LANGUAGES.map((code) => (
            <Chip
              key={code}
              label={t(`common.languages.${code}`)}
              selected={language === code}
              onPress={() => void setLanguage(code)}
            />
          ))}
        </Field>

        {user ? (
          <>
            <Field label={t('profile.radius')} hint={t('profile.radius_hint')}>
              {RADIUS_OPTIONS_KM.map((km) => (
                <Chip
                  key={km}
                  label={t('profile.radius_value', { km })}
                  selected={user.search_radius_km === km}
                  onPress={() => void save({ search_radius_km: km })}
                />
              ))}
            </Field>
            <Field label={t('profile.travel_mode')}>
              {TRAVEL_MODES.map((mode) => (
                <Chip
                  key={mode}
                  icon={TRAVEL_MODE_ICONS[mode]}
                  label={t(`profile.travel_modes.${mode}`)}
                  selected={user.travel_mode === mode}
                  onPress={() => void save({ travel_mode: mode })}
                />
              ))}
            </Field>
          </>
        ) : null}
      </Section>

      <Section title={t('profile.tutorial')}>
        <Button
          label={t('profile.replay_tutorial')}
          variant="secondary"
          icon="play-circle-outline"
          fullWidth
          onPress={replayOnboarding}
        />
      </Section>

      <Section title={t('profile.about')}>
        <View style={[styles.row, { gap: theme.spacing.sm }]}>
          <Ionicons name="basket" size={18} color={theme.colors.primary} />
          <AppText variant="subtitle">{t('common.app_name')}</AppText>
          <AppText variant="caption">{t('profile.version', { version })}</AppText>
        </View>

        <View
          style={[
            styles.notice,
            { gap: theme.spacing.sm, padding: theme.spacing.md, borderRadius: theme.radius.md, backgroundColor: theme.colors.surface },
          ]}
        >
          <Badge label={t('profile.demo_title')} tone="warning" icon="flask-outline" />
          <AppText variant="caption" color="text">
            {t('common.demo_prices')}
          </AppText>
        </View>

        <View style={{ gap: theme.spacing.sm }}>
          <AppText variant="label">{t('profile.licences.title')}</AppText>
          {(['map_data', 'map_library', 'icons', 'brands'] as const).map((key) => (
            <View key={key} style={[styles.bullet, { gap: theme.spacing.sm }]}>
              <AppText variant="caption">•</AppText>
              <AppText variant="caption" style={styles.bulletText}>
                {t(`profile.licences.${key}`)}
              </AppText>
            </View>
          ))}
        </View>

        <AppText variant="small">{t('common.osm_attribution')}</AppText>
      </Section>

      <View style={{ gap: theme.spacing.md }}>
        <Button label={t('profile.logout')} variant="secondary" icon="log-out-outline" fullWidth onPress={() => void logout()} />
        {user ? (
          <Button
            label={t('profile.delete_account')}
            variant="ghost"
            icon="trash-outline"
            fullWidth
            onPress={() => {
              setDeleteError(null);
              setConfirmDelete(true);
            }}
          />
        ) : null}
      </View>

      <ConfirmSheet
        visible={confirmDelete}
        title={t('profile.delete_confirm_title')}
        message={t('profile.delete_confirm_body')}
        confirmLabel={t('profile.delete_account')}
        busy={deleting}
        error={deleteError ? t(errorMessageKey(deleteError)) : null}
        onConfirm={() => void removeAccount()}
        onCancel={() => setConfirmDelete(false)}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  identity: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  avatar: {
    width: 64,
    height: 64,
    alignItems: 'center',
    justifyContent: 'center',
  },
  identityText: {
    flex: 1,
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
  },
  notice: {
    alignItems: 'flex-start',
  },
  bullet: {
    flexDirection: 'row',
  },
  bulletText: {
    flex: 1,
  },
});
