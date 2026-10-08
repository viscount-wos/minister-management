// /svs/plan/<token>: the shared, read-only battle plan (phone-first). Each group, its joining rules and notes, then
// its rally leaders in order: disguise (PFP + alias), heroes as pictures, troop ratio, pet-buff moment with its time,
// named joiners with their lead hero, "everyone else may use" heroes and extra joiners. "Find me" scrolls to a
// player's place. noindex + no-referrer (meta here, headers from the server).
import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Drama, LocateFixed, PawPrint, Search, Shield, Swords, Users, StickyNote, Clock, Link2Off } from 'lucide-react';
import { isApiError } from '../../../shared/api';
import { errorText } from '../../../shared/apiErrors';
import { usePageTitle } from '../../../shared/usePageTitle';
import { useTimezone } from '../../../shared/TimezoneContext';
import { formatTimeInTimezone } from '../../../shared/timezone';
import { planApi } from './api';
import { HeroTile, MinimumsList, RatioBar, TEAM, petBuffLabel } from './bits';
import { hasMinimums } from './model';
import type { PlanView, ViewGroup, ViewLeader, ViewPerson, ViewSide } from './model';

function useNoIndex() {
  useEffect(() => {
    const metas = [
      Object.assign(document.createElement('meta'), { name: 'robots', content: 'noindex, nofollow' }),
      Object.assign(document.createElement('meta'), { name: 'referrer', content: 'no-referrer' }),
    ];
    metas.forEach((m) => document.head.appendChild(m));
    return () => metas.forEach((m) => m.remove());
  }, []);
}

const norm = (s: string) => s.trim().toLowerCase().replace(/\s+/g, ' ');

interface Spot {
  id: string;
  person: ViewPerson;
  where: string;
}

function Name({ p, spotId, found }: { p: ViewPerson; spotId: string; found: string | null }) {
  return (
    <span
      id={spotId}
      data-spot={spotId}
      data-found={found === spotId || undefined}
      className={`inline-block rounded px-1 -mx-1 scroll-mt-24 ${found === spotId ? 'bg-accent text-dark-bg ring-4 ring-accent/40' : ''}`}
    >
      {p.alliance && <span className={found === spotId ? '' : 'text-accent'}>[{p.alliance}] </span>}
      <bdi className="font-semibold">{p.name}</bdi>
    </span>
  );
}

function SideBlock({ side, label, team }: { side: ViewSide; label: string | null; team: string }) {
  const { t } = useTranslation();
  return (
    <div className="space-y-2">
      {label && <h4 className={`text-xs font-bold uppercase tracking-wide ${team}`}>{label}</h4>}
      <div className="flex gap-2" data-testid="view-heroes">
        {side.heroes.map((h, i) => (
          <HeroTile key={i} hero={h} size="lg" />
        ))}
      </div>
      <div>
        <div className="text-[11px] text-theme-dim mb-1">{t('svs:view.troopRatio')}</div>
        <RatioBar ratio={side.ratio} testid="view-ratio" />
      </div>
    </div>
  );
}

function LeaderView({ l, group, spots, found }: { l: ViewLeader; group: ViewGroup; spots: Map<string, string>; found: string | null }) {
  const { t } = useTranslation();
  const team = TEAM[group.kind];
  const sides = l.split ? (['rally', 'garrison'] as const) : (['rally'] as const);
  const sideLabel = (s: 'rally' | 'garrison') => (l.split ? t(`svs:plan.side.${s}`) : null);
  const leaderSpot = spots.get(`L:${l.id}`);
  return (
    <article className={`bg-dark-card border border-theme-border border-s-4 ${team.border} rounded-xl p-3 space-y-4`} data-testid="view-leader" data-leader-id={l.id}>
      <header className="flex items-start gap-3">
        <span className={`shrink-0 min-w-[2.25rem] h-9 px-2 rounded-lg ${team.bar} text-dark-bg font-extrabold flex items-center justify-center`}>{l.number}</span>
        {l.pfp_hero && (
          <img src={l.pfp_hero.image ?? ''} alt={l.pfp_hero.name} className="w-12 h-12 rounded-full object-cover border-2 border-accent shrink-0" />
        )}
        <div className="min-w-0 flex-1">
          {l.alias ? (
            <>
              <p className="text-lg font-extrabold text-accent leading-tight break-words" data-testid="view-alias">
                <bdi>{l.alias}</bdi>
              </p>
              {l.player && leaderSpot && (
                <p className="text-sm text-theme-text" data-testid="view-real-name">
                  <Name p={l.player} spotId={leaderSpot} found={found} />
                </p>
              )}
              {l.pfp_hero && (
                <p className="text-[11px] text-theme-dim flex items-center gap-1">
                  <Drama className="w-3.5 h-3.5" aria-hidden="true" />
                  {t('svs:view.disguise', { hero: l.pfp_hero.name })}
                </p>
              )}
            </>
          ) : l.player && leaderSpot ? (
            <p className="text-lg text-theme-text leading-tight" data-testid="view-real-name">
              <Name p={l.player} spotId={leaderSpot} found={found} />
            </p>
          ) : (
            <p className="text-lg text-theme-dim">{t('svs:plan.leaderN', { n: l.number })}</p>
          )}
        </div>
      </header>

      <div className={l.split ? 'grid grid-cols-1 sm:grid-cols-2 gap-4' : ''}>
        {sides.map((s) => (
          <div key={s} data-testid={`view-${s}`}>
            <SideBlock side={l[s]!} label={sideLabel(s)} team={team.text} />
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2 text-sm" data-testid="view-pet">
        <PawPrint className="w-4 h-4 text-accent shrink-0" aria-hidden="true" />
        <span className="text-theme-dim">{t('svs:plan.petBuffs')}:</span>
        <span className="font-semibold text-theme-text">
          {l.pet_buff && l.pet_buff_time ? petBuffLabel(t, l.pet_buff, l.pet_buff_time) : t('svs:view.petNotSet')}
        </span>
      </div>

      {l.named_joiners.length > 0 && (
        <section>
          <h4 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-theme-dim mb-2">
            <Users className="w-4 h-4" aria-hidden="true" />
            {t('svs:plan.namedJoiners')}
          </h4>
          <ol className="space-y-2" data-testid="view-joiners">
            {l.named_joiners.map((j, i) => {
              const spot = spots.get(`J:${l.id}:${i}`)!;
              return (
                <li key={i} className="rounded-lg bg-dark-bg border border-theme-border/60 p-2">
                  <div className="text-sm text-theme-text mb-1.5">
                    <span className="text-theme-dim me-1.5">{i + 1}.</span>
                    <Name p={j.player} spotId={spot} found={found} />
                  </div>
                  <div className={l.split ? 'grid grid-cols-2 gap-2' : ''}>
                    {sides.map((s) => {
                      const js = j[s];
                      if (!js) return null;
                      return (
                        <div key={s} className="flex items-center gap-2 min-w-0" data-testid={`view-joiner-${s}`}>
                          <HeroTile hero={js.lead_hero} size="sm" />
                          <div className="min-w-0 text-xs">
                            {l.split && <div className={`font-bold ${team.text}`}>{t(`svs:plan.side.${s}`)}</div>}
                            {!l.split && <div className="text-theme-dim">{t('svs:plan.leadHeroShort')}</div>}
                            {js.ratio_overridden && js.ratio && (
                              <span className="block text-warning font-semibold" data-testid="view-own-ratio">
                                {t('svs:view.ownRatio')}:{' '}
                                <bdi dir="ltr">
                                  {js.ratio.inf}/{js.ratio.lan}/{js.ratio.mks}
                                </bdi>
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </li>
              );
            })}
          </ol>
          <p className="mt-1.5 text-[11px] text-theme-dim">{t('svs:view.joinersRatioNote')}</p>
        </section>
      )}

      {sides.some((s) => l[s]!.other_joiner_heroes.length > 0) && (
        <section data-testid="view-others">
          <h4 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-theme-dim mb-2">
            <Users className="w-4 h-4" aria-hidden="true" />
            {t('svs:plan.everyoneElse')}
          </h4>
          {sides.map((s) =>
            l[s]!.other_joiner_heroes.length ? (
              <div key={s} className="flex items-center gap-2 mb-1">
                {l.split && <span className={`w-16 shrink-0 text-[11px] font-bold ${team.text}`}>{t(`svs:plan.side.${s}`)}</span>}
                <div className="flex flex-wrap gap-2">
                  {l[s]!.other_joiner_heroes.map((h, i) => (
                    <HeroTile key={i} hero={h} size="sm" />
                  ))}
                </div>
              </div>
            ) : null,
          )}
        </section>
      )}

      {l.extra_joiners.length > 0 && (
        <section>
          <h4 className="text-xs font-bold uppercase tracking-wide text-theme-dim mb-2">{t('svs:plan.extraJoiners')}</h4>
          <ul className="flex flex-wrap gap-1.5" data-testid="view-extras">
            {l.extra_joiners.map((p, i) => (
              <li key={i} className="px-2 py-0.5 rounded-full bg-dark-input border border-theme-border text-xs text-theme-text">
                <Name p={p} spotId={spots.get(`E:${l.id}:${i}`)!} found={found} />
              </li>
            ))}
          </ul>
        </section>
      )}
    </article>
  );
}

export default function SvsPlanView() {
  const { token = '' } = useParams();
  const { t } = useTranslation();
  const { timezone } = useTimezone();
  const [plan, setPlan] = useState<PlanView | null>(null);
  const [error, setError] = useState<'notFound' | string | null>(null);
  const [q, setQ] = useState('');
  const [found, setFound] = useState<string | null>(null);
  const [findMsg, setFindMsg] = useState('');
  const [choices, setChoices] = useState<Spot[]>([]);
  const findRef = useRef<HTMLInputElement>(null);
  useNoIndex();
  usePageTitle(plan ? `${t('svs:view.title')} · ${plan.round_name}` : t('svs:view.title'));

  useEffect(() => {
    planApi
      .shared(token)
      .then(setPlan)
      .catch((e) => setError(isApiError(e) && e.status === 404 ? 'notFound' : errorText(t, e)));
  }, [token, t]);

  // Every place a player appears, with a readable "where" for Find me.
  const spots = useMemo(() => {
    const ids = new Map<string, string>();
    const list: Spot[] = [];
    if (!plan) return { ids, list };
    let n = 0;
    const gname = (g: ViewGroup) => g.name || t(`svs:plan.defaultName.${g.kind}`);
    for (const g of plan.groups) {
      for (const l of g.leaders ?? []) {
        const lname = l.alias || l.player?.name || t('svs:plan.leaderN', { n: l.number });
        if (l.player) {
          const id = `spot-${n++}`;
          ids.set(`L:${l.id}`, id);
          list.push({ id, person: l.player, where: t('svs:view.youLead', { leader: lname, group: gname(g) }) });
        }
        l.named_joiners.forEach((j, i) => {
          const id = `spot-${n++}`;
          ids.set(`J:${l.id}:${i}`, id);
          list.push({ id, person: j.player, where: t('svs:view.youJoin', { n: i + 1, leader: lname, group: gname(g) }) });
        });
        l.extra_joiners.forEach((p, i) => {
          const id = `spot-${n++}`;
          ids.set(`E:${l.id}:${i}`, id);
          list.push({ id, person: p, where: t('svs:view.youExtra', { leader: lname, group: gname(g) }) });
        });
      }
      (g.players ?? []).forEach((p, i) => {
        const id = `spot-${n++}`;
        ids.set(`G:${g.id}:${i}`, id);
        list.push({ id, person: p, where: t('svs:view.youGroup', { group: gname(g) }) });
      });
    }
    return { ids, list };
  }, [plan, t]);

  const goTo = (s: Spot) => {
    setFound(s.id);
    setChoices([]);
    setFindMsg(s.where);
    window.setTimeout(() => document.getElementById(s.id)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50);
  };

  const find = (e?: React.FormEvent) => {
    e?.preventDefault();
    const needle = norm(q);
    if (!needle) return;
    const exact = spots.list.filter((s) => s.person.fid === needle || norm(s.person.name) === needle);
    const partial = exact.length ? exact : spots.list.filter((s) => norm(s.person.name).includes(needle));
    if (partial.length === 1) goTo(partial[0]);
    else if (partial.length > 1) {
      setFound(null);
      setChoices(partial.slice(0, 8));
      setFindMsg(t('svs:view.severalFound'));
    } else {
      setFound(null);
      setChoices([]);
      setFindMsg(t('svs:view.notFound'));
    }
  };

  if (error === 'notFound') {
    return (
      <div className="min-h-[60vh] px-4 py-10 flex items-start justify-center">
        <div className="max-w-md w-full bg-dark-card border border-theme-border rounded-xl p-6 text-center space-y-3" data-testid="plan-not-found">
          <Link2Off className="w-10 h-10 mx-auto text-theme-dim" aria-hidden="true" />
          <h1 className="text-xl font-bold text-theme-text">{t('svs:view.notFoundTitle')}</h1>
          <p className="text-theme-dim">{t('svs:view.notFoundBody')}</p>
          <Link to="/svs" className="inline-block min-h-[44px] px-4 py-2.5 rounded-lg bg-accent text-dark-bg font-semibold">
            {t('svs:apply.backHome')}
          </Link>
        </div>
      </div>
    );
  }
  if (error) {
    return (
      <p className="py-16 text-center text-danger" role="alert">
        {error}
      </p>
    );
  }
  if (!plan) {
    return (
      <p className="py-16 text-center text-theme-dim" role="status">
        {t('common:loading')}
      </p>
    );
  }

  const local = (hhmm: string) => (timezone === 'UTC' ? '' : ` · ${formatTimeInTimezone(hhmm, timezone)}`);

  return (
    <div className="px-3 sm:px-4 py-4 sm:py-8" data-testid="svs-plan-view">
      <div className="max-w-3xl mx-auto space-y-5">
        <header className="space-y-1">
          <p className="text-xs font-bold uppercase tracking-wider text-accent">{t('svs:view.title')}</p>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-theme-text break-words" data-testid="view-round">
            {plan.round_name}
          </h1>
          <p className="text-sm text-theme-dim flex items-center gap-1.5">
            <Clock className="w-4 h-4" aria-hidden="true" />
            <bdi dir="ltr">
              {plan.battle.start}–{plan.battle.end} UTC
            </bdi>
            {local(plan.battle.start) && (
              <span>
                ({t('svs:view.localTimes', { range: `\u2066${formatTimeInTimezone(plan.battle.start, timezone)}–${formatTimeInTimezone(plan.battle.end, timezone)}\u2069` })})
              </span>
            )}
          </p>
        </header>

        {/* Find me */}
        <form onSubmit={find} className="sticky top-0 z-20 bg-dark-bg/95 backdrop-blur py-2 -mx-1 px-1" role="search" data-testid="find-me">
          <label htmlFor="find-me-input" className="block text-sm font-semibold text-theme-text mb-1">
            {t('svs:view.findMe')}
          </label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute start-3 top-1/2 -translate-y-1/2 w-4 h-4 text-theme-dim pointer-events-none" aria-hidden="true" />
              <input
                id="find-me-input"
                ref={findRef}
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder={t('svs:view.findPlaceholder')}
                data-testid="find-me-input"
                className="w-full min-h-[44px] ps-9 pe-3 text-base bg-dark-input border border-theme-border rounded-lg text-theme-text"
              />
            </div>
            <button type="submit" data-testid="find-me-go" className="shrink-0 inline-flex items-center gap-1.5 min-h-[44px] px-4 rounded-lg bg-accent text-dark-bg font-bold">
              <LocateFixed className="w-4 h-4" aria-hidden="true" />
              {t('svs:view.find')}
            </button>
          </div>
          {findMsg && (
            <p className={`mt-1.5 text-sm ${found ? 'text-accent font-semibold' : 'text-theme-dim'}`} role="status" data-testid="find-me-result">
              {findMsg}
            </p>
          )}
          {choices.length > 0 && (
            <ul className="mt-1.5 flex flex-wrap gap-1.5">
              {choices.map((c) => (
                <li key={c.id}>
                  <button type="button" onClick={() => goTo(c)} className="min-h-[36px] px-3 rounded-full border border-theme-border text-sm text-theme-text">
                    <bdi>{c.person.name}</bdi>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </form>

        {plan.groups.map((g) => {
          const team = TEAM[g.kind];
          const Icon = g.kind === 'counter' ? Shield : g.kind === 'main' ? Swords : Users;
          return (
            <section key={g.id} className="space-y-3" data-testid={`view-group-${g.kind}`}>
              <div className={`rounded-xl border-2 ${team.border} ${team.bg} p-3`}>
                <div className="flex items-center gap-2 flex-wrap">
                  <Icon className={`w-5 h-5 ${team.text}`} aria-hidden="true" />
                  <span className={`px-2 py-0.5 rounded-md ${team.bar} text-dark-bg text-xs font-extrabold uppercase tracking-wider`}>{t(`svs:plan.kind.${g.kind}`)}</span>
                  <h2 className="text-xl font-extrabold text-theme-text">
                    {g.alliance_tag && <span className="text-accent">[{g.alliance_tag}] </span>}
                    <bdi>{g.name || t(`svs:plan.defaultName.${g.kind}`)}</bdi>
                  </h2>
                </div>
                {g.min_requirements && hasMinimums(g.min_requirements) && (
                  <div className="mt-2">
                    <p className="text-xs text-theme-dim mb-1">{t('svs:view.joinRules')}</p>
                    <MinimumsList mins={g.min_requirements} />
                  </div>
                )}
                {g.notes && (
                  <p className="mt-2 text-sm text-theme-text whitespace-pre-line flex gap-1.5" data-testid="view-notes">
                    <StickyNote className="w-4 h-4 text-theme-dim shrink-0 mt-0.5" aria-hidden="true" />
                    <span>{g.notes}</span>
                  </p>
                )}
              </div>
              {g.kind === 'extra' ? (
                <ul className="flex flex-wrap gap-1.5 px-1">
                  {(g.players ?? []).map((p, i) => (
                    <li key={i} className="px-2 py-1 rounded-full bg-dark-card border border-theme-border text-sm text-theme-text">
                      <Name p={p} spotId={spots.ids.get(`G:${g.id}:${i}`)!} found={found} />
                    </li>
                  ))}
                </ul>
              ) : (g.leaders ?? []).length === 0 ? (
                <p className="text-sm text-theme-dim px-1">{t('svs:view.noLeaders')}</p>
              ) : (
                (g.leaders ?? []).map((l) => <LeaderView key={l.id} l={l} group={g} spots={spots.ids} found={found} />)
              )}
            </section>
          );
        })}

        <footer className="pt-4 border-t border-theme-border text-xs text-theme-dim space-y-1">
          <p>{t('svs:view.timesNote')}</p>
          <p>{t('common:heroes.credit')}</p>
        </footer>
      </div>
    </div>
  );
}
