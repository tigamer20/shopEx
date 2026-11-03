import { ApiError } from '@/api/client';

import {
  DISPLAY_NAME_MAX_LENGTH,
  loginErrorKey,
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
  registerErrorKey,
  validateDisplayName,
  validateEmail,
  validateLoginPassword,
  validateNewPassword,
} from '../validation';

describe('validateEmail', () => {
  it('requires a value', () => {
    expect(validateEmail('   ')?.key).toBe('auth.errors.email_required');
  });

  it('rejects malformed addresses', () => {
    for (const email of ['camille', 'camille@', '@example.ca', 'cam ille@example.ca', 'camille@example']) {
      expect({ email, key: validateEmail(email)?.key }).toEqual({ email, key: 'auth.errors.email_invalid' });
    }
  });

  it('accepts a normal address, ignoring surrounding spaces', () => {
    expect(validateEmail(' camille@example.ca ')).toBeNull();
  });
});

describe('passwords', () => {
  it('only requires a value at login', () => {
    expect(validateLoginPassword('')?.key).toBe('auth.errors.password_required');
    expect(validateLoginPassword('x')).toBeNull();
  });

  it('enforces the server length policy for new passwords', () => {
    expect(validateNewPassword('')?.key).toBe('auth.errors.password_required');
    expect(validateNewPassword('a'.repeat(PASSWORD_MIN_LENGTH - 1))).toEqual({
      key: 'auth.errors.password_too_short',
      params: { min: PASSWORD_MIN_LENGTH },
    });
    expect(validateNewPassword('a'.repeat(PASSWORD_MAX_LENGTH + 1))).toEqual({
      key: 'auth.errors.password_too_long',
      params: { max: PASSWORD_MAX_LENGTH },
    });
    expect(validateNewPassword('a'.repeat(PASSWORD_MIN_LENGTH))).toBeNull();
  });

  it('does not trim passwords (spaces count)', () => {
    expect(validateNewPassword(' '.repeat(PASSWORD_MIN_LENGTH))).toBeNull();
  });
});

describe('validateDisplayName', () => {
  it('requires a non-blank name', () => {
    expect(validateDisplayName('  ')?.key).toBe('auth.errors.display_name_required');
  });

  it('limits the trimmed length', () => {
    expect(validateDisplayName(` ${'a'.repeat(DISPLAY_NAME_MAX_LENGTH)} `)).toBeNull();
    expect(validateDisplayName('a'.repeat(DISPLAY_NAME_MAX_LENGTH + 1))?.key).toBe('auth.errors.display_name_too_long');
  });
});

describe('server error mapping', () => {
  it('maps a login 401 to the generic invalid-credentials message', () => {
    expect(loginErrorKey(new ApiError(401, 'Invalid credentials'))).toBe('auth.errors.invalid_credentials');
  });

  it('maps a login 429 to the rate-limit message', () => {
    expect(loginErrorKey(new ApiError(429, 'Too many attempts'))).toBe('common.errors.rate_limited');
  });

  it('maps a sign-up 409 to "email taken"', () => {
    expect(registerErrorKey(new ApiError(409, 'Email already registered'))).toBe('auth.errors.email_taken');
    expect(loginErrorKey(new ApiError(409, 'conflict'))).toBe('common.errors.conflict');
  });

  it('falls back to the shared messages for other failures', () => {
    expect(registerErrorKey(new ApiError(429, null))).toBe('common.errors.rate_limited');
    expect(registerErrorKey(new ApiError(0, null, 'network'))).toBe('common.errors.network');
    expect(loginErrorKey(new Error('boom'))).toBe('common.errors.generic');
  });
});
