/**
 * Sign-in screen. On success the root gate switches to the tabs by itself (no redirect here).
 * 401 → generic "invalid email or password", 429 → "too many attempts".
 */
import { useRouter } from 'expo-router';
import { useRef, useState } from 'react';
import type { TextInputInstance } from 'react-native';

import { useAuth } from '@/auth';
import { loginErrorKey, validateEmail, validateLoginPassword, type ValidationMessage } from '@/auth/validation';
import { AuthScaffold } from '@/components/auth/AuthScaffold';
import { PasswordField } from '@/components/auth/PasswordField';
import { Button, ErrorBanner, TextField } from '@/components/ui';
import { useT } from '@/i18n';

export default function LoginScreen() {
  const t = useT();
  const router = useRouter();
  const { login } = useAuth();
  const passwordRef = useRef<TextInputInstance>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<unknown>(null);

  const emailError = validateEmail(email);
  const passwordError = validateLoginPassword(password);
  const message = (error: ValidationMessage | null) => (submitted && error ? t(error.key, error.params) : null);

  async function submit(): Promise<void> {
    setSubmitted(true);
    if (emailError || passwordError || submitting) {
      return;
    }
    setSubmitting(true);
    setServerError(null);
    try {
      await login({ email: email.trim(), password });
      // The gate navigates away; this screen unmounts.
    } catch (error) {
      setServerError(error);
      setSubmitting(false);
    }
  }

  return (
    <AuthScaffold
      title={t('auth.login_title')}
      subtitle={t('auth.login_subtitle')}
      footer={
        <>
          <Button
            label={t('auth.login_cta')}
            icon="log-in-outline"
            size="lg"
            fullWidth
            loading={submitting}
            onPress={() => void submit()}
          />
          <Button label={t('auth.no_account')} variant="ghost" fullWidth onPress={() => router.replace('/register')} />
        </>
      }
    >
      {serverError ? <ErrorBanner message={t(loginErrorKey(serverError))} /> : null}
      <TextField
        label={t('auth.email')}
        placeholder={t('auth.email_placeholder')}
        value={email}
        onChangeText={setEmail}
        error={message(emailError)}
        keyboardType="email-address"
        autoCapitalize="none"
        autoCorrect={false}
        autoComplete="email"
        textContentType="username"
        inputMode="email"
        returnKeyType="next"
        submitBehavior="submit"
        onSubmitEditing={() => passwordRef.current?.focus()}
      />
      <PasswordField
        ref={passwordRef}
        label={t('auth.password')}
        value={password}
        onChangeText={setPassword}
        error={message(passwordError)}
        autoComplete="current-password"
        textContentType="password"
        returnKeyType="go"
        onSubmitEditing={() => void submit()}
      />
    </AuthScaffold>
  );
}
