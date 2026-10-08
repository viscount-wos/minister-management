// Type-ahead player search (ARIA combobox) over the round's SVS sign-ups: name, FID or alliance, filtering as you
// type. Results show strength, troop line, hours and VC (strongest first; SVS sign-up has no role); players already in the plan carry "Already with ..." and an
// explicit "Move here". "Quick add" at the bottom adds someone who never signed up (with an FID they get a sign-up).
import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Headphones, Search, UserPlus, ArrowRightLeft } from 'lucide-react';
import { usePlanner, type SignupInfo } from './PlannerContext';
import { TroopLine, hoursText } from './widgets';
import { playerKey, type PlayerRef, type PlayerTarget } from './model';
import { errorText } from '../../../shared/apiErrors';

const MAX_RESULTS = 8;

export default function PlayerSearch({
  target,
  placeholder,
  testid,
  autoFocus = false,
  onPlaced,
}: {
  target: PlayerTarget;
  placeholder: string;
  testid: string;
  autoFocus?: boolean;
  onPlaced?: () => void;
}) {
  const { t } = useTranslation();
  const ctx = usePlanner();
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [quick, setQuick] = useState<{ name: string; fid: string; busy: boolean; error: string } | null>(null);
  const [msg, setMsg] = useState('');
  const id = useId();
  const wrap = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (autoFocus) input.current?.focus();
  }, [autoFocus]);

  useEffect(() => {
    const onDoc = (e: PointerEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', onDoc);
    return () => document.removeEventListener('pointerdown', onDoc);
  }, []);

  const results = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const all = [...ctx.signups.values()];
    const hit = (s: SignupInfo) =>
      !needle ||
      s.name.toLowerCase().includes(needle) ||
      s.fid.startsWith(needle) ||
      (s.alliance ?? '').toLowerCase() === needle.replace(/[[\]]/g, '');
    // Unplaced first, then names starting with what was typed, then the strongest troops.
    const score = (s: SignupInfo) => (ctx.placed.has(`fid:${s.fid}`) ? 2 : 0) + (needle && !s.name.toLowerCase().startsWith(needle) ? 1 : 0);
    return all
      .filter(hit)
      .sort((a, b) => score(a) - score(b) || (b.strength ?? -1) - (a.strength ?? -1) || a.name.localeCompare(b.name))
      .slice(0, MAX_RESULTS);
  }, [q, ctx.signups, ctx.placed]);

  const count = results.length + 1; // + quick add
  const optionId = (i: number) => `${id}-opt-${i}`;

  const place = (ref: PlayerRef, move = false) => {
    const res = ctx.placePlayer(target, ref, move);
    if (res.ok) {
      setQ('');
      setOpen(false);
      setMsg('');
      setQuick(null);
      onPlaced?.();
    } else if (res.already) {
      setMsg(t('svs:plan.alreadyUseMove', { name: ctx.playerName(ref), where: ctx.placementLabel(res.already) }));
    }
  };

  const choose = (i: number) => {
    if (i < results.length) {
      place({ fid: results[i].fid });
    } else {
      const digits = /^\d{4,20}$/.test(q.trim());
      setQuick({ name: digits ? '' : q.trim(), fid: digits ? q.trim() : '', busy: false, error: '' });
      setOpen(false);
    }
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setOpen(true);
      setActive((a) => (a + 1) % count);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setOpen(true);
      setActive((a) => (a - 1 + count) % count);
    } else if (e.key === 'Enter') {
      if (!open) return;
      e.preventDefault();
      choose(active);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  const submitQuick = async () => {
    if (!quick) return;
    const name = quick.name.trim();
    const fid = quick.fid.trim();
    if (!name && !fid) return;
    setQuick({ ...quick, busy: true, error: '' });
    try {
      const ref = await ctx.quickAdd(name, fid);
      const res = ctx.placePlayer(target, ref);
      if (!res.ok && res.already) {
        setQuick({ ...quick, busy: false, error: t('svs:plan.alreadyUseMove', { name: ctx.playerName(ref), where: ctx.placementLabel(res.already) }) });
        return;
      }
      setQuick(null);
      setQ('');
      onPlaced?.();
    } catch (e) {
      setQuick({ ...quick, busy: false, error: errorText(t, e, 'svs:plan.quickAddError') });
    }
  };

  if (ctx.readOnly) return null;

  return (
    <div ref={wrap} className="relative min-w-0 flex-1" data-testid={testid}>
      <div className="relative">
        <Search className="absolute start-2 top-1/2 -translate-y-1/2 w-4 h-4 text-theme-dim pointer-events-none" aria-hidden="true" />
        <input
          ref={input}
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={`${id}-list`}
          aria-autocomplete="list"
          aria-activedescendant={open ? optionId(active) : undefined}
          aria-label={placeholder}
          value={q}
          placeholder={placeholder}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
            setActive(0);
            setMsg('');
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKey}
          data-testid={`${testid}-input`}
          className="w-full min-h-[36px] ps-8 pe-2 py-1 text-sm bg-dark-input border border-theme-border rounded-lg text-theme-text placeholder:text-theme-dim focus:ring-2 focus:ring-accent focus:border-accent"
        />
      </div>
      {open && (
        <ul
          id={`${id}-list`}
          role="listbox"
          aria-label={placeholder}
          className="absolute z-50 top-full start-0 mt-1 w-[22rem] max-w-[90vw] max-h-[26rem] overflow-y-auto bg-dark-bg border border-accent/40 rounded-lg shadow-2xl py-1"
          data-testid={`${testid}-results`}
        >
          {results.length === 0 && <li className="px-3 py-2 text-sm text-theme-dim">{t('svs:plan.noMatches')}</li>}
          {results.map((s, i) => {
            const where = ctx.placed.get(`fid:${s.fid}`);
            return (
              <li
                key={s.fid}
                id={optionId(i)}
                role="option"
                aria-selected={active === i}
                data-testid={`option-${s.fid}`}
                data-placed={where ? 'true' : undefined}
                onPointerEnter={() => setActive(i)}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => (where ? setMsg(t('svs:plan.alreadyUseMove', { name: s.name, where: ctx.placementLabel(where) })) : choose(i))}
                className={`px-3 py-2 cursor-pointer border-b border-theme-border/30 last:border-0 ${active === i ? 'bg-accent/15' : ''} ${
                  where ? 'opacity-80' : ''
                }`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="min-w-0 truncate font-semibold text-theme-text">
                    {s.alliance && <span className="text-accent font-normal">[{s.alliance}] </span>}
                    <bdi>{s.name}</bdi>
                  </span>
                  {s.strength != null && (
                    <span className="shrink-0 px-1.5 rounded text-[10px] font-semibold bg-accent/20 text-accent" title={t('svs:plan.strength')}>
                      {s.strength}
                    </span>
                  )}
                  {s.vc && <Headphones className="w-3.5 h-3.5 shrink-0 text-success" aria-label={t('svs:plan.vcYes')} role="img" />}
                  <span className="ms-auto shrink-0 text-[10px] text-theme-dim" dir="ltr">
                    {s.fid}
                  </span>
                </div>
                <div className="text-[11px] text-theme-dim mt-0.5">
                  <TroopLine troops={s.troops} />
                </div>
                <div className="text-[11px] text-theme-dim">
                  {t('svs:plan.hoursLabel')}{' '}
                  <bdi dir="ltr">{hoursText(s.hours, ctx.battleHours)}</bdi>
                </div>
                {where && (
                  <div className="mt-1 flex items-center gap-2">
                    <span className="px-1.5 py-0.5 rounded bg-warning/15 text-warning text-[11px] font-semibold" data-testid="already-placed">
                      {ctx.placementLabel(where)}
                    </span>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        place({ fid: s.fid }, true);
                      }}
                      data-testid={`move-here-${s.fid}`}
                      className="ms-auto inline-flex items-center gap-1 px-2 py-0.5 rounded border border-accent/50 text-accent text-[11px] font-semibold hover:bg-accent/15"
                    >
                      <ArrowRightLeft className="w-3 h-3" aria-hidden="true" />
                      {t('svs:plan.moveHere')}
                    </button>
                  </div>
                )}
              </li>
            );
          })}
          <li
            id={optionId(results.length)}
            role="option"
            aria-selected={active === results.length}
            onPointerEnter={() => setActive(results.length)}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => choose(results.length)}
            data-testid="option-quick-add"
            className={`px-3 py-2 cursor-pointer flex items-center gap-2 text-sm text-accent font-semibold ${active === results.length ? 'bg-accent/15' : ''}`}
          >
            <UserPlus className="w-4 h-4" aria-hidden="true" />
            {q.trim() ? t('svs:plan.quickAddNamed', { name: q.trim() }) : t('svs:plan.quickAdd')}
          </li>
        </ul>
      )}
      {msg && (
        <p className="mt-1 text-xs text-warning" role="alert" data-testid={`${testid}-msg`}>
          {msg}
        </p>
      )}
      {quick && (
        <div className="mt-2 p-2 rounded-lg border border-accent/40 bg-dark-bg space-y-2" data-testid="quick-add-form">
          <p className="text-xs text-theme-dim">{t('svs:plan.quickAddHint')}</p>
          <div className="flex flex-wrap gap-2">
            <input
              value={quick.name}
              onChange={(e) => setQuick({ ...quick, name: e.target.value })}
              placeholder={t('svs:plan.quickName')}
              aria-label={t('svs:plan.quickName')}
              data-testid="quick-add-name"
              maxLength={40}
              className="flex-1 min-w-[8rem] min-h-[36px] px-2 text-sm bg-dark-input border border-theme-border rounded-md text-theme-text"
            />
            <input
              value={quick.fid}
              onChange={(e) => setQuick({ ...quick, fid: e.target.value.replace(/\D/g, '') })}
              placeholder={t('svs:plan.quickFid')}
              aria-label={t('svs:plan.quickFid')}
              data-testid="quick-add-fid"
              inputMode="numeric"
              dir="ltr"
              className="w-32 min-h-[36px] px-2 text-sm bg-dark-input border border-theme-border rounded-md text-theme-text"
            />
          </div>
          {quick.error && (
            <p className="text-xs text-danger" role="alert">
              {quick.error}
            </p>
          )}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={submitQuick}
              disabled={quick.busy || (!quick.name.trim() && !quick.fid.trim())}
              data-testid="quick-add-submit"
              className="min-h-[36px] px-3 rounded-md bg-accent text-dark-bg text-sm font-semibold disabled:opacity-50"
            >
              {quick.fid.trim() ? t('svs:plan.quickAddSignUp') : t('svs:plan.quickAddPlanOnly')}
            </button>
            <button type="button" onClick={() => setQuick(null)} className="min-h-[36px] px-3 rounded-md border border-theme-border text-sm text-theme-dim">
              {t('common:cancel')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/** Ref equality helper for callers. */
export const sameRef = (a: PlayerRef | null, b: PlayerRef | null) => playerKey(a) === playerKey(b);
