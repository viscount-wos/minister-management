import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Field } from './fields';
import TimezoneSelector from './TimezoneSelector';
import FurnaceLevelSelect from './FurnaceLevelSelect';

// Persistent profile fields (one profile per FID, shared by every event).
// They always pre-fill from the stored profile.

export interface ProfileFormValues {
  game_name: string;
  alliance: string;
  timezone: string;
  /** '' = not given, else a furnace code 'FC1'..'FC10' / '1'..'30' (shared/furnace.ts). */
  furnace_level: string;
}

export const EMPTY_PROFILE: ProfileFormValues = { game_name: '', alliance: '', timezone: 'UTC', furnace_level: '' };

interface ProfileFieldsProps {
  fid: string;
  value: ProfileFormValues;
  onChange: (next: ProfileFormValues) => void;
  /** API field path of the field the server rejected, e.g. 'profile.alliance'. */
  invalidField?: string | null;
  disabled?: boolean;
  /** false = no timezone select (the ministry wizard picks the timezone on the time steps, as v1.4). */
  showTimezone?: boolean;
  /** Shown under the read-only FID, e.g. a "use a different FID" link. */
  fidHint?: ReactNode;
}

export default function ProfileFields({
  fid,
  value,
  onChange,
  invalidField,
  disabled,
  showTimezone = true,
  fidHint,
}: ProfileFieldsProps) {
  const { t } = useTranslation();
  const set = (patch: Partial<ProfileFormValues>) => onChange({ ...value, ...patch });

  return (
    <div className="space-y-4" data-testid="profile-fields">
      <Field
        id="profile-fid"
        name="fid"
        testId="profile-fid"
        label={t('profile:playerID')}
        value={fid}
        readOnly
        inputClassName="opacity-75 cursor-not-allowed"
        hint={fidHint}
      />
      <div className="grid grid-cols-3 gap-4">
        <Field
          id="profile-game-name"
          name="game_name"
          testId="profile-game-name"
          className="col-span-2"
          label={t('profile:gameName')}
          required
          maxLength={64}
          disabled={disabled}
          value={value.game_name}
          invalid={invalidField === 'profile.game_name'}
          onChange={(e) => set({ game_name: e.target.value })}
        />
        <Field
          id="profile-alliance"
          name="alliance"
          testId="profile-alliance"
          label={t('profile:alliance')}
          required
          maxLength={3}
          disabled={disabled}
          placeholder={t('profile:alliancePlaceholder')}
          inputClassName="uppercase"
          value={value.alliance}
          invalid={invalidField === 'profile.alliance'}
          onChange={(e) => set({ alliance: e.target.value.toUpperCase().slice(0, 3) })}
        />
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        {showTimezone && (
          <div>
            <label htmlFor="profile-timezone" className="block text-sm font-medium text-theme-text mb-2">
              {t('profile:timezone')}
            </label>
            <TimezoneSelector
              id="profile-timezone"
              testId="profile-timezone"
              value={value.timezone}
              onChange={(tz) => set({ timezone: tz })}
            />
          </div>
        )}
        <FurnaceLevelSelect
          id="profile-furnace-level"
          testId="profile-furnace-level"
          disabled={disabled}
          label={`${t('profile:furnaceLevel')} (${t('profile:optional')})`}
          value={value.furnace_level}
          invalid={invalidField === 'profile.furnace_level'}
          onChange={(code) => set({ furnace_level: code })}
        />
      </div>
    </div>
  );
}

/** Profile form values -> API body. */
export function profileToInput(v: ProfileFormValues) {
  return {
    game_name: v.game_name.trim(),
    alliance: v.alliance.trim().toUpperCase(),
    timezone: v.timezone,
    furnace_level: v.furnace_level || null,
  };
}
