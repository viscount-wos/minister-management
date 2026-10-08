// SVS admin Players tab -> "Add to rally" (one player or the bulk selection). Lists the plan's EXISTING rally leaders
// grouped by group with their free places (named joiners n/4, extra joiners n/14); then "as named joiner" / "as extra
// joiner" (default: named when there is room). Also "Make rally leader in …" and "Add to <extra group>". A player who is
// already in the plan sees where, and the buttons say "Move here" (the planner's explicit move).
// The change is ONE server call (POST …/plan/place) applied atomically to the stored plan with the revision this menu
// loaded; on 409 PLAN_CONFLICT the plan is re-read and the call retried ONCE if the choice still applies.
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { AlertCircle, ArrowLeft, Crown, Loader2, Swords, Users, X } from 'lucide-react';
import { isApiError, type Round } from '../../../shared/api';
import { errorText } from '../../../shared/apiErrors';
import type { SvsSettings } from '../api';
import { planApi, type PlaceBody, type PlaceResponse, type PlaceWhere } from '../plan/api';
import { capacity, groupLabel, leaderLabel, makePlayerName, placementShort } from '../plan/labels';
import { EXTRA_JOINERS, NAMED_JOINERS, leadersOf, normalizeDoc, placements } from '../plan/model';
import type { Leader, PlanDoc, PlanResponse, Placement } from '../plan/model';

export interface RallyPlayer {
  fid: string;
  name: string;
}

interface Props {
  round: Round<SvsSettings>;
  anchor: HTMLElement;
  /** One player = the row menu; several = the bulk bar. */
  players: RallyPlayer[];
  onClose: () => void;
  /** Called after a successful change (or a no-op) with the message for the toast. */
  onDone: (message: string, warn: boolean) => void;
  onOpenPlan?: () => void;
}

type Action = { body: Omit<PlaceBody, 'expected_revision'>; applies: (d: PlanDoc) => boolean };

const PANEL_W = 352; // 22rem
const BTN =
  'w-full flex items-center gap-2 min-h-[44px] px-3 py-2 rounded-lg text-start text-sm text-theme-text hover:bg-dark-card-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-40 disabled:cursor-not-allowed';

export default function AddToRally({ round, anchor, players, onClose, onDone, onOpenPlan }: Props) {
  const { t } = useTranslation();
  const bulk = players.length > 1;
  const single = players[0];
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [doc, setDoc] = useState<PlanDoc | null>(null);
  const [leaderId, setLeaderId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const panel = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number; maxH: number }>({ top: -9999, left: -9999, maxH: 480 });

  const load = useCallback(async () => {
    const res = await planApi.get(round.id);
    setPlan(res);
    const d = normalizeDoc(res.plan);
    setDoc(d);
    return { res, d };
  }, [round.id]);

  useEffect(() => {
    load().catch((e) => setError(errorText(t, e, 'admin:fetchError')));
  }, [load, t]);

  // ------------------------------------------------------------ position (fixed, next to the trigger; flips up)
  useLayoutEffect(() => {
    const place = () => {
      const r = anchor.getBoundingClientRect();
      const vw = document.documentElement.clientWidth;
      const vh = window.innerHeight;
      const rtl = document.documentElement.dir === 'rtl';
      const w = Math.min(PANEL_W, vw - 16);
      let left = rtl ? r.left : r.right - w;
      left = Math.max(8, Math.min(left, vw - w - 8));
      const below = vh - r.bottom - 12;
      const above = r.top - 12;
      const h = (panel.current?.scrollHeight ?? 400) + 2; // + borders
      if (h <= below) setPos({ top: r.bottom + 4, left, maxH: below });
      else if (h <= above) setPos({ top: r.top - 4 - h, left, maxH: above });
      else {
        // taller than either side: as much as fits, shifted up from the bottom of the window
        const maxH = vh - 16;
        setPos({ top: Math.max(8, vh - 8 - Math.min(h, maxH)), left, maxH });
      }
    };
    place();
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    return () => {
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', place, true);
    };
  }, [anchor, doc, leaderId, error]);

  // ------------------------------------------------------------ focus, Escape, outside click
  const close = useCallback(() => {
    onClose();
    anchor.focus();
  }, [anchor, onClose]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        close();
      }
    };
    const onDown = (e: PointerEvent) => {
      if (panel.current && !panel.current.contains(e.target as Node) && !anchor.contains(e.target as Node)) onClose();
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('pointerdown', onDown);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('pointerdown', onDown);
    };
  }, [anchor, close, onClose]);
  useEffect(() => {
    // the default (or first) choice of each step gets the focus
    const p = panel.current;
    if (!p) return;
    const el = p.querySelector<HTMLElement>('[data-autofocus="true"]:not(:disabled)') ??
      p.querySelector<HTMLElement>('[data-choice]:not(:disabled)') ??
      p.querySelector<HTMLElement>('button:not(:disabled)');
    el?.focus();
  }, [doc, leaderId]);

  // ------------------------------------------------------------ derived
  const playerName = useMemo(() => makePlayerName(plan?.people ?? {}, (fid) => players.find((p) => p.fid === fid)?.name), [plan, players]);
  const placed = useMemo(() => (doc ? placements(doc) : new Map<string, Placement>()), [doc]);
  const where = !bulk && single ? placed.get(`fid:${single.fid}`) : undefined;
  const whereText = where && doc ? placementShort(t, doc, where, playerName) : '';
  const battleGroups = doc ? doc.groups.filter((g) => g.kind !== 'extra') : [];
  const extraGroups = doc ? doc.groups.filter((g) => g.kind === 'extra') : [];
  const hasLeaders = !!doc && doc.leaders.length > 0;
  const chosen = doc && leaderId ? doc.leaders.find((l) => l.id === leaderId) ?? null : null;
  const lname = (l: Leader) => (doc ? leaderLabel(t, doc, l, playerName) : '');
  const placeKey = (d: PlanDoc) => (single ? JSON.stringify(placements(d).get(`fid:${single.fid}`) ?? null) : '');
  const startKey = useMemo(() => (doc ? placeKey(doc) : ''), [doc]); // eslint-disable-line react-hooks/exhaustive-deps

  // ------------------------------------------------------------ run one change (retry once on PLAN_CONFLICT)
  const describeError = (e: unknown): string => {
    if (isApiError(e, 'DOUBLE_BOOKED')) {
      const d = (e.details ?? {}) as PlaceWhere & { player_name?: string };
      const g = doc?.groups.find((x) => x.id === d.group_id);
      const gl = g ? groupLabel(t, g) : d.group_name ?? '';
      const w =
        d.position === 'extra_group'
          ? t('svs:plan.placed.inGroup', { group: gl })
          : d.position === 'leader'
            ? t('svs:plan.placed.leads', { group: gl })
            : t('svs:plan.placed.with', { leader: d.leader_label ?? '?' });
      return t('svs:plan.alreadyUseMove', { name: d.player_name ?? single?.name ?? '', where: w });
    }
    if (isApiError(e, 'RALLY_FULL') || isApiError(e, 'GROUP_FULL') || isApiError(e, 'SLOT_TAKEN')) return t('svs:players.err.full');
    if (isApiError(e, 'LEADER_NOT_FOUND') || isApiError(e, 'GROUP_NOT_FOUND')) return t('svs:players.err.gone');
    if (isApiError(e, 'PLAN_CONFLICT')) return t('svs:players.err.conflict');
    if (isApiError(e) && e.status === 422) return e.message; // any other plan rule: the server's message
    return errorText(t, e);
  };

  const run = async (a: Action) => {
    if (!plan || busy) return;
    setBusy(true);
    setError('');
    let res: PlaceResponse;
    try {
      try {
        res = await planApi.place(round.id, { ...a.body, expected_revision: plan.revision });
      } catch (e) {
        if (!isApiError(e, 'PLAN_CONFLICT')) throw e;
        // someone saved meanwhile: re-read; retry once only if the choice still means the same thing
        const fresh = await load();
        if (!a.applies(fresh.d) || placeKey(fresh.d) !== startKey) {
          setError(t('svs:players.err.conflict'));
          return;
        }
        res = await planApi.place(round.id, { ...a.body, expected_revision: fresh.res.revision });
      }
    } catch (e) {
      setError(describeError(e));
      if (isApiError(e, 'PLAN_CONFLICT') || isApiError(e, 'LEADER_NOT_FOUND') || isApiError(e, 'RALLY_FULL')) load().catch(() => undefined);
      return;
    } finally {
      setBusy(false);
    }
    onDone(...summarise(res));
  };

  const summarise = (res: PlaceResponse): [string, boolean] => {
    const d = normalizeDoc(res.plan);
    const name = makePlayerName(res.people, (fid) => players.find((p) => p.fid === fid)?.name);
    const nm = (fid?: string) => players.find((p) => p.fid === fid)?.name ?? name({ fid });
    const r = res.result;
    if (!bulk) {
      const p = placements(d).get(`fid:${single.fid}`);
      const w = p ? placementShort(t, d, p, name) : '';
      if (r.unchanged.length) return [t('svs:players.done.unchanged', { name: single.name, where: w }), false];
      return [t(r.moved.length ? 'svs:players.done.moved' : 'svs:players.done.one', { name: single.name, where: w }), false];
    }
    const parts: string[] = [];
    const target = r.placed[0];
    const l = target?.leader_id ? d.leaders.find((x) => x.id === target.leader_id) : null;
    const g = target ? d.groups.find((x) => x.id === target.group_id) : null;
    const to = l ? leaderLabel(t, d, l, name) : g ? groupLabel(t, g) : '';
    const named = r.placed.filter((p) => p.as === 'named').length;
    const extra = r.placed.length - named;
    parts.push(
      r.placed.length
        ? l
          ? t('svs:players.done.bulk', { n: r.placed.length, to, named, extra })
          : t('svs:players.done.bulkGroup', { n: r.placed.length, to })
        : t('svs:players.done.none'),
    );
    const already = [...r.unchanged.map((x) => x.player.fid), ...r.skipped.map((x) => x.player.fid)];
    if (already.length) parts.push(t('svs:players.done.skipped', { list: already.map(nm).join(', ') }));
    if (r.overflow.length) parts.push(t('svs:players.done.overflow', { list: r.overflow.map((x) => nm(x.player.fid)).join(', ') }));
    return [parts.join(' '), already.length > 0 || r.overflow.length > 0];
  };

  // ------------------------------------------------------------ actions
  const groupExists = (id: string) => (d: PlanDoc) => d.groups.some((x) => x.id === id);
  const fidsBody = bulk ? { fids: players.map((p) => p.fid) } : { fid: single.fid };
  const move = !!where;
  const asJoiner = (l: Leader, mode: 'named' | 'extra' | 'auto') =>
    run({
      body: { ...fidsBody, as: mode, leader_id: l.id, ...(bulk ? {} : { move }) },
      applies: (d) => {
        const x = d.leaders.find((y) => y.id === l.id);
        if (!x) return false;
        const c = capacity(x);
        return mode === 'named' ? c.namedFree > 0 : mode === 'extra' ? c.extraFree > 0 : true;
      },
    });

  const here = (l: Leader, kind: Placement['kind']) => !!where && where.kind === kind && 'leaderId' in where && where.leaderId === l.id;

  // ------------------------------------------------------------ render
  const title = bulk ? t('svs:players.add.bulkTitle', { n: players.length }) : t('svs:players.add.title');
  // A portal: an ancestor with a transform would otherwise become the containing block of `position: fixed`.
  return createPortal(
    <div
      ref={panel}
      role="dialog"
      aria-modal="false"
      aria-labelledby="add-to-rally-title"
      data-testid="add-to-rally"
      style={{ top: pos.top, left: pos.left, maxHeight: pos.maxH, width: Math.min(PANEL_W, document.documentElement.clientWidth - 16) }}
      className="fixed z-50 overflow-auto bg-dark-card border border-theme-border rounded-xl shadow-2xl p-3 space-y-2"
    >
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <h3 id="add-to-rally-title" className="font-semibold text-accent">
            {title}
          </h3>
          {!bulk && (
            <p className="text-sm text-theme-text truncate">
              <bdi>{single.name}</bdi>
            </p>
          )}
        </div>
        <button type="button" onClick={close} aria-label={t('svs:players.add.close')} className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] -m-2 rounded-lg text-theme-dim hover:text-theme-text">
          <X className="w-4 h-4" aria-hidden="true" />
        </button>
      </div>

      {where && (
        <p className="text-xs px-2 py-1.5 rounded bg-warning/15 text-warning font-semibold" data-testid="add-now">
          {t('svs:players.add.now', { where: whereText })}
        </p>
      )}
      {error && (
        <p className="text-sm px-2 py-1.5 rounded bg-danger/10 text-danger flex gap-2" role="alert" data-testid="add-error">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
          <span>{error}</span>
        </p>
      )}

      {!doc && !error && (
        <p className="flex items-center gap-2 text-sm text-theme-dim py-3" role="status">
          <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
          {t('svs:players.add.loading')}
        </p>
      )}

      {doc && !chosen && (
        <>
          {!hasLeaders ? (
            <div className="text-sm text-theme-dim space-y-2 py-1" data-testid="add-no-leaders">
              <p>{t('svs:players.add.noLeaders')}</p>
              {onOpenPlan && (
                <button type="button" onClick={onOpenPlan} data-testid="add-open-plan" data-choice className="inline-flex items-center gap-2 min-h-[44px] px-3 rounded-lg bg-accent/20 text-accent font-medium hover:bg-accent/30">
                  <Swords className="w-4 h-4" aria-hidden="true" />
                  {t('svs:players.add.openPlan')}
                </button>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-xs text-theme-dim">{t('svs:players.add.chooseLeader')}</p>
              {battleGroups.map((g) => {
                const ls = leadersOf(doc, g.id);
                if (!ls.length) return null;
                return (
                  <div key={g.id} role="group" aria-label={groupLabel(t, g)} data-testid={`add-group-${g.id}`}>
                    <div className={`text-xs font-semibold uppercase tracking-wide px-1 pt-1 ${g.kind === 'counter' ? 'text-team-counter' : 'text-team-main'}`}>{groupLabel(t, g)}</div>
                    {ls.map((l) => {
                      const c = capacity(l);
                      const full = c.namedFree <= 0 && c.extraFree <= 0;
                      return (
                        <button
                          key={l.id}
                          type="button"
                          disabled={full || busy}
                          onClick={() => setLeaderId(l.id)}
                          data-testid={`rally-leader-${l.id}`} data-choice
                          className={BTN}
                        >
                          <Users className="w-4 h-4 shrink-0 text-theme-dim" aria-hidden="true" />
                          <span className="flex-1 min-w-0">
                            <span className="block truncate font-medium">
                              <bdi>{lname(l)}</bdi>
                              {where && 'leaderId' in where && where.leaderId === l.id && <span className="text-warning"> · {t('svs:players.add.hereNow')}</span>}
                            </span>
                            <span className="block text-xs text-theme-dim" data-testid="leader-capacity">
                              {full ? t('svs:players.add.full') : t('svs:players.add.capacity', { named: c.named, extra: c.extra, maxNamed: NAMED_JOINERS, maxExtra: EXTRA_JOINERS })}
                            </span>
                          </span>
                        </button>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          )}

          {(!bulk || extraGroups.length > 0) && (
            <div className="border-t border-theme-border pt-2 space-y-1">
              <p className="text-xs text-theme-dim">{t('svs:players.add.other')}</p>
              {!bulk &&
                battleGroups.map((g) => (
                  <button
                    key={g.id}
                    type="button"
                    disabled={busy}
                    data-testid={`make-leader-${g.id}`} data-choice
                    onClick={() => run({ body: { fid: single.fid, as: 'leader', group_id: g.id, move }, applies: groupExists(g.id) })}
                    className={BTN}
                  >
                    <Crown className="w-4 h-4 shrink-0 text-theme-dim" aria-hidden="true" />
                    {t(move ? 'svs:players.add.moveMakeLeader' : 'svs:players.add.makeLeader', { group: groupLabel(t, g) })}
                  </button>
                ))}
              {extraGroups.map((g) => {
                const isHere = !!where && where.kind === 'extraGroup' && where.groupId === g.id;
                return (
                  <button
                    key={g.id}
                    type="button"
                    disabled={busy || isHere}
                    data-testid={`to-group-${g.id}`} data-choice
                    onClick={() => run({ body: { ...fidsBody, as: 'group', group_id: g.id, ...(bulk ? {} : { move }) }, applies: groupExists(g.id) })}
                    className={BTN}
                  >
                    <Users className="w-4 h-4 shrink-0 text-theme-dim" aria-hidden="true" />
                    {t(move ? 'svs:players.add.moveToGroup' : 'svs:players.add.toGroup', { group: groupLabel(t, g) })}
                  </button>
                );
              })}
            </div>
          )}
        </>
      )}

      {doc && chosen && (
        <div className="space-y-2" data-testid="add-step-mode">
          <button type="button" onClick={() => setLeaderId(null)} className="inline-flex items-center gap-1 min-h-[44px] px-2 -ms-2 text-sm text-theme-dim hover:text-theme-text">
            <ArrowLeft className="w-4 h-4 rtl:rotate-180" aria-hidden="true" />
            {t('svs:players.add.back')}
          </button>
          <p className="text-sm font-semibold text-theme-text">
            <bdi>{lname(chosen)}</bdi>{' '}
            <span className="text-theme-dim font-normal">({groupLabel(t, doc.groups.find((g) => g.id === chosen.group_id)!)})</span>
          </p>
          {(() => {
            const c = capacity(chosen);
            if (bulk) {
              const free = c.namedFree + c.extraFree;
              return (
                <>
                  <button type="button" data-autofocus="true" disabled={busy || free <= 0} onClick={() => asJoiner(chosen, 'auto')} data-testid="bulk-auto" className={`${BTN} bg-accent/20 text-accent font-semibold hover:bg-accent/30`}>
                    {t('svs:players.add.bulkAuto', { free })}
                  </button>
                  <button type="button" disabled={busy || c.extraFree <= 0} onClick={() => asJoiner(chosen, 'extra')} data-testid="bulk-extra" className={BTN}>
                    {t('svs:players.add.bulkExtra', { n: c.extra, max: EXTRA_JOINERS })}
                  </button>
                </>
              );
            }
            const namedDefault = c.namedFree > 0;
            const namedHere = here(chosen, 'joiner');
            const extraHere = here(chosen, 'extra');
            return (
              <>
                <button
                  type="button"
                  data-autofocus={namedDefault ? 'true' : undefined}
                  disabled={busy || namedHere || c.namedFree <= 0}
                  onClick={() => asJoiner(chosen, 'named')}
                  data-testid="add-as-named"
                  data-default={namedDefault ? 'true' : undefined}
                  className={`${BTN} ${namedDefault ? 'bg-accent/20 text-accent font-semibold hover:bg-accent/30' : ''}`}
                >
                  {t(move && !namedHere ? 'svs:players.add.moveNamed' : 'svs:players.add.asNamed', { n: c.named, max: NAMED_JOINERS })}
                  {namedHere && <span className="text-warning"> · {t('svs:players.add.hereNow')}</span>}
                </button>
                <button
                  type="button"
                  data-autofocus={!namedDefault ? 'true' : undefined}
                  disabled={busy || extraHere || c.extraFree <= 0}
                  onClick={() => asJoiner(chosen, 'extra')}
                  data-testid="add-as-extra"
                  data-default={!namedDefault ? 'true' : undefined}
                  className={`${BTN} ${!namedDefault ? 'bg-accent/20 text-accent font-semibold hover:bg-accent/30' : ''}`}
                >
                  {t(move && !extraHere ? 'svs:players.add.moveExtra' : 'svs:players.add.asExtra', { n: c.extra, max: EXTRA_JOINERS })}
                  {extraHere && <span className="text-warning"> · {t('svs:players.add.hereNow')}</span>}
                </button>
                <p className="text-xs text-theme-dim">{t('svs:players.add.namedHint')}</p>
              </>
            );
          })()}
          {busy && (
            <p className="flex items-center gap-2 text-xs text-theme-dim" role="status">
              <Loader2 className="w-3 h-3 animate-spin" aria-hidden="true" />
              {t('svs:players.add.saving')}
            </p>
          )}
        </div>
      )}
    </div>,
    document.body,
  );
}
