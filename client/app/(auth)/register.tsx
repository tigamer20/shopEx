/**
 * Sign-up screen. The account is created in the language currently shown (FR/EN toggle).
 * On success the root gate switches to the tabs by itself. 409 → "email already in use".
 */
import { useRouter } from 'expo-router';
import { useRef, useState } from 'react';
import type { TextInputInstance } from 'react-native';

import { useAuth } from '@/auth';
import {
  PASSWORD_MIN_LENGTH,
  registerErrorKey,
  validateDisplayName,
  validateEmail,
  validateNewPassword,
  type ValidationMessage,
} from '@/auth/validation';
import { AuthScaffold } from '@/components/auth/AuthScaffold';
import { PasswordField } from '@/components/auth/PasswordField';
import { Button, ErrorBanner, TextField } from '@/components/ui';
import { useLanguage, useT } from '@/i18n';

export default function RegisterScreen() {
  const t = useT();
  const router = useRouter();
  const { register } = useAuth();
  const { language } = useLanguage();
  const emailRef = useRef<TextInputInstance>(null);
  const passwordRef = useRef<TextInputInstance>(null);
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<unknown>(null);

  const nameError = validateDisplayName(displayName);
  const emailError = validateEmail(email);
  const passwordError = validateNewPassword(password);
  const message = (error: ValidationMessage | null) => (submitted && error ? t(error.key, error.params) : null);

  async function submit(): Promise<void> {
    setSubmitted(true);
    if (nameError || emailError || passwordError || submitting) {
      return;
    }
    setSubmitting(true);
    setServerError(null);
    try {
      await register({ display_name: displayName.trim(), email: email.trim(), password, language });
    } catch (error) {
      setServerError(error);
      setSubmitting(false);
    }
  }

  return (
    <AuthScaffold
      title={t('auth.register_title')}
      subtitle={t('auth.register_subtitle')}
      footer={
        <>
          <Button
            label={t('auth.register_cta')}
            icon="person-add-outline"
            size="lg"
            fullWidth
            loading={submitting}
            onPress={() => void submit()}
          />
          <Button label={t('auth.have_account')} variant="ghost" fullWidth onPress={() => router.replace('/login')} />
        </>
      }
    >
      {serverError ? <ErrorBanner message={t(registerErrorKey(serverError))} /> : null}
      <TextField
        label={t('auth.display_name')}
        placeholder={t('auth.display_name_placeholder')}
        value={displayName}
        onChangeText={setDisplayName}
        error={message(nameError)}
        autoComplete="name"
        textContentType="name"
        autoCapitalize="words"
        returnKeyType="next"
        submitBehavior="submit"
        onSubmitEditing={() => emailRef.current?.focus()}
      />
      <TextField
        ref={emailRef}
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
        hint={t('auth.password_hint', { min: PASSWORD_MIN_LENGTH })}
        autoComplete="new-password"
        textContentType="newPassword"
        passwordRules={`minlength: ${PASSWORD_MIN_LENGTH};`}
        returnKeyType="go"
        onSubmitEditing={() => void submit()}
      />
    </AuthScaffold>
  );
}
