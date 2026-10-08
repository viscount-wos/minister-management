import { FormEvent, ReactNode, useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { AlertCircle, CheckCircle, XCircle, CalendarOff, Clock, Pencil } from 'lucide-react';
import { BackLink, STEP_TITLE, StatusCard, WIZARD_CARD, WIZARD_PAGE, WizardNav } from '../../shared/WizardChrome';
import type { Round } from '../../shared/api';
import { ApiError, isApiError } from '../../shared/api';
import { errorText } from '../../shared/apiErrors';
import { FID_RE } from '../../shared/FidLookup';
import UseLastAnswers from '../../shared/UseLastAnswers';
import { Field, INPUT_CLASS } from '../../shared/fields';
import WizardSteps from '../ministry/WizardSteps';
import FurnaceLevelSelect from '../../shared/FurnaceLevelSelect';
import { toFcCode } from '../../shared/furnace';
import {
  ROLES,
  Role,
  TIERS,
  TROOP_TYPES,
  TroopType,
  Troops,
  TyrantAnswers,
  TyrantApplication,
  TyrantSettings,
  parseTroops,
  tyrantApi,
} from './api';
import { TYRANT_PATHS } from './paths';
import { usePageTitle } from '../../shared/usePageTitle';

// The Frost Dragon Tyrant sign-up WIZARD, ported from the live tyrantpoll app
// (templates/poll.html), same 6 steps in the same order:
//   1 Player Identity  2 Availability  3 Player Stats  4 Troop Levels
//   5 Roles Wanted     6 Review (Edit per section) -> Submit
// with the ministry wizard's round flow on top (SPEC "Concepts"): step 1 starts
// with the FID; then NEW mode for <round> (profile pre-filled, round answers
// blank, "Use my last answers" when an earlier Tyrant sign-up exists) or EDIT
// mode (everything pre-filled). Closing time: NEW is blocked once it passes.

const TOTAL_STEPS = 6;
type Phase = 'loading' | 'noRound' | 'loadError' | 'closed' | 'wizard' | 'saved';

interface FormState {
  game_name: string;
  alliance: string;
  discord_id: string;
  /** '' or a furnace code (shared/furnace.ts). */
  furnace_level: string;
  /** Power in millions, as typed. */
  power_m: string;
  gem_spend: string;
  troops: Troops;
  availability: string[];
  discord_vc: boolean;
  roles: Role[];
}

const blankTroops = (): Troops => parseTroops(null);

/** Drops camp levels the Tyrant form doesn't offer (legacy pre-FC codes) so the player picks an FC level. */
function fcOnlyTroops(tr: Troops): Troops {
  const out = { ...tr };
  for (const k of TROOP_TYPES) out[k] = { ...tr[k], furnace_level: toFcCode(tr[k].furnace_level) || null };
  return out;
}

const EMPTY: FormState = {
  game_name: '',
  alliance: '',
  discord_id: '',
  furnace_level: '',
  power_m: '',
  gem_spend: '',
  troops: blankTroops(),
  availability: [],
  discord_vc: false,
  roles: [],
};

/** Round answers of a stored application -> form fields (unknown windows/roles dropped). */
function answersToForm(a: Partial<TyrantAnswers> | undefined, windowIds: string[]) {
  const roles = Array.isArray(a?.roles) ? a!.roles.filter((r): r is Role => (ROLES as readonly string[]).includes(r)) : [];
  return {
    availability: Array.isArray(a?.availability) ? a!.availability.filter((w) => windowIds.includes(w)) : [],
    discord_vc: !!a?.discord_vc,
    gem_spend: a?.gem_spend != null ? String(a.gem_spend) : '',
    roles,
  };
}

/** 410500000 -> "410.5" */
function powerToMillions(p: number | null | undefined): string {
  if (p == null) return '';
  return String(Math.round((p / 1_000_000) * 100) / 100);
}

/** API field path -> wizard step that holds it. */
function stepForField(field: string | null, current: number): number {
  if (!field) return current;
  if (/^profile\.(game_name|alliance|discord_id|fid)$/.test(field) || field === 'fid') return 1;
  if (field.startsWith('answers.availability') || field === 'answers.discord_vc') return 2;
  if (field === 'profile.furnace_level' || field === 'profile.power' || field === 'answers.gem_spend') return 3;
  if (field.startsWith('profile.troops')) return 4;
  if (field.startsWith('answers.roles')) return 5;
  return current;
}

const FIELD_LABELS: [RegExp, string][] = [
  [/^profile\.game_name$/, 'tyrant:fields.ingameName'],
  [/^profile\.alliance$/, 'tyrant:fields.alliance'],
  [/^profile\.discord_id$/, 'tyrant:fields.discordId'],
  [/^answers\.availability/, 'tyrant:step2.title'],
  [/^profile\.furnace_level$/, 'tyrant:step3.furnaceLevel'],
  [/^profile\.power$/, 'tyrant:step3.power'],
  [/^answers\.gem_spend$/, 'tyrant:step3.gemSpend'],
  [/^profile\.troops/, 'tyrant:step4.title'],
  [/^answers\.roles/, 'tyrant:step5.title'],
];

function Select({ id, label, value, onChange, children, invalid, required }: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  children: ReactNode;
  invalid?: boolean;
  required?: boolean;
}) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-theme-text mb-2">
        {label}
      </label>
      <select
        id={id}
        data-testid={id}
        value={value}
        required={required}
        aria-invalid={invalid || undefined}
        onChange={(e) => onChange(e.target.value)}
        className={`${INPUT_CLASS} ${invalid ? 'border-danger' : 'border-theme-border'}`}
      >
        {children}
      </select>
    </div>
  );
}

function CheckRow({ id, checked, onChange, children, tag, emphasis }: {
  id: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  children: ReactNode;
  tag?: ReactNode;
  emphasis?: boolean;
}) {
  return (
    <label
      htmlFor={id}
      className={`flex items-center gap-3 min-h-[52px] px-4 py-3 rounded-lg border cursor-pointer transition-colors ${
        checked ? 'border-accent bg-accent/10' : 'border-theme-border bg-dark-bg hover:bg-dark-card-hover'
      } ${emphasis ? 'font-semibold' : ''}`}
    >
      <input
        id={id}
        data-testid={id}
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="w-5 h-5 shrink-0 accent-accent"
      />
      <span className="text-theme-text min-w-0 break-words">{children}</span>
      {tag && <span className="ms-auto shrink-0 px-2 py-1 rounded bg-accent/20 text-accent text-xs font-semibold">{tag}</span>}
    </label>
  );
}

/** "11:01-11:15" kept left-to-right inside Arabic text. */
const TimeRange = ({ start, end }: { start: string; end: string }) => (
  <bdi dir="ltr">
    {start}–{end}
  </bdi>
);

export default function TyrantWizard() {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  usePageTitle(t('tyrant:apply.title'));
  const [params, setParams] = useSearchParams();

  const [phase, setPhase] = useState<Phase>('loading');
  const [step, setStep] = useState(1);
  const [round, setRound] = useState<Round<TyrantSettings> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [invalidField, setInvalidField] = useState<string | null>(null);

  const [fidInput, setFidInput] = useState(params.get('fid') ?? '');
  const [fid, setFid] = useState('');
  const [mode, setMode] = useState<'new' | 'edit'>('new');
  const [knownProfile, setKnownProfile] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [previous, setPrevious] = useState<TyrantApplication | null>(null);
  const [lastApplied, setLastApplied] = useState(false);

  const windows = round?.settings.windows ?? [];
  const windowIds = windows.map((w) => w.id);
  const loaded = fid !== '';
  const set = (patch: Partial<FormState>) => setForm((f) => ({ ...f, ...patch }));

  const loadRound = useCallback(async () => {
    try {
      const r = await tyrantApi.currentRound();
      setRound(r);
      return r;
    } catch (e) {
      setPhase(isApiError(e, 'NO_CURRENT_ROUND') ? 'noRound' : 'loadError');
      if (!isApiError(e, 'NO_CURRENT_ROUND')) setError(errorText(t, e));
      return null;
    }
  }, [t]);

  const loadPlayer = useCallback(
    async (theFid: string, r: Round<TyrantSettings>) => {
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
          orNull(tyrantApi.profile(theFid)),
          orNull(tyrantApi.currentApplication(theFid)),
          orNull(tyrantApi.previousApplication(theFid)),
        ]);
        const ids = r.settings.windows.map((w) => w.id);
        setPrevious(prev);
        setLastApplied(false);
        setKnownProfile(!!prof);
        const profilePart = {
          game_name: prof?.game_name ?? '',
          alliance: (prof?.alliance ?? '').toUpperCase().slice(0, 3),
          discord_id: prof?.discord_id ?? '',
          // Tyrant offers FC1-FC10 only (owner rule p2d): a saved pre-FC furnace / camp shows as unselected
          // and must be re-picked (the wizard requires them).
          furnace_level: toFcCode(prof?.furnace_level),
          power_m: powerToMillions(prof?.power),
          troops: fcOnlyTroops(parseTroops(prof?.troops)),
        };
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
    set(answersToForm(previous.answers, windowIds));
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
      if (!form.alliance.trim()) return fail('profile.alliance', 'profile:allianceRequired');
    }
    if (s === 3) {
      if (!form.furnace_level) return fail('profile.furnace_level', 'tyrant:errors.furnaceRequired');
      const p = form.power_m.trim();
      if (p && !(Number.isFinite(Number(p)) && Number(p) >= 0)) return fail('profile.power', 'tyrant:errors.power');
      const g = form.gem_spend.trim();
      if (g && !/^\d{1,10}$/.test(g)) return fail('answers.gem_spend', 'tyrant:errors.gems');
    }
    if (s === 4) {
      // camp level AND tier are required for all three troop types (owner rule p2d); any combination is fine
      for (const k of TROOP_TYPES) {
        if (!form.troops[k].furnace_level) return fail(`profile.troops.${k}.furnace_level`, 'tyrant:errors.campRequired');
        if (form.troops[k].tier == null) return fail(`profile.troops.${k}.tier`, 'tyrant:errors.campRequired');
      }
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
    if (step === 1) navigate(TYRANT_PATHS.home);
    else setStep(step - 1);
  };

  const toggle = <T extends string>(list: T[], item: T, on: boolean, order: readonly T[]) =>
    order.filter((x) => (x === item ? on : list.includes(x)));

  const submit = async () => {
    if (!round) return;
    for (const s of [1, 3, 4]) {
      if (!validateStep(s)) return setStep(s);
    }
    setBusy(true);
    setError('');
    const pm = form.power_m.trim();
    try {
      const res = await tyrantApi.putApplication(fid, {
        profile: {
          game_name: form.game_name.trim(),
          alliance: form.alliance.trim().toUpperCase(),
          discord_id: form.discord_id.trim() || null,
          furnace_level: form.furnace_level || null,
          power: pm ? Math.round(Number(pm) * 1_000_000) : null,
          troops: form.troops,
        },
        answers: {
          availability: windowIds.filter((w) => form.availability.includes(w)),
          discord_vc: form.discord_vc,
          gem_spend: form.gem_spend.trim() ? parseInt(form.gem_spend, 10) : null,
          roles: ROLES.filter((r) => form.roles.includes(r)),
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

  const backHomeButton = <BackLink onClick={() => navigate(TYRANT_PATHS.home)}>{t('tyrant:apply.backHome')}</BackLink>;

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
        title={t('tyrant:apply.notOpenTitle')}
        body={t('tyrant:apply.notOpenBody')}
      >
        {backHomeButton}
      </StatusCard>
    );
  }
  if (phase === 'loadError') {
    return (
      <StatusCard
        testId="load-error"
        tone="danger"
        icon={<AlertCircle className="w-20 h-20 text-danger" aria-hidden="true" />}
        title={t('ministry:form.error')}
        body={error}
      >
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
      {round.is_closed_for_new
        ? t('tyrant:apply.closedButEditable')
        : t('tyrant:home.closeAt', { time: new Date(round.closing_time).toLocaleString() })}
    </p>
  ) : null;

  const stepHeader = (n: number) => (
    <div className="text-center mb-6">
      <h2 className={`${STEP_TITLE} mb-2`} data-testid="wizard-step-title">
        {t(`tyrant:step${n}.title`)}
      </h2>
      <p className="text-theme-dim">{t(`tyrant:step${n}.desc`)}</p>
    </div>
  );

  const setTroop = (kind: TroopType, key: 'furnace_level' | 'tier', v: string) => {
    // picking the missing value clears its "required" message (the next missing one shows on Next)
    if (invalidField === `profile.troops.${kind}.${key}` && v !== '') {
      setInvalidField(null);
      setError('');
    }
    set({
      troops: {
        ...form.troops,
        [kind]: { ...form.troops[kind], [key]: v === '' ? null : key === 'tier' ? Number(v) : v },
      },
    });
  };

  const allWindows = windows.length > 0 && windows.every((w) => form.availability.includes(w.id));
  const yes = (on: boolean) => (on ? <span className="text-success font-bold">✓</span> : <span className="text-theme-dim">—</span>);
  const dash = (v: string) => (v ? <bdi>{v}</bdi> : <span className="text-theme-dim">—</span>);
  const troopText = (kind: TroopType) => {
    const { furnace_level, tier } = form.troops[kind];
    return `${furnace_level || '—'} / ${tier ? `T${tier}` : '—'}`;
  };

  const reviewSections: { step: number; rows: [ReactNode, ReactNode, string][] }[] = [
    {
      step: 1,
      rows: [
        [t('tyrant:fields.ingameName'), dash(form.game_name), 'game-name'],
        [t('tyrant:fields.fid'), dash(fid), 'fid'],
        [t('tyrant:fields.discordId'), dash(form.discord_id), 'discord-id'],
        [t('tyrant:fields.alliance'), dash(form.alliance), 'alliance'],
      ],
    },
    {
      step: 2,
      rows: [
        ...windows.map((w): [ReactNode, ReactNode, string] => [
          w.rush ? (
            <>
              {t('tyrant:step2.openingRush')} <TimeRange start={w.start} end={w.end} />
            </>
          ) : (
            <TimeRange start={w.start} end={w.end} />
          ),
          yes(form.availability.includes(w.id)),
          `window-${w.id}`,
        ]),
        [t('tyrant:step2.discordVc'), yes(form.discord_vc), 'discord-vc'],
      ],
    },
    {
      step: 3,
      rows: [
        [t('tyrant:step3.furnaceLevel'), dash(form.furnace_level), 'furnace-level'],
        [t('tyrant:step3.power'), dash(form.power_m.trim()), 'power'],
        [t('tyrant:step3.gemSpend'), dash(form.gem_spend.trim()), 'gem-spend'],
      ],
    },
    {
      step: 4,
      rows: TROOP_TYPES.map((k): [ReactNode, ReactNode, string] => [t(`tyrant:step4.${k}`), <bdi dir="ltr">{troopText(k)}</bdi>, `troop-${k}`]),
    },
    {
      step: 5,
      rows: ROLES.map((r): [ReactNode, ReactNode, string] => [t(`tyrant:roles.${r}`), yes(form.roles.includes(r)), `role-${r}`]),
    },
  ];

  return (
    <div className={WIZARD_PAGE}>
      <div className={`${WIZARD_CARD} max-w-3xl`} data-testid="wizard" data-mode={loaded ? mode : 'lookup'}>
        <div className="text-center mb-6 space-y-1">
          <p className="text-lg font-semibold text-theme-text break-words" data-testid="application-heading" data-mode={loaded ? mode : 'lookup'}>
            {!loaded
              ? t('tyrant:apply.title')
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

        {/* Step 1: Player Identity */}
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
                  id="profile-discord-id"
                  name="discord_id"
                  testId="profile-discord-id"
                  label={`${t('tyrant:fields.discordId')} (${t('profile:optional')})`}
                  placeholder={t('tyrant:fields.discordPlaceholder')}
                  maxLength={64}
                  autoComplete="off"
                  value={form.discord_id}
                  invalid={invalidField === 'profile.discord_id'}
                  onChange={(e) => set({ discord_id: e.target.value })}
                />
                <Field
                  id="profile-alliance"
                  name="alliance"
                  testId="profile-alliance"
                  label={t('tyrant:fields.alliance')}
                  required
                  maxLength={3}
                  autoComplete="off"
                  placeholder={t('tyrant:fields.alliancePlaceholder')}
                  inputClassName="uppercase"
                  value={form.alliance}
                  invalid={invalidField === 'profile.alliance'}
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

        {/* Step 2: Availability */}
        {step === 2 && (
          <div data-testid="wizard-step-2">
            {stepHeader(2)}
            <p className="text-sm text-accent text-center mb-4 font-medium" data-testid="utc-note">
              {t('tyrant:step2.utcNote')}
            </p>
            <div className="space-y-3" key="windows">
              <CheckRow
                id="select-all-windows"
                checked={allWindows}
                emphasis
                onChange={(on) => set({ availability: on ? [...windowIds] : [] })}
              >
                {t('tyrant:step2.selectAll')}
              </CheckRow>
              {windows.map((w) => (
                <CheckRow
                  key={w.id}
                  id={`window-${w.id}`}
                  checked={form.availability.includes(w.id)}
                  onChange={(on) => set({ availability: toggle(form.availability, w.id, on, windowIds) })}
                  tag={w.rush ? <TimeRange start={w.start} end={w.end} /> : undefined}
                >
                  {w.rush ? t('tyrant:step2.openingRush') : <TimeRange start={w.start} end={w.end} />}
                </CheckRow>
              ))}
            </div>
            <hr className="my-6 border-theme-border" />
            <CheckRow id="discord-vc" checked={form.discord_vc} onChange={(on) => set({ discord_vc: on })}>
              {t('tyrant:step2.discordVc')}
            </CheckRow>
          </div>
        )}

        {/* Step 3: Player Stats */}
        {step === 3 && (
          <div data-testid="wizard-step-3" className="space-y-4">
            {stepHeader(3)}
            <FurnaceLevelSelect
              id="furnace-level"
              label={t('tyrant:step3.furnaceLevel')}
              fcOnly
              required
              value={form.furnace_level}
              invalid={invalidField === 'profile.furnace_level'}
              onChange={(code) => {
                if (invalidField === 'profile.furnace_level' && code) {
                  setInvalidField(null);
                  setError('');
                }
                set({ furnace_level: code });
              }}
            />
            <Field
              id="power-millions"
              name="power"
              testId="power-millions"
              type="number"
              min={0}
              step="any"
              inputMode="decimal"
              label={t('tyrant:step3.power')}
              placeholder={t('tyrant:step3.powerPlaceholder')}
              value={form.power_m}
              invalid={invalidField === 'profile.power'}
              onChange={(e) => set({ power_m: e.target.value })}
            />
            <Field
              id="gem-spend"
              name="gem_spend"
              testId="gem-spend"
              type="number"
              min={0}
              step={1}
              inputMode="numeric"
              label={t('tyrant:step3.gemSpend')}
              placeholder={t('tyrant:step3.gemPlaceholder')}
              value={form.gem_spend}
              invalid={invalidField === 'answers.gem_spend'}
              onChange={(e) => set({ gem_spend: e.target.value })}
            />
          </div>
        )}

        {/* Step 4: Troop Levels */}
        {step === 4 && (
          <div data-testid="wizard-step-4">
            {stepHeader(4)}
            <p className="mb-4 p-3 rounded-lg bg-accent/10 border border-accent/30 text-sm text-theme-text" data-testid="camp-hint">
              {t('tyrant:step4.campHint')}
            </p>
            <div className="space-y-4">
              {TROOP_TYPES.map((kind) => {
                const { furnace_level, tier } = form.troops[kind];
                const tiers = tier != null && !TIERS.includes(tier) ? [tier, ...TIERS] : TIERS;
                return (
                  <div key={kind} className="bg-dark-bg p-4 rounded-lg border border-theme-border" data-testid={`troop-${kind}`}>
                    <h3 className="font-semibold text-lg text-accent mb-3">{t(`tyrant:step4.${kind}`)}</h3>
                    {/* items-end: a camp label that wraps to two lines keeps both selects on one baseline */}
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
                      <Select
                        id={`troop-${kind}-tier`}
                        label={t('tyrant:step4.tLevel')}
                        required
                        value={tier != null ? String(tier) : ''}
                        invalid={invalidField === `profile.troops.${kind}.tier` || invalidField === `profile.troops.${kind}`}
                        onChange={(v) => setTroop(kind, 'tier', v)}
                      >
                        <option value="">—</option>
                        {tiers.map((n) => (
                          <option key={n} value={String(n)}>
                            T{n}
                          </option>
                        ))}
                      </Select>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Step 5: Roles Wanted */}
        {step === 5 && (
          <div data-testid="wizard-step-5">
            {stepHeader(5)}
            <div className="space-y-3">
              {ROLES.map((r) => (
                <CheckRow
                  key={r}
                  id={`role-${r}`}
                  checked={form.roles.includes(r)}
                  onChange={(on) => set({ roles: toggle(form.roles, r, on, ROLES) })}
                >
                  {t(`tyrant:roles.${r}`)}
                </CheckRow>
              ))}
            </div>
          </div>
        )}

        {/* Step 6: Review, with Edit per section (as tyrantpoll) */}
        {step === 6 && (
          <div data-testid="wizard-step-6">
            {stepHeader(6)}
            <div className="space-y-4">
              {reviewSections.map((sec) => (
                <div key={sec.step} className="bg-dark-bg p-4 sm:p-5 rounded-lg border border-theme-border" data-testid={`review-section-${sec.step}`}>
                  <div className="flex items-center justify-between gap-3 mb-3">
                    <h3 className="font-semibold text-lg text-accent min-w-0 break-words">{t(`tyrant:step${sec.step}.title`)}</h3>
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

        <WizardNav
          isLast={step >= TOTAL_STEPS}
          busy={busy}
          mode={mode}
          onBack={handleBack}
          onNext={handleNext}
          onSubmit={submit}
        />
      </div>
    </div>
  );
}
