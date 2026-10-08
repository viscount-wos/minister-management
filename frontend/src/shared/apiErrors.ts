import type { TFunction } from 'i18next';
import { ApiError } from './api';

// Turns an API failure into a translated, user-facing message. Server error
// strings are English-only, so they are never shown directly; the machine
// `code` (and `field`, for VALIDATION_ERROR) pick the translated text.

/** Translation key of the label for an API `field` path. */
const FIELD_LABELS: Record<string, string> = {
  fid: 'profile:playerID',
  'profile.fid': 'profile:playerID',
  'profile.game_name': 'profile:gameName',
  'profile.alliance': 'profile:alliance',
  'profile.timezone': 'common:header.timezone',
  'profile.furnace_level': 'profile:furnaceLevel',
  'answers.construction_speedups_days': 'ministry:form.constructionSpeedups',
  'answers.research_speedups_days': 'ministry:form.researchSpeedups',
  'answers.troop_training_speedups_days': 'ministry:form.troopSpeedups',
  'answers.general_speedups_days': 'ministry:form.generalSpeedups',
  'answers.fire_crystals': 'ministry:form.fireCrystals',
  'answers.refined_fire_crystals': 'ministry:form.refinedFireCrystals',
  'answers.fire_crystal_shards': 'ministry:form.fireCrystalShards',
  'answers.time_slots_by_day': 'ministry:form.timePreferences',
  name: 'admin:round.name',
  closing_time: 'admin:closingTime',
  state_number: 'admin:stateNumber',
  state_generation: 'admin:heroes.generation',
  'answers.hours': 'svs:step2.title',
  'answers.role': 'svs:step4.roleTitle',
  'answers.discord_vc': 'svs:step4.vc',
  password: 'admin:password',
};

export function fieldLabelKey(field: string | null | undefined): string | null {
  if (!field) return null;
  if (FIELD_LABELS[field]) return FIELD_LABELS[field];
  if (field.startsWith('answers.time_slots')) return FIELD_LABELS['answers.time_slots_by_day'];
  if (field.startsWith('profile.troops')) return 'tyrant:step4.title';
  return null;
}

/** Translated message for any error thrown by the API client. */
export function errorText(t: TFunction, err: unknown, fallbackKey = 'common:errors.generic'): string {
  if (!(err instanceof ApiError)) return t(fallbackKey);
  switch (err.code) {
    case 'APPLICATIONS_CLOSED':
      return t('common:errors.applicationsClosed');
    case 'NO_CURRENT_ROUND':
      return t('common:errors.noCurrentRound');
    case 'ROUND_CLOSED':
      return t('common:errors.roundClosed');
    case 'TOO_MANY_ATTEMPTS':
      return t('common:errors.tooManyAttempts');
    case 'RATE_LIMITED':
      return t('common:errors.rateLimited');
    case 'RETRY':
      return t('common:errors.retry');
    case 'NOT_FOUND':
      return t('common:errors.notFound');
    case 'CONFLICT':
      return t('common:errors.conflict');
    case 'NETWORK_ERROR':
      return t('common:errors.network');
    case 'VALIDATION_ERROR': {
      const key = fieldLabelKey(err.field);
      return key ? t('common:errors.invalidField', { field: t(key) }) : t('common:errors.invalidInput');
    }
    case 'UNAUTHORIZED':
    case 'INVALID_TOKEN':
    case 'TOKEN_EXPIRED':
      return t('admin:sessionExpired');
    case 'INVALID_PASSWORD':
      return t('admin:invalidPassword');
    case 'APPLICATION_EXISTS':
      return t('admin:addPlayer.exists');
    case 'ROUND_ALREADY_OPEN':
      return t('admin:round.alreadyOpen');
    default:
      return t(fallbackKey);
  }
}
