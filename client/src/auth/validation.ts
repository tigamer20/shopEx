/**
 * Client-side checks for the auth and profile forms, mirroring the server rules (ARCHITECTURE §4):
 * password 8..128 characters (never trimmed), display name 1..60 characters after trimming.
 * Each validator returns an i18n key plus its params, or null when the value is valid.
 * The server stays the authority: these only spare a round trip and give precise messages.
 */
import { isApiError } from '@/api/client';
import type { TranslationKey, TranslationParams } from '@/i18n/types';
import { errorMessageKey } from '@/utils/errors';

export const PASSWORD_MIN_LENGTH = 8;
export const PASSWORD_MAX_LENGTH = 128;
export const DISPLAY_NAME_MAX_LENGTH = 60;
const EMAIL_MAX_LENGTH = 254;

/** Deliberately loose (one "@", a dot in the domain, no spaces): the server does the real check. */
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export interface ValidationMessage {
  key: TranslationKey;
  params?: TranslationParams;
}

export function validateEmail(value: string): ValidationMessage | null {
  const email = value.trim();
  if (!email) {
    return { key: 'auth.errors.email_required' };
  }
  if (email.length > EMAIL_MAX_LENGTH || !EMAIL_PATTERN.test(email)) {
    return { key: 'auth.errors.email_invalid' };
  }
  return null;
}

/** Login only requires a password: its answer must not reveal the password policy. */
export function validateLoginPassword(value: string): ValidationMessage | null {
  return value ? null : { key: 'auth.errors.password_required' };
}

export function validateNewPassword(value: string): ValidationMessage | null {
  if (!value) {
    return { key: 'auth.errors.password_required' };
  }
  if (value.length < PASSWORD_MIN_LENGTH) {
    return { key: 'auth.errors.password_too_short', params: { min: PASSWORD_MIN_LENGTH } };
  }
  if (value.length > PASSWORD_MAX_LENGTH) {
    return { key: 'auth.errors.password_too_long', params: { max: PASSWORD_MAX_LENGTH } };
  }
  return null;
}

export function validateDisplayName(value: string): ValidationMessage | null {
  const name = value.trim();
  if (!name) {
    return { key: 'auth.errors.display_name_required' };
  }
  if (name.length > DISPLAY_NAME_MAX_LENGTH) {
    return { key: 'auth.errors.display_name_too_long', params: { max: DISPLAY_NAME_MAX_LENGTH } };
  }
  return null;
}

/** Login failures: 401 is a generic "invalid credentials" (never says which field was wrong). */
export function loginErrorKey(error: unknown): TranslationKey {
  if (isApiError(error) && error.kind === 'http' && error.status === 401) {
    return 'auth.errors.invalid_credentials';
  }
  return errorMessageKey(error);
}

/** Sign-up failures: 409 means the email already has an account. */
export function registerErrorKey(error: unknown): TranslationKey {
  if (isApiError(error) && error.kind === 'http' && error.status === 409) {
    return 'auth.errors.email_taken';
  }
  return errorMessageKey(error);
}
