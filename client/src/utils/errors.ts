/**
 * Maps any thrown value to a user-facing i18n key, so screens can write
 * `t(errorMessageKey(error))` instead of showing raw server messages.
 */
import { isApiError } from '@/api/client';
import type { TranslationKey } from '@/i18n/types';

export function errorMessageKey(error: unknown): TranslationKey {
  if (!isApiError(error)) {
    return 'common.errors.generic';
  }
  switch (error.kind) {
    case 'network':
      return 'common.errors.network';
    case 'timeout':
      return 'common.errors.timeout';
    case 'aborted':
      return 'common.errors.generic';
    case 'http':
      break;
  }
  switch (error.status) {
    case 400:
    case 422:
      return 'common.errors.validation';
    case 401:
      return 'common.errors.unauthorized';
    case 403:
      return 'common.errors.forbidden';
    case 404:
      return 'common.errors.not_found';
    case 409:
      return 'common.errors.conflict';
    case 429:
      return 'common.errors.rate_limited';
    case 503:
      return 'common.errors.unavailable';
    default:
      return error.status >= 500 ? 'common.errors.server' : 'common.errors.generic';
  }
}
