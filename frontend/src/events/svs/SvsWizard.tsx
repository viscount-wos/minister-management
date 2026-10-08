import { FormEvent, ReactNode, useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { AlertCircle, CheckCircle, XCircle, CalendarOff, Clock, Pencil, Mic, MicOff } from 'lucide-react';
import { BackLink, STEP_TITLE, StatusCard, WIZARD_CARD, WIZARD_PAGE, WizardNav } from '../../shared/WizardChrome';
import type { Round } from '../../shared/api';
import { ApiError, isApiError } from '../../shared/api';
import { errorText } from '../../shared/apiErrors';
import { FID_RE } from '../../shared/FidLookup';
import UseLastAnswers from '../../shared/UseLastAnswers';
import { Field } from '../../shared/fields';
import WizardSteps from '../ministry/WizardSteps';
import FurnaceLevelSelect from '../../shared/FurnaceLevelSelect';
import { usePageTitle } from '../../shared/usePageTitle';
import { useFormatDateTime } from '../../shared/DateTime';
import { useTimezone } from '../../shared/TimezoneContext';
import { formatTimeInTimezone, timezoneShortLabel } from '../../shared/timezone';
import FidHelp from '../../shared/FidHelp';
import {
  SVS_TIERS,
  SvsApplication,
  SvsSettings,
  SvsTroops,
  TROOP_TYPES,
  TroopType,
  battleHours,
  svsApi,
  svsTroops,
} from './api';
import { SVS_PATHS } from './paths';

// The SVS sign-up WIZARD (phone-first, owner brief 2026-10-08): much smaller than Frost Dragon Tyrant's.
//   1 Player (FID -> name, alliance)  2 Battle hours  3 Troops (camp FC + T10/T11)
//   4 Discord voice chat   5 Review -> Submit   (no role question: the battle planner assigns leaders, owner)
// Round flow exactly as the other wizards: FID lookup -> NEW (profile pre-filled from the SHARED profile, so
// Frost Dragon Tyrant data flows in; "Use my last answers" when an earlier SVS sign-up exists) or EDIT.

const TOTAL_STEPS = 5;
type Phase = 'loading' | 'noRound' | 'loadError' | 'closed' | 'wizard' | 'saved';

interface FormState {
  game_name: string;
  alliance: string;
  troops: SvsTroops;
  hours: string[];
  discord_vc: boolean | null;
}

const EMPTY: FormState = {
  game_name: '',
  alliance: '',
  troops: svsTroops(null),
  hours: [],
  discord_vc: null,
};

function answersToForm(a: SvsApplication['answers'] | undefined, hourIds: string[]) {
  return {
    hours: Array.isArray(a?.hours) ? hourIds.filter((h) => a!.hours!.includes(h)) : [],
    discord_vc: typeof a?.discord_vc === 'boolean' ? a.discord_vc : null,
  };
}

function stepForField(field: string | null, current: number): number {
  if (!field) return current;
  if (/^profile\.(game_name|alliance|fid)$/.test(field) || field === 'fid') return 1;
  if (field.startsWith('answers.hours')) return 2;
  if (field.startsWith('profile.troops')) return 3;
  if (field === 'answers.discord_vc') return 4;
  return current;
}

const FIELD_LABELS: [RegExp, string][] = [
  [/^profile\.game_name$/, 'tyrant:fields.ingameName'],
  [/^profile\.alliance$/, 'tyrant:fields.alliance'],
  [/^answers\.hours/, 'svs:step2.title'],
  [/^profile\.troops/, 'svs:step3.title'],
  [/^answers\.discord_vc$/, 'svs:step4.vc'],
];

/** A big tappable choice (radio semantics): VC yes/no, tier buttons. */
function Choice({
  testId,
  selected,
  onSelect,
  children,
  sub,
  icon,
  compact,
}: {
  testId: string;
  selected: boolean;
  onSelect: () => void;
  children: ReactNode;
  sub?: ReactNode;
  icon?: ReactNode;
  compact?: boolean;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      data-testid={testId}
      onClick={onSelect}
      className={`w-full flex items-center gap-3 ${compact ? 'justify-center min-h-[48px] px-3 py-2' : 'min-h-[60px] px-4 py-3 text-start'} rounded-lg border-2 font-medium transition-colors ${
        selected
          ? compact
            ? 'border-accent bg-accent text-dark-bg'
            : 'border-accent bg-accent/15 text-theme-text'
          : 'border-theme-border bg-dark-bg text-theme-text hover:border-accent'
      }`}
    >
      {icon && <span className={`shrink-0 ${selected ? (compact ? 'text-dark-bg' : 'text-accent') : 'text-theme-dim'}`}>{icon}</span>}
      <span className="min-w-0">
        <span className="block break-words">{children}</span>
        {sub && <span className="block text-sm font-normal text-theme-dim break-words">{sub}</span>}
      </span>
    </button>
  );
}

export default function SvsWizard() {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const fmt = useFormatDateTime();
  const { timezone } = useTimezone();
  usePageTitle(t('svs:apply.title'));
  const [params, setParams] = useSearchParams();

  const [phase, setPhase] = useState<Phase>('loading');
  const [step, setStep] = useState(1);
  const [round, setRound] = useState<Round<SvsSettings> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [invalidField, setInvalidField] = useState<string | null>(null);

  const [fidInput, setFidInput] = useState(params.get('fid') ?? '');
  const [fid, setFid] = useState('');
  const [mode, setMode] = useState<'new' | 'edit'>('new');
  const [knownProfile, setKnownProfile] = useState(false);
  /** The shared profile already has an alliance: then the alliance is optional here (owner: ask new players). */
  const [profileAlliance, setProfileAlliance] = useState('');
  const [form, setForm] = useState<FormState>(EMPTY);
  const [previous, setPrevious] = useState<SvsApplication | null>(null);
  const [lastApplied, setLastApplied] = useState(false);

  const hours = round ? battleHours(round.settings) : [];
  const loaded = fid !== '';
  const set = (patch: Partial<FormState>) => setForm((f) => ({ ...f, ...patch }));

  const loadRound = useCallback(async () => {
    try {
      const r = await svsApi.currentRound();
      setRound(r);
      return r;
    } catch (e) {
      setPhase(isApiError(e, 'NO_CURRENT_ROUND') ? 'noRound' : 'loadError');
      if (!isApiError(e, 'NO_CURRENT_ROUND')) setError(errorText(t, e));
      return null;
    }
  }, [t]);

  const loadPlayer = useCallback(
    async (theFid: string, r: Round<SvsSettings>) => {
      setBusy(true);
      setError('');
      setInvalidField(null);
      const orNull = <T,>(p: Promise<T>) =>
        p.catch((e) => {
          if (e instanceof ApiError && e.status === 404) return null;
          throw e;
        });
      try {
        const [prof, app, prev] = await Promise.all([
          orNull(svsApi.profile(theFid)),
          orNull(svsApi.currentApplication(theFid)),
          orNull(svsApi.previousApplication(theFid)),
        ]);
        const ids = battleHours(r.settings);
        const ally = (prof?.alliance ?? '').toUpperCase().slice(0, 3);
        setPrevious(prev);
        setLastApplied(false);
        setKnownProfile(!!prof);
        setProfileAlliance(ally);
        // Shared profile (Frost Dragon Tyrant writes it too): FC camps only, tiers T10/T11 only; anything else
        // (e.g. a Tyrant T9) shows unselected and must be picked.
        const profilePart = { game_name: prof?.game_name ?? '', alliance: ally, troops: svsTroops(prof?.troops) };
        setStep(1);
        setFid(theFid);
        if (app) {
          setMode('edit');
          setForm({ ...EMPTY, ...profilePart, ...answersToForm(app.answers, ids) });
          setPhase('wizard');
        } else {
          setMode('new');
          setForm({ ...EMPTY, ...profilePart });
          setPhase(r.is_closed_for_new ? 'closed' : 'wizard');
        }
      } catch (e) {
        if (isApiError(e, 'NO_CURRENT_ROUND')) setPhase('noRound');
        else setError(errorText(t, e));
      } finally {
        setBusy(false);
      }
    },
    [t],
  );

  useEffect(() => {
    let cancelled = false;
    loadRound().then((r) => {
      if (cancelled || !r) return;
      setPhase('wizard');
      const initial = params.get('fid');
      if (initial && FID_RE.test(initial)) loadPlayer(initial, r);
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const lookupFid = (e?: FormEvent) => {
    e?.preventDefault();
    if (!round || busy) return;
    const clean = fidInput.trim();
    if (!clean) {
      setInvalidField('fid');
      return setError(t('profile:fidRequired'));
    }
    if (!FID_RE.test(clean)) {
      setInvalidField('fid');
      return setError(t('profile:fidDigitsOnly'));
    }
    setError('');
    setInvalidField(null);
    setParams({ fid: clean }, { replace: true });
    loadPlayer(clean, round);
  };

  const changeFid = () => {
    setParams({}, { replace: true });
    setFid('');
    setStep(1);
    setError('');
    setInvalidField(null);
    setPhase('wizard');
  };

  const applyLastAnswers = () => {
    if (!previous) return;
    set(answersToForm(previous.answers, hours));
    setLastApplied(true);
  };

  const fail = (field: string, msgKey: string) => {
    setInvalidField(field);
    setError(t(msgKey));
    return false;
  };

  const validateStep = (s: number) => {
    if (s === 1) {
      if (!form.game_name.trim()) return fail('profile.game_name', 'ministry:form.required');
      if (!profileAlliance && !form.alliance.trim()) return fail('profile.alliance', 'profile:allianceRequired');
    }
    if (s === 2 && form.hours.length === 0) return fail('answers.hours', 'svs:errors.hoursRequired');
    if (s === 3) {
      for (const k of TROOP_TYPES) {
        if (!form.troops[k].furnace_level) return fail(`profile.troops.${k}.furnace_level`, 'svs:errors.troopsRequired');
        if (form.troops[k].tier == null) return fail(`profile.troops.${k}.tier`, 'svs:errors.troopsRequired');
      }
    }
    if (s === 4) {
      if (form.discord_vc == null) return fail('answers.discord_vc', 'svs:errors.vcRequired');
    }
    setError('');
    setInvalidField(null);
    return true;
  };

  const handleNext = () => {
    if (step === 1 && !loaded) return lookupFid();
    if (!validateStep(step)) return;
    setStep(step + 1);
  };

  const handleBack = () => {
    setError('');
    setInvalidField(null);
    if (step === 1) navigate(SVS_PATHS.home);
    else setStep(step - 1);
  };

  const clearIf = (field: string) => {
    if (invalidField === field) {
      setInvalidField(null);
      setError('');
    }
  };

  const submit = async () => {
    if (!round) return;
    for (const s of [1, 2, 3, 4]) {
      if (!validateStep(s)) return setStep(s);
    }
    setBusy(true);
    setError('');
    const alliance = form.alliance.trim().toUpperCase();
    try {
      const res = await svsApi.putApplication(fid, {
        profile: { game_name: form.game_name.trim(), ...(alliance ? { alliance } : {}), troops: form.troops },
        answers: {
          hours: hours.filter((h) => form.hours.includes(h)),
          discord_vc: form.discord_vc,
          language: i18n.language,
        },
      });
      setMode(res.created ? 'new' : 'edit');
      setPhase('saved');
    } catch (e) {
      if (isApiError(e, 'APPLICATIONS_CLOSED')) {
        setRound((r) => (r ? { ...r, is_closed_for_new: true } : r));
        setPhase('closed');
      } else if (isApiError(e, 'NO_CURRENT_ROUND') || isApiError(e, 'ROUND_CLOSED')) {
        setPhase('noRound');
      } else if (isApiError(e, 'VALIDATION_ERROR')) {
        setInvalidField(e.field);
        setStep(stepForField(e.field, step));
        const label = FIELD_LABELS.find(([re]) => e.field && re.test(e.field))?.[1];
        setError(label ? t('common:errors.invalidField', { field: t(label) }) : errorText(t, e));
      } else {
        setError(errorText(t, e, mode === 'edit' ? 'ministry:form.updateError' : 'ministry:form.submitError'));
      }
    } finally {
      setBusy(false);
    }
  };

  const backHomeButton = <BackLink onClick={() => navigate(SVS_PATHS.home)}>{t('svs:apply.backHome')}</BackLink>;

  // ------------------------------------------------------------ status states

  if (phase === 'loading') {
    return (
      <div className="min-h-[60vh] flex items-center justify-center p-4">
        <p className="text-theme-dim">{t('ministry:form.loading')}</p>
      </div>
    );
  }
  if (phase === 'noRound') {
    return (
      <StatusCard
        testId="no-round"
        tone="dim"
        icon={<CalendarOff className="w-20 h-20 text-theme-dim" aria-hidden="true" />}
        title={t('svs:apply.notOpenTitle')}
        body={t('svs:apply.notOpenBody')}
      >
        {backHomeButton}
      </StatusCard>
    );
  }
  if (phase === 'loadError') {
    return (
      <StatusCard testId="load-error" tone="danger" icon={<AlertCircle className="w-20 h-20 text-danger" aria-hidden="true" />} title={t('ministry:form.error')} body={error}>
        {backHomeButton}
      </StatusCard>
    );
  }
  if (phase === 'closed') {
    return (
      <StatusCard
        testId="applications-closed"
        tone="danger"
        icon={<XCircle className="w-20 h-20 text-danger" aria-hidden="true" />}
        title={t('tyrant:apply.closedTitle')}
        body={t('tyrant:apply.closedBody', { round: round?.name ?? '' })}
      >
        <div className="flex flex-col gap-4">
          <button type="button" onClick={changeFid} className="min-h-[44px] text-theme-dim hover:text-theme-text text-sm underline">
            {t('tyrant:apply.otherFid')}
          </button>
          {backHomeButton}
        </div>
      </StatusCard>
    );
  }
  if (phase === 'saved') {
    return (
      <StatusCard
        testId="save-success"
        tone="success"
        icon={<CheckCircle className="w-20 h-20 text-success" aria-hidden="true" />}
        title={t('tyrant:apply.savedTitle')}
        body={t(mode === 'new' ? 'tyrant:apply.savedNew' : 'tyrant:apply.savedEdit', { round: round?.name ?? '' })}
      >
        <div className="flex flex-col gap-4">
          <button
            type="button"
            data-testid="reopen-application"
            onClick={() => round && loadPlayer(fid, round)}
            className="min-h-[48px] px-6 py-3 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium transition-colors"
          >
            {t('tyrant:apply.viewMine')}
          </button>
          {backHomeButton}
        </div>
      </StatusCard>
    );
  }
  if (!round) return null;

  // ------------------------------------------------------------ the wizard

  const closingNote = round.closing_time ? (
    <p
      className={`flex items-center justify-center gap-2 text-sm font-medium ${round.is_closed_for_new ? 'text-warning' : 'text-success'}`}
      data-testid="closing-note"
    >
      <Clock className="w-4 h-4 shrink-0" aria-hidden="true" />
      {round.is_closed_for_new ? t('tyrant:apply.closedButEditable') : t('tyrant:home.closeAt', { time: fmt(round.closing_time) })}
    </p>
  ) : null;

  const stepHeader = (n: number) => (
    <div className="text-center mb-6">
      <h2 className={`${STEP_TITLE} mb-2`} data-testid="wizard-step-title">
        {t(`svs:step${n}.title`)}
      </h2>
      <p className="text-theme-dim">{t(`svs:step${n}.desc`)}</p>
    </div>
  );

  const setTroop = (kind: TroopType, key: 'furnace_level' | 'tier', v: string | number | null) => {
    if (v !== '' && v != null) clearIf(`profile.troops.${kind}.${key}`);
    set({ troops: { ...form.troops, [kind]: { ...form.troops[kind], [key]: v === '' ? null : v } } });
  };

  const showLocal = timezone !== 'UTC';
  const localTime = (h: string) => formatTimeInTimezone(h, timezone);
  const allHours = hours.length > 0 && hours.every((h) => form.hours.includes(h));
  const yes = (on: boolean) => (on ? <span className="text-success font-bold">✓</span> : <span className="text-theme-dim">—</span>);
  const dash = (v: ReactNode) => (v ? <bdi>{v}</bdi> : <span className="text-theme-dim">—</span>);

  const reviewSections: { step: number; rows: [ReactNode, ReactNode, string][] }[] = [
    {
      step: 1,
      rows: [
        [t('tyrant:fields.ingameName'), dash(form.game_name), 'game-name'],
        [t('tyrant:fields.fid'), dash(fid), 'fid'],
        [t('tyrant:fields.alliance'), dash(form.alliance || profileAlliance), 'alliance'],
      ],
    },
    {
      step: 2,
      rows: [
        [
          t('svs:step2.gameTime'),
          <span className="flex flex-wrap justify-end gap-1" key="h">
            {hours
              .filter((h) => form.hours.includes(h))
              .map((h) => (
                <span key={h} className="px-2 py-0.5 rounded bg-accent/20 text-accent text-xs font-semibold" data-hour={h}>
                  <bdi dir="ltr">{h}</bdi>
                </span>
              ))}
          </span>,
          'hours',
        ],
      ],
    },
    {
      step: 3,
      rows: TROOP_TYPES.map((k): [ReactNode, ReactNode, string] => [
        t(`tyrant:step4.${k}`),
        <bdi dir="ltr" key={k}>
          {`${form.troops[k].furnace_level || '—'} / ${form.troops[k].tier ? `T${form.troops[k].tier}` : '—'}`}
        </bdi>,
        `troop-${k}`,
      ]),
    },
    {
      step: 4,
      rows: [
        [t('svs:step4.vc'), form.discord_vc == null ? dash('') : yes(form.discord_vc), 'discord-vc'],
      ],
    },
  ];

  return (
    <div className={WIZARD_PAGE}>
      <div className={`${WIZARD_CARD} max-w-3xl`} data-testid="wizard" data-mode={loaded ? mode : 'lookup'}>
        <div className="text-center mb-6 space-y-1">
          <p className="text-lg font-semibold text-theme-text break-words" data-testid="application-heading" data-mode={loaded ? mode : 'lookup'}>
            {!loaded
              ? t('svs:apply.title')
              : mode === 'new'
                ? t('tyrant:apply.newFor', { round: round.name })
                : t('tyrant:apply.editFor', { round: round.name })}
          </p>
          {!loaded && (
            <p className="text-theme-dim" data-testid="round-name">
              {round.name}
            </p>
          )}
          {closingNote}
        </div>

        <WizardSteps step={step} total={TOTAL_STEPS} />

        {/* Step 1: Player */}
        {step === 1 && (
          <div data-testid="wizard-step-1">
            {stepHeader(1)}
            {!loaded ? (
              <form onSubmit={lookupFid} noValidate data-testid="fid-form">
                <p className="text-theme-dim text-center mb-6">{t('tyrant:apply.enterFid')}</p>
                <Field
                  id="fid-lookup"
                  name="fid"
                  testId="fid-input"
                  label={t('tyrant:fields.fid')}
                  required
                  placeholder={t('tyrant:fields.fidPlaceholder')}
                  inputMode="numeric"
                  autoComplete="off"
                  autoFocus
                  value={fidInput}
                  invalid={invalidField === 'fid'}
                  onChange={(e) => setFidInput(e.target.value)}
                />
                <FidHelp />
              </form>
            ) : (
              <div className="space-y-4" data-testid="profile-fields">
                <Field
                  id="profile-game-name"
                  name="game_name"
                  testId="profile-game-name"
                  label={t('tyrant:fields.ingameName')}
                  required
                  maxLength={64}
                  autoComplete="off"
                  value={form.game_name}
                  invalid={invalidField === 'profile.game_name'}
                  onChange={(e) => set({ game_name: e.target.value })}
                />
                <Field
                  id="profile-fid"
                  name="fid"
                  testId="profile-fid"
                  label={t('tyrant:fields.fid')}
                  value={fid}
                  readOnly
                  inputClassName="opacity-75 cursor-not-allowed"
                  hint={
                    <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <span data-testid="profile-status">{knownProfile ? t('profile:prefilled') : t('profile:newProfile')}</span>
                      <button type="button" onClick={changeFid} data-testid="change-fid" className="min-h-[44px] underline hover:text-theme-text">
                        {t('profile:changeFid')}
                      </button>
                    </span>
                  }
                />
                <Field
                  id="profile-alliance"
                  name="alliance"
                  testId="profile-alliance"
                  label={t('tyrant:fields.alliance')}
                  required={!profileAlliance}
                  maxLength={3}
                  autoComplete="off"
                  placeholder={t('tyrant:fields.alliancePlaceholder')}
                  inputClassName="uppercase"
                  value={form.alliance}
                  invalid={invalidField === 'profile.alliance'}
                  hint={profileAlliance ? t('svs:step1.allianceKnown') : t('svs:step1.allianceNew')}
                  onChange={(e) => set({ alliance: e.target.value.toUpperCase().slice(0, 3) })}
                />
                {mode === 'new' && (
                  <UseLastAnswers
                    available={!!previous}
                    previousRoundName={previous?.round_name}
                    applied={lastApplied}
                    onUse={applyLastAnswers}
                    disabled={busy}
                  />
                )}
              </div>
            )}
          </div>
        )}

        {/* Step 2: Battle hours (game time UTC, with the player's local time) */}
        {step === 2 && (
          <div data-testid="wizard-step-2">
            {stepHeader(2)}
            <p className="text-sm text-accent text-center mb-1 font-medium" data-testid="utc-note">
              {t('svs:step2.utcNote')}
            </p>
            {showLocal && (
              <p className="text-xs text-theme-dim text-center mb-4" data-testid="local-note">
                {t('svs:step2.localNote', { zone: timezoneShortLabel(timezone) })}
              </p>
            )}
            <div
              className={`grid grid-cols-2 min-[400px]:grid-cols-3 sm:grid-cols-5 gap-2 sm:gap-3 ${showLocal ? '' : 'mt-4'}`}
              key="hours"
              data-testid="hour-grid"
              role="group"
              aria-label={t('svs:step2.title')}
            >
              {hours.map((h) => {
                const on = form.hours.includes(h);
                return (
                  <button
                    key={h}
                    type="button"
                    aria-pressed={on}
                    data-testid={`hour-${h}`}
                    onClick={() => {
                      clearIf('answers.hours');
                      set({ hours: hours.filter((x) => (x === h ? !on : form.hours.includes(x))) });
                    }}
                    className={`min-h-[56px] px-2 py-2 rounded-lg border-2 font-semibold transition-colors ${
                      on ? 'bg-accent border-accent text-dark-bg' : `bg-dark-input text-theme-text hover:border-accent ${invalidField === 'answers.hours' ? 'border-danger' : 'border-theme-border'}`
                    }`}
                  >
                    <bdi dir="ltr" className="block text-lg leading-tight" data-testid="hour-utc">
                      {h} UTC
                    </bdi>
                    {showLocal && (
                      <bdi dir="ltr" className={`block text-xs mt-0.5 font-normal ${on ? 'opacity-80' : 'opacity-60'}`} data-testid="hour-local">
                        {localTime(h)}
                      </bdi>
                    )}
                  </button>
                );
              })}
            </div>
            <button
              type="button"
              onClick={() => {
                clearIf('answers.hours');
                set({ hours: allHours ? [] : [...hours] });
              }}
              data-testid="select-all-hours"
              aria-pressed={allHours}
              className="mt-4 w-full min-h-[48px] px-4 py-2 rounded-lg border border-theme-border text-theme-text hover:bg-dark-card-hover font-medium"
            >
              {allHours ? t('svs:step2.clearAll') : t('svs:step2.selectAll')}
            </button>
          </div>
        )}

        {/* Step 3: Troops: camp FC level + T10/T11 */}
        {step === 3 && (
          <div data-testid="wizard-step-3">
            {stepHeader(3)}
            <p className="mb-4 p-3 rounded-lg bg-accent/10 border border-accent/30 text-sm text-theme-text" data-testid="camp-hint">
              <span className="block">{t('tyrant:step4.campHint')}</span>
              <span className="block mt-1 font-semibold">{t('svs:step3.tierHint')}</span>
            </p>
            <div className="space-y-4">
              {TROOP_TYPES.map((kind) => {
                const { furnace_level, tier } = form.troops[kind];
                return (
                  <div key={kind} className="bg-dark-bg p-4 rounded-lg border border-theme-border" data-testid={`troop-${kind}`}>
                    <h3 className="font-semibold text-lg text-accent mb-3">{t(`tyrant:step4.${kind}`)}</h3>
                    <div className="grid grid-cols-1 min-[340px]:grid-cols-2 gap-3 sm:gap-4 items-end">
                      <FurnaceLevelSelect
                        id={`troop-${kind}-furnace`}
                        label={t(`tyrant:step4.camp.${kind}`)}
                        fcOnly
                        required
                        emptyLabel="—"
                        value={furnace_level ?? ''}
                        invalid={invalidField === `profile.troops.${kind}.furnace_level`}
                        onChange={(code) => setTroop(kind, 'furnace_level', code)}
                      />
                      <div>
                        <p className="block text-sm font-medium text-theme-text mb-2" id={`troop-${kind}-tier-label`}>
                          {t('tyrant:step4.tLevel')}
                        </p>
                        <div
                          role="radiogroup"
                          aria-labelledby={`troop-${kind}-tier-label`}
                          data-testid={`troop-${kind}-tier`}
                          data-value={tier ?? ''}
                          className={`grid grid-cols-2 gap-2 rounded-lg ${invalidField === `profile.troops.${kind}.tier` ? 'ring-2 ring-danger' : ''}`}
                        >
                          {SVS_TIERS.map((n) => (
                            <Choice key={n} compact testId={`tier-${kind}-${n}`} selected={tier === n} onSelect={() => setTroop(kind, 'tier', n)}>
                              <bdi dir="ltr">T{n}</bdi>
                            </Choice>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Step 4: Discord voice chat */}
        {step === 4 && (
          <div data-testid="wizard-step-4" className="space-y-6">
            {stepHeader(4)}
            <fieldset>
              <legend className="block font-semibold text-theme-text mb-3">{t('svs:step4.vc')}</legend>
              <div role="radiogroup" className={`grid grid-cols-2 gap-3 rounded-lg ${invalidField === 'answers.discord_vc' ? 'ring-2 ring-danger' : ''}`} data-testid="vc-group">
                {[true, false].map((v) => (
                  <Choice
                    key={String(v)}
                    compact
                    testId={`vc-${v ? 'yes' : 'no'}`}
                    selected={form.discord_vc === v}
                    onSelect={() => {
                      clearIf('answers.discord_vc');
                      set({ discord_vc: v });
                    }}
                    icon={v ? <Mic className="w-5 h-5" aria-hidden="true" /> : <MicOff className="w-5 h-5" aria-hidden="true" />}
                  >
                    {t(v ? 'common:yes' : 'common:no')}
                  </Choice>
                ))}
              </div>
              <p className="text-xs text-theme-dim mt-2">{t('svs:step4.vcHint')}</p>
            </fieldset>
          </div>
        )}

        {/* Step 5: Review, with Edit per section */}
        {step === 5 && (
          <div data-testid="wizard-step-5">
            {stepHeader(5)}
            <div className="space-y-4">
              {reviewSections.map((sec) => (
                <div key={sec.step} className="bg-dark-bg p-4 sm:p-5 rounded-lg border border-theme-border" data-testid={`review-section-${sec.step}`}>
                  <div className="flex items-center justify-between gap-3 mb-3">
                    <h3 className="font-semibold text-lg text-accent min-w-0 break-words">{t(`svs:step${sec.step}.title`)}</h3>
                    <button
                      type="button"
                      onClick={() => setStep(sec.step)}
                      data-testid={`review-edit-${sec.step}`}
                      className="flex items-center gap-1 min-h-[44px] px-3 py-1 text-sm border border-theme-border rounded-lg text-theme-text hover:bg-dark-card-hover shrink-0"
                    >
                      <Pencil className="w-4 h-4" aria-hidden="true" />
                      {t('tyrant:step6.edit')}
                    </button>
                  </div>
                  <div className="divide-y divide-theme-border/50">
                    {sec.rows.map(([label, value, key]) => (
                      <div key={key} className="flex items-center justify-between gap-4 py-2 text-sm" data-testid={`review-${key}`}>
                        <span className="text-theme-dim min-w-0 break-words">{label}</span>
                        <span className="font-medium text-theme-text text-end min-w-0 break-words">{value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="mt-6 p-4 bg-danger/10 border border-danger/30 rounded-lg flex items-center gap-3" role="alert" data-testid="form-error">
            <AlertCircle className="w-5 h-5 text-danger shrink-0" aria-hidden="true" />
            <p className="text-danger">{error}</p>
          </div>
        )}

        <WizardNav isLast={step >= TOTAL_STEPS} busy={busy} mode={mode} onBack={handleBack} onNext={handleNext} onSubmit={submit} />
      </div>
    </div>
  );
}
