import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, Save, AlertCircle, CheckCircle, XCircle, CalendarOff, Clock, UserRound } from 'lucide-react';
import api, { Application, Heatmap, MinistrySettings, PlayerAssignments, Round, isApiError } from '../../shared/api';
import { errorText } from '../../shared/apiErrors';
import FidLookup from '../../shared/FidLookup';
import ProfileFields, { EMPTY_PROFILE, ProfileFormValues, profileToInput } from '../../shared/ProfileFields';
import UseLastAnswers from '../../shared/UseLastAnswers';
import { Field } from '../../shared/fields';
import { useTimezone } from '../../shared/TimezoneContext';
import { AnswersForm, CRYSTAL_FIELDS, SPEEDUP_FIELDS, answersToForm, blankAnswers, formToAnswers, totalSlots } from './answers';
import TimeSlotPicker from './TimeSlotPicker';
import MyAssignments from './MyAssignments';
import { MINISTRY_PATHS } from './paths';

// One page for the whole player flow (SPEC "Concepts"):
//   enter FID -> "New application for <round>" (answers blank, "Use my last
//   answers" when an earlier application exists) or "Edit your application for
//   <round>" (answers from this round). Profile fields always pre-fill.
// Closing time: after it passes NEW applications are blocked (403
// APPLICATIONS_CLOSED); existing ones stay editable until the round closes.

type Phase = 'loading' | 'noRound' | 'loadError' | 'fid' | 'closed' | 'form' | 'saved';

function StatusCard({ icon, tone, title, body, testId, children }: {
  icon: React.ReactNode;
  tone: 'danger' | 'success' | 'dim';
  title: string;
  body?: string;
  testId: string;
  children?: React.ReactNode;
}) {
  const titleClass = tone === 'danger' ? 'text-danger' : tone === 'success' ? 'text-accent' : 'text-theme-text';
  return (
    <div className="min-h-[70vh] flex items-center justify-center p-4">
      <div className="bg-dark-card rounded-2xl p-10 border border-theme-border max-w-md w-full text-center" data-testid={testId}>
        <div className="flex justify-center mb-6">{icon}</div>
        <h2 className={`text-3xl font-bold mb-4 ${titleClass}`}>{title}</h2>
        {body && <p className="text-theme-dim mb-6">{body}</p>}
        {children}
      </div>
    </div>
  );
}

export default function ApplicationPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const { timezone, setTimezone } = useTimezone();

  const [phase, setPhase] = useState<Phase>('loading');
  const [round, setRound] = useState<Round<MinistrySettings> | null>(null);
  const [heatmap, setHeatmap] = useState<Heatmap>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [invalidField, setInvalidField] = useState<string | null>(null);

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
        setFid(theFid);
        setPrevious(prev);
        setLastApplied(false);
        setKnownProfile(!!prof);
        const tz = prof?.timezone || timezone;
        if (prof?.timezone) setTimezone(prof.timezone);
        setProfile({
          game_name: prof?.game_name ?? '',
          alliance: (prof?.alliance ?? '').toUpperCase().slice(0, 3),
          timezone: tz,
          furnace_level: prof?.furnace_level != null ? String(prof.furnace_level) : '',
        });
        if (app) {
          setMode('edit');
          setAnswers(answersToForm(app.answers));
          api.ministry.playerAssignments(theFid).then(setAssignments).catch(() => setAssignments(null));
          setPhase('form');
        } else {
          setMode('new');
          setAnswers(blankAnswers());
          setAssignments(null);
          setPhase(r.is_closed_for_new ? 'closed' : 'form');
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
      const initial = params.get('fid');
      if (initial && /^\d{1,20}$/.test(initial)) loadPlayer(initial, r);
      else setPhase('fid');
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startWithFid = (theFid: string) => {
    if (!round) return;
    setParams({ fid: theFid }, { replace: true });
    loadPlayer(theFid, round);
  };

  const changeFid = () => {
    setParams({}, { replace: true });
    setError('');
    setPhase('fid');
  };

  const applyLastAnswers = () => {
    if (!previous) return;
    setAnswers(answersToForm(previous.answers));
    setLastApplied(true);
  };

  const handleProfileChange = (next: ProfileFormValues) => {
    if (next.timezone !== profile.timezone) setTimezone(next.timezone);
    setProfile(next);
  };

  const handleTimezone = (tz: string) => {
    setTimezone(tz);
    setProfile((p) => ({ ...p, timezone: tz }));
  };

  const save = async () => {
    if (!round) return;
    setError('');
    setInvalidField(null);
    if (!profile.game_name.trim()) {
      setInvalidField('profile.game_name');
      return setError(t('ministry:form.required'));
    }
    if (!profile.alliance.trim()) {
      setInvalidField('profile.alliance');
      return setError(t('profile:allianceRequired'));
    }
    if (totalSlots(answers.time_slots_by_day) === 0 && !window.confirm(t('ministry:form.noTimeSlotsConfirm'))) return;

    setBusy(true);
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
      } else if (isApiError(e, 'NO_CURRENT_ROUND')) {
        setPhase('noRound');
      } else {
        if (isApiError(e, 'VALIDATION_ERROR')) setInvalidField(e.field);
        setError(errorText(t, e, 'ministry:form.submitError'));
      }
    } finally {
      setBusy(false);
    }
  };

  const backButton = (
    <button
      type="button"
      onClick={() => navigate(MINISTRY_PATHS.home)}
      className="flex items-center gap-2 mx-auto text-accent hover:text-accent-dim transition-colors"
    >
      <ArrowLeft className="w-5 h-5 rtl:rotate-180" aria-hidden="true" />
      {t('ministry:update.backHome')}
    </button>
  );

  if (phase === 'loading') {
    return (
      <div className="min-h-[70vh] flex items-center justify-center p-4">
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
        {backButton}
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
        {backButton}
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
          <button type="button" onClick={changeFid} className="text-theme-dim hover:text-theme-text text-sm underline">
            {t('ministry:apply.otherFid')}
          </button>
          {backButton}
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
            className="px-6 py-3 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium transition-colors"
          >
            {t('ministry:apply.viewMine')}
          </button>
          {backButton}
        </div>
      </StatusCard>
    );
  }

  const closingNote = round?.closing_time ? (
    <p
      className={`flex items-center justify-center gap-2 text-sm font-medium ${round.is_closed_for_new ? 'text-warning' : 'text-success'}`}
      data-testid="closing-note"
    >
      <Clock className="w-4 h-4 shrink-0" aria-hidden="true" />
      {round.is_closed_for_new
        ? t('ministry:apply.closedButEditable')
        : t('ministry:home.applicationsCloseAt', { time: new Date(round.closing_time).toLocaleString() })}
    </p>
  ) : null;

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="bg-dark-card rounded-2xl p-8 border border-theme-border max-w-4xl w-full">
        <button
          type="button"
          onClick={() => navigate(MINISTRY_PATHS.home)}
          className="flex items-center gap-2 text-theme-dim hover:text-theme-text mb-6"
        >
          <ArrowLeft className="w-5 h-5 rtl:rotate-180" aria-hidden="true" />
          {t('ministry:update.backHome')}
        </button>

        {phase === 'fid' && (
          <div>
            <h2 className="text-3xl font-bold text-accent mb-2 text-center" data-testid="application-heading" data-mode="lookup">
              {t('ministry:apply.title')}
            </h2>
            <p className="text-center text-theme-text font-medium mb-2" data-testid="round-name">{round?.name}</p>
            <div className="mb-6">{closingNote}</div>
            <FidLookup
              onSubmit={startWithFid}
              loading={busy}
              initialFid={params.get('fid') ?? ''}
              intro={t('ministry:apply.enterFid')}
            />
          </div>
        )}

        {phase === 'form' && round && settings && (
          <div className="space-y-8">
            <div className="text-center space-y-2">
              <h2 className="text-3xl font-bold text-accent" data-testid="application-heading" data-mode={mode}>
                {mode === 'new'
                  ? t('ministry:apply.newFor', { round: round.name })
                  : t('ministry:apply.editFor', { round: round.name })}
              </h2>
              {closingNote}
              <div className="flex flex-wrap items-center justify-center gap-3 text-sm text-theme-dim">
                <UserRound className="w-4 h-4" aria-hidden="true" />
                <span data-testid="profile-status">
                  {knownProfile ? t('profile:prefilled') : t('profile:newProfile')}
                </span>
                <button type="button" onClick={changeFid} data-testid="change-fid" className="underline hover:text-theme-text">
                  {t('profile:changeFid')}
                </button>
              </div>
            </div>

            {mode === 'edit' && assignments && (
              <MyAssignments data={assignments} researchDay={researchDay} timezone={timezone} />
            )}

            <section aria-labelledby="sec-profile">
              <h3 id="sec-profile" className="text-xl font-semibold mb-4 text-accent">{t('profile:playerInfo')}</h3>
              <ProfileFields fid={fid} value={profile} onChange={handleProfileChange} invalidField={invalidField} />
            </section>

            <section aria-labelledby="sec-answers" className="space-y-4">
              <h3 id="sec-answers" className="text-xl font-semibold text-accent">{t('ministry:apply.answersTitle')}</h3>
              <p className="text-sm text-theme-dim">
                {mode === 'new' ? t('ministry:apply.answersBlankNote') : t('ministry:apply.answersEditNote')}
              </p>
              <UseLastAnswers
                available={!!previous}
                previousRoundName={previous?.round_name}
                applied={lastApplied}
                onUse={applyLastAnswers}
                disabled={busy}
              />
              <div className="grid md:grid-cols-2 gap-4">
                {SPEEDUP_FIELDS.map(({ key, label }) => (
                  <Field
                    key={key}
                    id={`answer-${key}`}
                    name={key}
                    testId={`answer-${key}`}
                    type="number"
                    min={0}
                    step={0.1}
                    placeholder="0"
                    label={t(label)}
                    value={answers[key]}
                    invalid={invalidField === `answers.${key}`}
                    onChange={(e) => setAnswers((a) => ({ ...a, [key]: e.target.value }))}
                  />
                ))}
                {settings.show_fire_crystals &&
                  CRYSTAL_FIELDS.map(({ key, label }) => (
                    <Field
                      key={key}
                      id={`answer-${key}`}
                      name={key}
                      testId={`answer-${key}`}
                      type="number"
                      min={0}
                      step={1}
                      placeholder="0"
                      label={t(label)}
                      value={answers[key]}
                      invalid={invalidField === `answers.${key}`}
                      onChange={(e) => setAnswers((a) => ({ ...a, [key]: e.target.value }))}
                    />
                  ))}
              </div>
              <div className="p-4 bg-accent/10 border border-accent/30 rounded-lg">
                <p className="text-sm text-accent">
                  <strong>💡 </strong>
                  {t('ministry:form.generalSpeedupsNote')}
                </p>
              </div>
            </section>

            <section aria-labelledby="sec-times">
              <h3 id="sec-times" className="text-xl font-semibold mb-4 text-accent">{t('ministry:form.selectTimes')}</h3>
              <TimeSlotPicker
                value={answers.time_slots_by_day}
                onChange={(next) => setAnswers((a) => ({ ...a, time_slots_by_day: next }))}
                researchDay={researchDay}
                timezone={timezone}
                onTimezoneChange={handleTimezone}
                heatmap={heatmap}
              />
            </section>

            <button
              type="button"
              onClick={save}
              disabled={busy}
              data-testid="save-application"
              className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-accent text-dark-bg rounded-lg hover:bg-accent-dim font-medium transition-colors disabled:opacity-50"
            >
              <Save className="w-5 h-5" aria-hidden="true" />
              {busy ? t('ministry:form.loading') : mode === 'new' ? t('ministry:form.submit') : t('ministry:form.update')}
            </button>
          </div>
        )}

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
      </div>
    </div>
  );
}
