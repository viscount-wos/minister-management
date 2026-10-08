import { FormEvent, useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { AlertCircle, CheckCircle, XCircle, CalendarOff, Clock } from 'lucide-react';
import { BackLink, STEP_TITLE, StatusCard, WIZARD_CARD, WIZARD_PAGE, WizardNav } from '../../shared/WizardChrome';
import api, { Application, DayType, Heatmap, MinistrySettings, PlayerAssignments, Round, isApiError } from '../../shared/api';
import { errorText } from '../../shared/apiErrors';
import { FID_RE } from '../../shared/FidLookup';
import ProfileFields, { EMPTY_PROFILE, ProfileFormValues, profileToInput } from '../../shared/ProfileFields';
import UseLastAnswers from '../../shared/UseLastAnswers';
import { Field } from '../../shared/fields';
import TimezoneSelector from '../../shared/TimezoneSelector';
import { useTimezone } from '../../shared/TimezoneContext';
import { toFurnaceCode } from '../../shared/furnace';
import { getTimezoneAbbr } from '../../shared/timezone';
import TimeWithUtc from '../../shared/TimeWithUtc';
import {
  AnswersForm,
  CRYSTAL_FIELDS,
  DAY_TYPES,
  SPEEDUP_FIELDS,
  answersToForm,
  blankAnswers,
  formToAnswers,
  toNumber,
} from './answers';
import { SlotGrid, ToleranceNote, useDayTypeLabel } from './TimeSlotPicker';
import MyAssignments from './MyAssignments';
import WizardSteps from './WizardSteps';
import { MINISTRY_PATHS } from './paths';
import { usePageTitle } from '../../shared/usePageTitle';
import { useFormatDateTime } from '../../shared/DateTime';
import FidHelp from '../../shared/FidHelp';
import GuideLink from '../../shared/guide/GuideLink';

// The ministry application WIZARD, restored from v1.4's PlayerForm:
//   1 Player information (+ speedups)   2 Construction day times
//   3 Research day times                 4 Troop training day times
//   5 Review & confirm
// Same steps, order, indicator, per-step checks (v1.4 wording) and the
// per-day "no slots selected" confirm. Rounds on top (SPEC "Concepts"):
//   - step 1 starts with the FID. After lookup the wizard is EDIT mode for
//     "<round>" when this FID already applied in the current round (every step
//     pre-filled, v1.4's update page: current assignments on top, "Update"
//     button) or NEW mode (profile pre-filled, round answers blank, with
//     "Use my last answers" when an earlier application exists).
//   - closing time: NEW applications are blocked once it passes (403
//     APPLICATIONS_CLOSED); existing ones stay editable while the round is open.

const TOTAL_STEPS = 5;
const DAY_STEP: Record<number, DayType> = { 2: 'construction', 3: 'research', 4: 'troop' };

type Phase = 'loading' | 'noRound' | 'loadError' | 'closed' | 'wizard' | 'saved';

/** "Label: value" pair on the review step (v1.4 layout). */
function ReviewItem({ label, children, testId }: { label: string; children: React.ReactNode; testId?: string }) {
  return (
    <div data-testid={testId}>
      <span className="text-theme-dim">{label}:</span>
      <span className="ms-2 font-medium text-theme-text">{children}</span>
    </div>
  );
}

export default function ApplicationWizard() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const fmt = useFormatDateTime();
  usePageTitle(t('ministry:apply.title'));
  const [params, setParams] = useSearchParams();
  const { timezone, setTimezone } = useTimezone();
  const dayTypeLabel = useDayTypeLabel();

  const [phase, setPhase] = useState<Phase>('loading');
  const [step, setStep] = useState(1);
  const [round, setRound] = useState<Round<MinistrySettings> | null>(null);
  const [heatmap, setHeatmap] = useState<Heatmap>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [invalidField, setInvalidField] = useState<string | null>(null);

  // Step 1 starts with the FID; the rest of the wizard opens once it is looked up.
  const [fidInput, setFidInput] = useState(params.get('fid') ?? '');
  const [fid, setFid] = useState('');
  const [mode, setMode] = useState<'new' | 'edit'>('new');
  const [profile, setProfile] = useState<ProfileFormValues>(EMPTY_PROFILE);
  const [knownProfile, setKnownProfile] = useState(false);
  const [answers, setAnswers] = useState<AnswersForm>(blankAnswers);
  const [previous, setPrevious] = useState<Application | null>(null);
  const [lastApplied, setLastApplied] = useState(false);
  const [assignments, setAssignments] = useState<PlayerAssignments | null>(null);

  const settings = round?.settings;
  const researchDay = settings?.research_day ?? 'tuesday';
  const showCrystals = !!settings?.show_fire_crystals;
  const loaded = fid !== '';

  const loadRound = useCallback(async () => {
    try {
      const r = await api.currentRound<MinistrySettings>('ministry');
      setRound(r);
      api.ministry.heatmap().then(setHeatmap).catch(() => {});
      return r;
    } catch (e) {
      setPhase(isApiError(e, 'NO_CURRENT_ROUND') ? 'noRound' : 'loadError');
      if (!isApiError(e, 'NO_CURRENT_ROUND')) setError(errorText(t, e));
      return null;
    }
  }, [t]);

  const loadPlayer = useCallback(
    async (theFid: string, r: Round<MinistrySettings>) => {
      setBusy(true);
      setError('');
      setInvalidField(null);
      try {
        const [prof, app, prev] = await Promise.all([
          api.orNull(api.profile(theFid)),
          api.orNull(api.currentApplication('ministry', theFid)),
          api.orNull(api.previousApplication('ministry', theFid)),
        ]);
        setPrevious(prev);
        setLastApplied(false);
        setKnownProfile(!!prof);
        const tz = prof?.timezone || timezone;
        if (prof?.timezone) setTimezone(prof.timezone);
        setProfile({
          game_name: prof?.game_name ?? '',
          alliance: (prof?.alliance ?? '').toUpperCase().slice(0, 3),
          timezone: tz,
          furnace_level: toFurnaceCode(prof?.furnace_level),
        });
        setStep(1);
        if (app) {
          setMode('edit');
          setAnswers(answersToForm(app.answers));
          api.ministry.playerAssignments(theFid).then(setAssignments).catch(() => setAssignments(null));
          setFid(theFid);
          setPhase('wizard');
        } else {
          setMode('new');
          setAnswers(blankAnswers());
          setAssignments(null);
          setFid(theFid);
          setPhase(r.is_closed_for_new ? 'closed' : 'wizard');
        }
      } catch (e) {
        if (isApiError(e, 'NO_CURRENT_ROUND')) setPhase('noRound');
        else setError(errorText(t, e));
      } finally {
        setBusy(false);
      }
    },
    [t, timezone, setTimezone],
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
    setInvalidField(null);
    if (!clean) {
      setInvalidField('fid');
      return setError(t('profile:fidRequired'));
    }
    if (!FID_RE.test(clean)) {
      setInvalidField('fid');
      return setError(t('profile:fidDigitsOnly'));
    }
    setError('');
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
    setAnswers(answersToForm(previous.answers));
    setLastApplied(true);
  };

  const handleTimezone = (tz: string) => {
    setTimezone(tz);
    setProfile((p) => ({ ...p, timezone: tz }));
  };

  const toggleSlot = (dayType: DayType, utc: string) =>
    setAnswers((a) => {
      const cur = a.time_slots_by_day[dayType];
      return {
        ...a,
        time_slots_by_day: {
          ...a.time_slots_by_day,
          [dayType]: cur.includes(utc) ? cur.filter((s) => s !== utc) : [...cur, utc],
        },
      };
    });

  const validateStep1 = () => {
    if (!profile.game_name.trim()) {
      setInvalidField('profile.game_name');
      setError(t('ministry:form.required'));
      return false;
    }
    if (!profile.alliance.trim()) {
      setInvalidField('profile.alliance');
      setError(t('profile:allianceRequired'));
      return false;
    }
    setError('');
    setInvalidField(null);
    return true;
  };

  const handleNext = () => {
    if (step === 1 && !loaded) return lookupFid();
    if (step === 1 && !validateStep1()) return;
    // v1.4: warn when a day has no time slots selected
    const dayType = DAY_STEP[step];
    if (dayType && answers.time_slots_by_day[dayType].length === 0 && !window.confirm(t('ministry:form.noTimeSlotsConfirm'))) {
      return;
    }
    setError('');
    setStep(step + 1);
  };

  const handleBack = () => {
    setError('');
    setInvalidField(null);
    if (step === 1) navigate(MINISTRY_PATHS.home);
    else setStep(step - 1);
  };

  /** Step that holds a server-rejected field, so the player lands on it. */
  const stepForField = (field: string | null) => {
    if (!field) return step;
    if (field.startsWith('answers.time_slots')) {
      const day = DAY_TYPES.find((d) => field.includes(d));
      return day ? Number(Object.keys(DAY_STEP).find((k) => DAY_STEP[Number(k)] === day)) : 2;
    }
    return field.startsWith('profile.') || field.startsWith('answers.') ? 1 : step;
  };

  const submit = async () => {
    if (!round || !validateStep1()) {
      setStep(1);
      return;
    }
    setBusy(true);
    setError('');
    try {
      const res = await api.putApplication('ministry', fid, {
        profile: profileToInput(profile),
        answers: formToAnswers(answers),
      });
      setMode(res.created ? 'new' : 'edit');
      setPhase('saved');
    } catch (e) {
      if (isApiError(e, 'APPLICATIONS_CLOSED')) {
        setRound((r) => (r ? { ...r, is_closed_for_new: true } : r));
        setPhase('closed');
      } else if (isApiError(e, 'NO_CURRENT_ROUND') || isApiError(e, 'ROUND_CLOSED')) {
        setPhase('noRound');
      } else {
        if (isApiError(e, 'VALIDATION_ERROR')) {
          setInvalidField(e.field);
          setStep(stepForField(e.field));
        }
        setError(errorText(t, e, mode === 'edit' ? 'ministry:form.updateError' : 'ministry:form.submitError'));
      }
    } finally {
      setBusy(false);
    }
  };

  const backHomeButton = <BackLink onClick={() => navigate(MINISTRY_PATHS.home)}>{t('ministry:update.backHome')}</BackLink>;

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
        title={t('ministry:apply.notOpenTitle')}
        body={t('ministry:apply.notOpenBody')}
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
        title={t('ministry:home.applicationsClosed')}
        body={t('ministry:apply.closedBody', { round: round?.name ?? '' })}
      >
        <div className="flex flex-col gap-4">
          <button type="button" onClick={changeFid} className="min-h-[44px] text-theme-dim hover:text-theme-text text-sm underline">
            {t('ministry:apply.otherFid')}
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
        title={t('ministry:form.success')}
        body={t(mode === 'new' ? 'ministry:apply.savedNew' : 'ministry:apply.savedEdit', { round: round?.name ?? '' })}
      >
        <div className="flex flex-col gap-4">
          <button
            type="button"
            data-testid="reopen-application"
            onClick={() => round && loadPlayer(fid, round)}
            className="min-h-[48px] px-6 py-3 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium transition-colors"
          >
            {t('ministry:apply.viewMine')}
          </button>
          {backHomeButton}
        </div>
      </StatusCard>
    );
  }

  if (!round || !settings) return null;

  // ------------------------------------------------------------ the wizard

  const closingNote = round.closing_time ? (
    <p
      className={`flex items-center justify-center gap-2 text-sm font-medium ${round.is_closed_for_new ? 'text-warning' : 'text-success'}`}
      data-testid="closing-note"
    >
      <Clock className="w-4 h-4 shrink-0" aria-hidden="true" />
      {round.is_closed_for_new
        ? t('ministry:apply.closedButEditable')
        : t('ministry:home.applicationsCloseAt', { time: fmt(round.closing_time) })}
    </p>
  ) : null;

  const dayType = DAY_STEP[step];
  const numberField = (key: (typeof SPEEDUP_FIELDS)[number]['key'] | (typeof CRYSTAL_FIELDS)[number]['key'], label: string, integer: boolean) => (
    <Field
      key={key}
      id={`answer-${key}`}
      name={key}
      testId={`answer-${key}`}
      type="number"
      min={0}
      step={integer ? 1 : 0.1}
      inputMode={integer ? 'numeric' : 'decimal'}
      placeholder="0"
      label={t(label)}
      value={answers[key]}
      invalid={invalidField === `answers.${key}`}
      onChange={(e) => setAnswers((a) => ({ ...a, [key]: e.target.value }))}
    />
  );

  return (
    <div className={WIZARD_PAGE}>
      <div className={`${WIZARD_CARD} max-w-4xl`} data-testid="wizard" data-mode={loaded ? mode : 'lookup'}>
        {/* Which round this is for, and whether it is a new application or an edit */}
        <div className="text-center mb-6 space-y-1">
          <p className="text-lg font-semibold text-theme-text break-words" data-testid="application-heading" data-mode={loaded ? mode : 'lookup'}>
            {!loaded
              ? t('ministry:apply.title')
              : mode === 'new'
                ? t('ministry:apply.newFor', { round: round.name })
                : t('ministry:apply.editFor', { round: round.name })}
          </p>
          {!loaded && (
            <p className="text-theme-dim" data-testid="round-name">
              {round.name}
            </p>
          )}
          {closingNote}
        </div>

        <WizardSteps step={step} total={TOTAL_STEPS} />

        {/* Step 1: Player Information */}
        {step === 1 && (
          <div data-testid="wizard-step-1">
            <h2 className={`${STEP_TITLE} mb-6`} data-testid="wizard-step-title">
              {t('ministry:form.step1Title')}
            </h2>

            {!loaded ? (
              <form onSubmit={lookupFid} noValidate data-testid="fid-form">
                <p className="text-theme-dim text-center mb-6">{t('ministry:apply.enterFid')}</p>
                <Field
                  id="fid-lookup"
                  name="fid"
                  testId="fid-input"
                  label={t('profile:playerID')}
                  required
                  placeholder={t('profile:playerIDPlaceholder')}
                  inputMode="numeric"
                  autoComplete="off"
                  autoFocus
                  value={fidInput}
                  invalid={invalidField === 'fid'}
                  onChange={(e) => setFidInput(e.target.value)}
                />
                <FidHelp />
                <GuideLink to={MINISTRY_PATHS.guide} testId="ministry-wizard-guide-link" />
              </form>
            ) : (
              <div className="space-y-4">
                {mode === 'edit' && assignments && (
                  <MyAssignments data={assignments} researchDay={researchDay} timezone={timezone} />
                )}
                <ProfileFields
                  fid={fid}
                  value={profile}
                  onChange={setProfile}
                  invalidField={invalidField}
                  showTimezone={false}
                  fidHint={
                    <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <span data-testid="profile-status">
                        {knownProfile ? t('profile:prefilled') : t('profile:newProfile')}
                      </span>
                      <button
                        type="button"
                        onClick={changeFid}
                        data-testid="change-fid"
                        className="min-h-[44px] underline hover:text-theme-text"
                      >
                        {t('profile:changeFid')}
                      </button>
                    </span>
                  }
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
                <div className="grid md:grid-cols-2 gap-4">
                  {SPEEDUP_FIELDS.map(({ key, label }) => numberField(key, label, false))}
                  {showCrystals && CRYSTAL_FIELDS.map(({ key, label }) => numberField(key, label, true))}
                </div>
                {/* General Speedups Note */}
                <div className="mt-4 p-4 bg-accent/10 border border-accent/30 rounded-lg">
                  <p className="text-sm text-accent">
                    <strong>💡 </strong>
                    {t('ministry:form.generalSpeedupsNote')}
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Steps 2-4: Time Preferences per day type */}
        {dayType && (
          <div data-testid={`wizard-step-${step}`} data-day={dayType}>
            <h2 className={`${STEP_TITLE} mb-4`} data-testid="wizard-step-title">
              {dayTypeLabel(dayType, researchDay)}
            </h2>
            <div className="flex flex-wrap items-center justify-center gap-4 mb-4">
              <p className="text-theme-dim">{t('ministry:form.selectMultiple')}</p>
              <TimezoneSelector value={timezone} onChange={handleTimezone} label={t('common:header.timezone')} testId="wizard-timezone" />
            </div>
            <p className="text-sm text-accent text-center mb-6 font-medium">{t('ministry:form.selectAllAvailable')}</p>
            <SlotGrid
              key={dayType /* fresh buttons per day: no colour cross-fade from the previous day */}
              dayType={dayType}
              selected={answers.time_slots_by_day[dayType]}
              onToggle={(utc) => toggleSlot(dayType, utc)}
              timezone={timezone}
              heatmap={heatmap}
            />
            <ToleranceNote />
          </div>
        )}

        {/* Step 5: Review */}
        {step === 5 && (
          <div data-testid="wizard-step-5">
            <h2 className={`${STEP_TITLE} mb-6`} data-testid="wizard-step-title">
              {t('ministry:form.step3Title')}
            </h2>
            <div className="space-y-4">
              <div className="bg-dark-bg p-4 sm:p-6 rounded-lg border border-theme-border" data-testid="review-player">
                <h3 className="font-semibold text-lg mb-4 text-accent">{t('profile:playerInfo')}</h3>
                <div className="grid md:grid-cols-2 gap-4 text-sm">
                  <ReviewItem label={t('profile:gameName')} testId="review-game-name">
                    {profile.alliance && <span className="text-accent">[{profile.alliance}] </span>}
                    <bdi>{profile.game_name}</bdi>
                  </ReviewItem>
                  <ReviewItem label={t('profile:playerID')} testId="review-fid">
                    {fid}
                  </ReviewItem>
                  {SPEEDUP_FIELDS.map(({ key, label }) => (
                    <ReviewItem key={key} label={t(label)} testId={`review-${key}`}>
                      {toNumber(answers[key])} {t('ministry:form.days')}
                    </ReviewItem>
                  ))}
                  {showCrystals &&
                    CRYSTAL_FIELDS.map(({ key, label }) => (
                      <ReviewItem key={key} label={t(label)} testId={`review-${key}`}>
                        {toNumber(answers[key])}
                      </ReviewItem>
                    ))}
                  {profile.furnace_level !== '' && (
                    <ReviewItem label={t('profile:furnaceLevel')} testId="review-furnace-level">
                      {profile.furnace_level}
                    </ReviewItem>
                  )}
                </div>
              </div>
              <div className="bg-dark-bg p-4 sm:p-6 rounded-lg border border-theme-border" data-testid="review-times">
                <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                  <h3 className="font-semibold text-lg text-accent" data-testid="review-times-heading">
                    {t('ministry:form.step2Title')} <bdi dir="ltr">({getTimezoneAbbr(timezone)})</bdi>
                  </h3>
                  <TimezoneSelector value={timezone} onChange={handleTimezone} label={t('common:header.timezone')} />
                </div>
                {DAY_TYPES.map((d) => {
                  const slots = [...answers.time_slots_by_day[d]].sort();
                  return (
                    <div key={d} className="mb-3 last:mb-0" data-testid={`review-slots-${d}`}>
                      <p className="text-sm font-medium text-theme-dim mb-1">{dayTypeLabel(d, researchDay)}</p>
                      <div className="flex flex-wrap gap-2">
                        {slots.map((time) => (
                          <span key={time} className="px-3 py-1 bg-accent/20 text-accent rounded-full text-sm font-medium" data-slot={time}>
                            <TimeWithUtc utc={time} timezone={timezone} />
                          </span>
                        ))}
                        {slots.length === 0 && <span className="text-theme-dim text-sm">{t('ministry:form.noTimeSelected')}</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div
            className="mt-6 p-4 bg-danger/10 border border-danger/30 rounded-lg flex items-center gap-3"
            role="alert"
            data-testid="form-error"
          >
            <AlertCircle className="w-5 h-5 text-danger shrink-0" aria-hidden="true" />
            <p className="text-danger">{error}</p>
          </div>
        )}

        {/* Back / Next (sticky on phones) */}
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
