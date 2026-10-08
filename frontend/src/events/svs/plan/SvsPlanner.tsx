// Event Management -> SVS -> Battle plan (desktop-first). Loads the round's plan, its sign-ups and the hero library;
// every change autosaves (debounced) with the plan's revision; a newer revision saved by someone else shows a conflict
// banner (never a silent overwrite). Drag and drop: heroes into slots, leaders between/within groups, sign-ups into
// joiner rows / extra joiners / "new leader". Click-to-place and keyboard work everywhere too.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  closestCenter,
  pointerWithin,
  useSensor,
  useSensors,
  type CollisionDetection,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core';
import { arrayMove, sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import { AlertCircle, AlertTriangle, CheckCircle2, CloudOff, Loader2, Plus, RefreshCw, Info } from 'lucide-react';
import api, { isApiError, type Round } from '../../../shared/api';
import { errorText } from '../../../shared/apiErrors';
import HeroCard from '../../../shared/heroes/HeroCard';
import { fetchHeroes, type Hero } from '../../../shared/heroes/api';
import { battleHours, svsApi, svsTroops, type SvsSettings } from '../api';
import { planApi } from './api';
import { PlannerContext, type PlannerCtx, type SignupInfo } from './PlannerContext';
import { ExtraGroupCard, GroupColumn } from './GroupColumn';
import Sidebar from './Sidebar';
import SharePanel from './SharePanel';
import {
  MAX_EXTRA_GROUPS,
  applyPlayer,
  blankGroup,
  getSlotHero,
  leadersOf,
  nextEmptySlot,
  normalizeDoc,
  placements,
  playerKey,
  removePlacement,
  renumber,
  sameSlot,
  setSlotHero,
} from './model';
import type { HeroSlot, Leader, PetBuff, Person, Placement, PlanDoc, PlanGroup, PlayerRef, PlayerTarget, ShareInfo, Strategy } from './model';

type SaveStatus = 'saved' | 'dirty' | 'saving' | 'error';
const SAVE_DELAY = 700;

/** The most specific (smallest) droppable under the pointer that accepts what is dragged; keyboard: closest. */
const collision: CollisionDetection = (args) => {
  const type = args.active.data.current?.type as string | undefined;
  const containers = args.droppableContainers.filter((c) => ((c.data.current?.accepts as string[] | undefined) ?? []).includes(type ?? ''));
  const scoped = { ...args, droppableContainers: containers };
  if (!args.pointerCoordinates) return closestCenter(scoped);
  const hits = pointerWithin(scoped);
  const area = (id: string | number) => {
    const r = args.droppableRects.get(id);
    return r ? r.width * r.height : Infinity;
  };
  return [...hits].sort((a, b) => area(a.id) - area(b.id));
};

function relTime(t: (k: string, o?: Record<string, unknown>) => string, at: number | null, now: number): string {
  if (!at) return '';
  const s = Math.max(0, Math.round((now - at) / 1000));
  if (s < 45) return t('svs:plan.save.justNow');
  return t('svs:plan.save.minutesAgo', { n: Math.max(1, Math.round(s / 60)) });
}

export default function SvsPlanner({ round, readOnly: shellReadOnly }: { round: Round<SvsSettings>; readOnly: boolean }) {
  const { t } = useTranslation();
  const [loadError, setLoadError] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [doc, setDoc] = useState<PlanDoc | null>(null);
  const docRef = useRef<PlanDoc | null>(null);
  const revRef = useRef(0);
  const [share, setShare] = useState<ShareInfo>({ enabled: false, token: null, path: null, created_at: null });
  const [people, setPeople] = useState<Record<string, Person>>({});
  const [petTimes, setPetTimes] = useState<Record<PetBuff, string>>({ open: '11:00', two_hours: '13:00', last_hour: '15:00' });
  const [stateGen, setStateGen] = useState(99);
  const [heroes, setHeroes] = useState<Map<string, Hero>>(new Map());
  const [signups, setSignups] = useState<Map<string, SignupInfo>>(new Map());
  const [status, setStatus] = useState<SaveStatus>('saved');
  const [saveError, setSaveError] = useState('');
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [conflict, setConflict] = useState<number | null>(null);
  const conflictRef = useRef(false);
  const [closed, setClosed] = useState(false);
  const [now, setNow] = useState(Date.now());
  const [armedSlot, setArmedSlotState] = useState<HeroSlot | null>(null);
  const [armedHero, setArmedHeroState] = useState<string | null>(null);
  const [sidebarTab, setSidebarTab] = useState<'heroes' | 'players'>('heroes');
  const [toast, setToast] = useState('');
  const [active, setActive] = useState<Record<string, unknown> | null>(null);
  const [addingGroup, setAddingGroup] = useState(false);
  const [newGroupName, setNewGroupName] = useState('');
  const timer = useRef<number | null>(null);
  const saving = useRef(false);
  const dirty = useRef(false);
  const readOnly = shellReadOnly || closed || conflict != null;
  const hours = useMemo(() => battleHours(round.settings), [round.settings]);

  const loadSignups = useCallback(async () => {
    const res = await svsApi.admin.applications(round.id, { sort: 'name', dir: 'asc' });
    const m = new Map<string, SignupInfo>();
    for (const a of res.applications) {
      m.set(a.fid, {
        fid: a.fid,
        name: a.profile.game_name,
        alliance: a.profile.alliance,
        hours: a.answers.hours ?? [],
        vc: a.answers.discord_vc ?? null,
        troops: svsTroops(a.profile.troops),
        strength: a.joiner_strength ?? null,
      });
    }
    setSignups(m);
  }, [round.id]);

  const load = useCallback(async () => {
    setLoadError('');
    try {
      const [plan, lib] = await Promise.all([planApi.get(round.id), fetchHeroes(), loadSignups()]);
      // Every hero (also above the state's generation), so a plan saved before the generation was lowered still
      // shows its pictures; the palette offers only heroes up to the state's generation.
      const all = lib.state_generation < lib.max_generation ? await fetchHeroes({ max_gen: lib.max_generation }) : lib;
      setHeroes(new Map(all.heroes.map((h) => [h.slug, h])));
      setStateGen(plan.state_generation);
      const d = normalizeDoc(plan.plan);
      docRef.current = d;
      setDoc(d);
      revRef.current = plan.revision;
      setShare(plan.share);
      setPeople(plan.people);
      setPetTimes(plan.pet_buff_times);
      setSavedAt(plan.updated_at ? Date.parse(plan.updated_at) : null);
      setStatus('saved');
      setSaveError('');
      setConflict(null);
      conflictRef.current = false;
      dirty.current = false;
      setLoaded(true);
    } catch (e) {
      setLoadError(errorText(t, e, 'admin:fetchError'));
    }
  }, [round.id, loadSignups, t]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 15000);
    return () => window.clearInterval(id);
  }, []);

  // ------------------------------------------------------------ autosave
  const flush = useCallback(async () => {
    if (timer.current) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
    if (saving.current || conflictRef.current || !docRef.current) return;
    if (!dirty.current) return;
    saving.current = true;
    dirty.current = false;
    let failed = false;
    setStatus('saving');
    try {
      const res = await planApi.save(round.id, revRef.current, docRef.current);
      revRef.current = res.revision;
      setPeople(res.people);
      setSavedAt(Date.now());
      setSaveError('');
      setStatus(dirty.current ? 'dirty' : 'saved');
    } catch (e) {
      dirty.current = true;
      failed = true;
      if (isApiError(e, 'PLAN_CONFLICT')) {
        conflictRef.current = true;
        setConflict(((e.details as { revision?: number }) ?? {}).revision ?? revRef.current + 1);
        setStatus('error');
      } else if (isApiError(e, 'ROUND_CLOSED')) {
        setClosed(true);
        setStatus('error');
        setSaveError(errorText(t, e));
      } else {
        setStatus('error');
        setSaveError(e instanceof Error && isApiError(e) && e.status < 500 ? e.message : errorText(t, e));
      }
    } finally {
      saving.current = false;
      // More edits arrived while saving: save again. After a failure, the next edit (or Retry) saves.
      if (dirty.current && !conflictRef.current && !failed) schedule(); // eslint-disable-line @typescript-eslint/no-use-before-define
    }
  }, [round.id, t]); // eslint-disable-line react-hooks/exhaustive-deps

  const schedule = useCallback(() => {
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => void flush(), SAVE_DELAY);
  }, [flush]);

  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (dirty.current || saving.current) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, []);

  // Someone else may have saved meanwhile: check when the tab regains focus (only when nothing is pending here).
  useEffect(() => {
    const check = async () => {
      if (document.visibilityState !== 'visible' || dirty.current || saving.current || conflictRef.current || !loaded) return;
      try {
        const res = await planApi.get(round.id);
        if (res.revision > revRef.current) {
          conflictRef.current = true;
          setConflict(res.revision);
        }
      } catch {
        // offline: the next save will tell
      }
    };
    window.addEventListener('focus', check);
    document.addEventListener('visibilitychange', check);
    return () => {
      window.removeEventListener('focus', check);
      document.removeEventListener('visibilitychange', check);
    };
  }, [round.id, loaded]);

  const update = useCallback(
    (fn: (d: PlanDoc) => void) => {
      if (readOnly || !docRef.current) return;
      const next = structuredClone(docRef.current);
      fn(next);
      docRef.current = next;
      setDoc(next);
      dirty.current = true;
      setStatus('dirty');
      schedule();
    },
    [readOnly, schedule],
  );

  // ------------------------------------------------------------ helpers for the context
  const placed = useMemo(() => (doc ? placements(doc) : new Map<string, Placement>()), [doc]);

  const playerName = useCallback(
    (ref: PlayerRef | null | undefined) => {
      if (!ref) return '';
      if (ref.fid) return signups.get(ref.fid)?.name ?? people[ref.fid]?.game_name ?? ref.name ?? `FID ${ref.fid}`;
      return ref.name ?? '';
    },
    [signups, people],
  );

  const groupLabel = useCallback((g: PlanGroup) => g.name || t(`svs:plan.defaultName.${g.kind}`), [t]);

  const leaderLabel = useCallback(
    (l: Leader) => {
      if (l.disguise.alias) return l.disguise.alias;
      if (l.player) return playerName(l.player);
      const d = docRef.current;
      const n = d ? leadersOf(d, l.group_id).findIndex((x) => x.id === l.id) + 1 : 0;
      return t('svs:plan.leaderN', { n });
    },
    [playerName, t],
  );

  const placementLabel = useCallback(
    (p: Placement) => {
      const d = docRef.current!;
      const g = d.groups.find((x) => x.id === p.groupId);
      const gl = g ? groupLabel(g) : '';
      if (p.kind === 'extraGroup') return t('svs:plan.placed.inGroup', { group: gl });
      const l = d.leaders.find((x) => x.id === p.leaderId);
      if (p.kind === 'leader') return t('svs:plan.placed.leads', { group: gl });
      return t('svs:plan.placed.with', { leader: l ? leaderLabel(l) : '?' });
    },
    [groupLabel, leaderLabel, t],
  );

  const notify = useCallback((msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast((m) => (m === msg ? '' : m)), 4000);
  }, []);

  const placePlayer = useCallback(
    (target: PlayerTarget, ref: PlayerRef, move = false) => {
      const d = docRef.current;
      if (!d || readOnly) return { ok: false };
      const key = playerKey(ref);
      const where = key ? placements(d).get(key) : undefined;
      if (where && !move) return { ok: false, already: where };
      let ok = false;
      update((n) => {
        if (where && key) {
          const w = placements(n).get(key);
          if (w) removePlacement(n, w);
        }
        ok = applyPlayer(n, target, ref);
      });
      return { ok };
    },
    [readOnly, update],
  );

  const setArmedSlot = useCallback((s: HeroSlot | null) => {
    setArmedSlotState(s);
    if (s) setArmedHeroState(null);
  }, []);
  const setArmedHero = useCallback((slug: string | null) => {
    setArmedHeroState(slug);
    if (slug) setArmedSlotState(null);
  }, []);

  const placeHero = useCallback(
    (slot: HeroSlot, slug: string | null) => {
      update((d) => setSlotHero(d, slot, slug));
      setArmedHeroState(null);
      setArmedSlotState((cur) => {
        if (!slug || !sameSlot(cur, slot) || !docRef.current) return null;
        const nxt = nextEmptySlot(docRef.current, slot);
        return nxt && !getSlotHero(docRef.current, nxt) ? nxt : null;
      });
    },
    [update],
  );

  useEffect(() => {
    const esc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setArmedSlotState(null);
        setArmedHeroState(null);
      }
    };
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, []);

  const moveLeader = useCallback(
    (leaderId: string, groupId: string, beforeId?: string | null) =>
      update((d) => {
        const l = d.leaders.find((x) => x.id === leaderId);
        if (!l) return;
        const list = leadersOf(d, groupId).filter((x) => x.id !== leaderId);
        let idx = beforeId ? list.findIndex((x) => x.id === beforeId) : list.length;
        if (idx < 0) idx = list.length;
        list.splice(idx, 0, l);
        l.group_id = groupId;
        list.forEach((x, i) => (x.order = i));
        renumber(d);
      }),
    [update],
  );

  const quickAdd = useCallback(
    async (name: string, fid: string): Promise<PlayerRef> => {
      if (!fid) return { name };
      const profile = await api.orNull(api.admin.profile(fid));
      try {
        await api.admin.addPlayer(round.id, { fid, ...(profile ? {} : { profile: { game_name: name || `FID ${fid}` } }) });
      } catch (e) {
        if (!isApiError(e, 'APPLICATION_EXISTS')) throw e;
      }
      await loadSignups();
      return { fid };
    },
    [round.id, loadSignups],
  );

  // ------------------------------------------------------------ drag and drop
  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 5 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const onDragStart = (e: DragStartEvent) => setActive((e.active.data.current as Record<string, unknown>) ?? null);
  const onDragEnd = (e: DragEndEvent) => {
    setActive(null);
    const a = e.active.data.current as Record<string, any> | undefined;
    const o = e.over?.data.current as Record<string, any> | undefined;
    if (!a || !o || !docRef.current) return;
    if (a.type === 'hero' && o.type === 'heroSlot') {
      placeHero(o.slot as HeroSlot, a.slug as string);
    } else if (a.type === 'leader') {
      const d = docRef.current;
      if (o.type === 'leader' && o.leaderId !== a.leaderId) {
        if (o.groupId === a.groupId) {
          const list = leadersOf(d, a.groupId);
          const from = list.findIndex((x) => x.id === a.leaderId);
          const to = list.findIndex((x) => x.id === o.leaderId);
          const ids = arrayMove(list, from, to).map((x) => x.id);
          update((n) => {
            for (const l of n.leaders) if (l.group_id === a.groupId) l.order = ids.indexOf(l.id);
            renumber(n);
          });
        } else moveLeader(a.leaderId, o.groupId, o.leaderId);
      } else if (o.type === 'group' && o.groupId !== a.groupId) {
        moveLeader(a.leaderId, o.groupId, null);
      }
    } else if (a.type === 'player' && o.type === 'playerTarget') {
      const res = placePlayer(o.target as PlayerTarget, a.ref as PlayerRef);
      if (!res.ok && res.already) notify(t('svs:plan.alreadyUseMove', { name: playerName(a.ref), where: placementLabel(res.already) }));
    }
  };

  // ------------------------------------------------------------ strategy / groups
  const setStrategy = (s: Strategy) => {
    const d = docRef.current;
    if (!d || s === d.strategy) return;
    if (s === 'single') {
      const counter = d.groups.find((g) => g.kind === 'counter');
      const n = counter ? leadersOf(d, counter.id).length : 0;
      if (n && !window.confirm(t('svs:plan.confirmSingle', { n }))) return;
      update((x) => {
        const main = x.groups.find((g) => g.kind === 'main')!;
        const c = x.groups.find((g) => g.kind === 'counter');
        if (c) {
          const base = leadersOf(x, main.id).length;
          leadersOf(x, c.id).forEach((l, i) => {
            l.group_id = main.id;
            l.order = base + i;
          });
          x.groups = x.groups.filter((g) => g.id !== c.id);
        }
        x.strategy = 'single';
        renumber(x);
      });
    } else {
      update((x) => {
        x.groups.push(blankGroup('counter'));
        x.strategy = 'main_counter';
        renumber(x);
      });
    }
  };

  const addGroup = () => {
    const name = newGroupName.trim();
    update((d) => {
      const g = blankGroup('extra');
      g.name = name || null;
      d.groups.push(g);
    });
    setNewGroupName('');
    setAddingGroup(false);
  };

  // ------------------------------------------------------------ render
  if (loadError) {
    return (
      <div className="p-4 bg-danger/10 border border-danger/30 rounded-xl text-danger flex items-center gap-2" role="alert">
        <AlertCircle className="w-5 h-5" aria-hidden="true" />
        {loadError}
        <button type="button" onClick={load} className="ms-auto underline">
          {t('svs:plan.retry')}
        </button>
      </div>
    );
  }
  if (!loaded || !doc) {
    return (
      <p className="py-12 text-center text-theme-dim" role="status" data-testid="planner-loading">
        {t('common:loading')}
      </p>
    );
  }

  const ctx: PlannerCtx = {
    doc,
    readOnly,
    update,
    heroes,
    stateGen,
    signups,
    people,
    placed,
    petTimes,
    battleHours: hours,
    armedSlot,
    setArmedSlot,
    armedHero,
    setArmedHero,
    placeHero,
    placePlayer,
    quickAdd,
    playerName,
    placementLabel,
    leaderLabel,
    groupLabel,
    moveLeader,
    setSidebarTab,
    notify,
  };

  const battleGroups = doc.groups.filter((g) => g.kind !== 'extra');
  const extras = doc.groups.filter((g) => g.kind === 'extra');
  const activeHero = active?.type === 'hero' ? heroes.get(active.slug as string) : undefined;
  const activeLeader = active?.type === 'leader' ? doc.leaders.find((l) => l.id === active.leaderId) : undefined;

  const statusView = {
    saved: (
      <span className="inline-flex items-center gap-1.5 text-success" data-testid="save-status" data-status="saved">
        <CheckCircle2 className="w-4 h-4" aria-hidden="true" />
        {savedAt ? t('svs:plan.save.saved', { when: relTime(t, savedAt, now) }) : t('svs:plan.save.nothingYet')}
      </span>
    ),
    dirty: (
      <span className="inline-flex items-center gap-1.5 text-theme-dim" data-testid="save-status" data-status="dirty">
        <Loader2 className="w-4 h-4" aria-hidden="true" />
        {t('svs:plan.save.pending')}
      </span>
    ),
    saving: (
      <span className="inline-flex items-center gap-1.5 text-theme-dim" data-testid="save-status" data-status="saving">
        <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
        {t('svs:plan.save.saving')}
      </span>
    ),
    error: (
      <span className="inline-flex items-center gap-1.5 text-danger" data-testid="save-status" data-status="error">
        <CloudOff className="w-4 h-4" aria-hidden="true" />
        {t('svs:plan.save.failed')}
      </span>
    ),
  }[status];

  return (
    <PlannerContext.Provider value={ctx}>
      <div className="space-y-4" data-testid="svs-planner" data-revision={revRef.current} data-strategy={doc.strategy}>
        {/* toolbar */}
        <div className="sticky top-0 z-30 bg-dark-card/95 backdrop-blur border border-theme-border rounded-xl px-3 py-2 flex flex-wrap items-center gap-3 shadow">
          <div role="radiogroup" aria-label={t('svs:plan.strategy')} className="inline-flex rounded-lg border border-theme-border overflow-hidden" data-testid="strategy">
            {(['single', 'main_counter'] as Strategy[]).map((s) => (
              <button
                key={s}
                type="button"
                role="radio"
                aria-checked={doc.strategy === s}
                disabled={readOnly}
                onClick={() => setStrategy(s)}
                data-testid={`strategy-${s}`}
                className={`min-h-[40px] px-3 text-sm font-semibold ${doc.strategy === s ? 'bg-accent text-dark-bg' : 'text-theme-text hover:bg-dark-card-hover'}`}
              >
                {t(`svs:plan.strategyName.${s}`)}
              </button>
            ))}
          </div>
          {!readOnly && extras.length < MAX_EXTRA_GROUPS && (
            <div className="relative">
              <button
                type="button"
                onClick={() => setAddingGroup((v) => !v)}
                aria-expanded={addingGroup}
                data-testid="add-group"
                className="inline-flex items-center gap-1.5 min-h-[40px] px-3 rounded-lg border border-theme-border text-sm text-theme-text hover:border-accent"
              >
                <Plus className="w-4 h-4" aria-hidden="true" />
                {t('svs:plan.addGroup')}
              </button>
              {addingGroup && (
                <div role="dialog" aria-label={t('svs:plan.addGroup')} className="absolute z-40 top-full start-0 mt-1 w-72 p-3 bg-dark-bg border border-accent/40 rounded-lg shadow-2xl space-y-2" data-testid="add-group-dialog">
                  <p className="text-xs text-theme-dim">{t('svs:plan.addGroupHint')}</p>
                  <input
                    autoFocus
                    value={newGroupName}
                    maxLength={40}
                    onChange={(e) => setNewGroupName(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && addGroup()}
                    placeholder={t('svs:plan.addGroupPlaceholder')}
                    aria-label={t('svs:plan.groupName')}
                    data-testid="add-group-name"
                    className="w-full min-h-[36px] px-2 text-sm bg-dark-input border border-theme-border rounded-md text-theme-text"
                  />
                  <div className="flex gap-2">
                    <button type="button" onClick={addGroup} data-testid="add-group-save" className="min-h-[36px] px-3 rounded-md bg-accent text-dark-bg text-sm font-bold">
                      {t('svs:plan.add')}
                    </button>
                    <button type="button" onClick={() => setAddingGroup(false)} className="min-h-[36px] px-3 rounded-md border border-theme-border text-sm text-theme-dim">
                      {t('common:cancel')}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
          <p className="hidden xl:flex items-center gap-1.5 text-xs text-theme-dim">
            <Info className="w-4 h-4 shrink-0" aria-hidden="true" />
            {t('svs:plan.howTo')}
          </p>
          <div className="ms-auto text-sm" aria-live="polite">
            {statusView}
          </div>
        </div>

        {conflict != null && (
          <div className="p-4 rounded-xl border-2 border-warning bg-warning/15 flex flex-wrap items-center gap-3" role="alert" data-testid="conflict-banner">
            <AlertTriangle className="w-6 h-6 text-warning shrink-0" aria-hidden="true" />
            <div className="flex-1 min-w-[16rem]">
              <p className="font-bold text-theme-text">{t('svs:plan.conflictTitle')}</p>
              <p className="text-sm text-theme-dim">{t('svs:plan.conflictBody')}</p>
            </div>
            <button type="button" onClick={load} data-testid="conflict-reload" className="inline-flex items-center gap-2 min-h-[44px] px-4 rounded-lg bg-warning text-dark-bg font-bold">
              <RefreshCw className="w-4 h-4" aria-hidden="true" />
              {t('svs:plan.reload')}
            </button>
          </div>
        )}
        {status === 'error' && saveError && conflict == null && (
          <div className="p-3 rounded-xl border border-danger/40 bg-danger/10 text-danger flex flex-wrap items-center gap-2" role="alert" data-testid="save-error">
            <CloudOff className="w-5 h-5 shrink-0" aria-hidden="true" />
            <span className="flex-1">{t('svs:plan.saveError', { msg: saveError })}</span>
            {!closed && (
              <button type="button" onClick={() => void flush()} className="underline font-semibold">
                {t('svs:plan.retry')}
              </button>
            )}
          </div>
        )}
        {toast && (
          <div className="fixed bottom-4 start-1/2 -translate-x-1/2 rtl:translate-x-1/2 z-50 px-4 py-2 rounded-lg bg-dark-bg border border-warning text-warning shadow-2xl text-sm" role="status" data-testid="planner-toast">
            {toast}
          </div>
        )}

        <DndContext sensors={sensors} collisionDetection={collision} onDragStart={onDragStart} onDragEnd={onDragEnd} onDragCancel={() => setActive(null)}>
          <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_19.5rem] gap-4 items-start">
            <div className="space-y-4 min-w-0">
              <div className={doc.strategy === 'main_counter' ? 'grid grid-cols-1 xl:grid-cols-2 gap-4 items-start' : ''}>
                {battleGroups.map((g) => (
                  <GroupColumn key={g.id} group={g} wide={doc.strategy === 'single'} />
                ))}
              </div>
              {extras.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
                  {extras.map((g) => (
                    <ExtraGroupCard key={g.id} group={g} />
                  ))}
                </div>
              )}
            </div>
            <div className="space-y-4 lg:sticky lg:top-16">
              <SharePanel roundId={round.id} share={share} onShare={setShare} />
              <Sidebar tab={sidebarTab} setTab={setSidebarTab} />
            </div>
          </div>
          <DragOverlay dropAnimation={null}>
            {activeHero ? (
              <HeroCard hero={activeHero} size="sm" className="shadow-2xl ring-2 ring-accent" />
            ) : activeLeader ? (
              <div className="px-4 py-3 rounded-xl bg-dark-card border-2 border-accent shadow-2xl font-semibold text-theme-text">{leaderLabel(activeLeader)}</div>
            ) : active?.type === 'player' ? (
              <div className="px-3 py-2 rounded-full bg-dark-card border-2 border-accent shadow-2xl text-sm font-semibold text-theme-text">
                {playerName(active.ref as PlayerRef)}
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      </div>
    </PlannerContext.Provider>
  );
}
