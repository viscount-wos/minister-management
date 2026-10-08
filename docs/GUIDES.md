# Guides: what documents what

Owner rule: **every section has a player guide and an admin guide in all 9 languages, and every user-visible change
updates the guide that describes it in the same change** (see claude.md "Documentation rule").

All guide text lives in the i18n namespace `guide` (`frontend/src/i18n/locales/<lang>/guide.json`, 9 languages,
checked by `check-i18n`). It is a **lazy chunk per language** (`guide-<lang>`, `i18n/index.ts` `loadGuides`): players
on sign-up pages never download it; a guide page loads it through `shared/guide/useGuidesReady.tsx`. The short link
texts that appear on normal pages live in `common:guideLinks.*` (eager). Shared look: `shared/guide/GuideBits.tsx`
(`GuideSection`, `GuideList` (bullets or numbered steps), `GuideNote`, `GuideTips`, `PlayerGuideFrame`) and
`shared/guide/GuideLink.tsx`.

## Map: guide -> route -> keys -> component -> screens it describes

| Guide | Route | i18n keys | Component | Describes (keep in step with) |
|---|---|---|---|---|
| Minister player guide | `/minister/guide` (`#apply`) | `guide:player.*` | `events/ministry/PlayerGuide.tsx` | `MinistryHome`, `ApplicationWizard` (5 steps, FID + find-your-ID hint, furnace FC10..FC1 then 30..1, speedups/crystals, hours + heat map + timezone, review), `MyAssignments`, `PublishedSchedule`, closing time |
| Frost Dragon Tyrant player guide | `/tyrant/guide` (`#apply`, `#camps`) | `guide:tyrantPlayer.*` | `events/tyrant/TyrantGuide.tsx` | `TyrantPage`, `TyrantWizard` (6 steps: identity, windows (UTC) + VC, power/gems, camp FC1-FC10 + T8-T11 per troop, roles, review) |
| SVS player guide | `/svs/guide` (`#apply`, `#plan`, `#secret`) | `guide:svsPlayer.*` | `events/svs/SvsGuide.tsx` | `SvsPage`, `SvsWizard` (5 steps: player, hours, camps + T10/T11, voice chat, review) and the shared plan view `plan/SvsPlanView.tsx` (Find me, groups, joining rules, leaders, heroes, ratio, split, pet buffs, named/other/extra joiners, aliases/PFP and keeping them secret) |
| Event Management basics | `/admin/guide?event=<key>&topic=basics` | `guide:basics.*` | `admin/EventBasicsGuide.tsx` | `AdminLogin`, `AdminShell` (event switch, Round menu, status, read-only banner, Logout), `StartNewRoundDialog`, `RenameRound`, `AddPlayerDialog`, closing-time inputs (display timezone), `HeroGenerationSetting`, state number, filters in the URL + filtered exports, rate limits (`core/ratelimit.py`, login throttle), share links |
| Minister admin guide | `/admin/guide?event=ministry` | `guide:admin.*` | `events/ministry/admin/MinistryAdminGuide.tsx` | `PlayerManagement` (table, sort, search, edit, delete, Add player, JSON export/import), `AssignmentManagement` (Auto Assign, drag-and-drop, tap-to-move, locks, publish, Excel), `AdminSettings` (state number, hero generation, closing time, research day, fire crystals, slot scheme, published days) |
| Frost Dragon Tyrant admin guide | `/admin/guide?event=tyrant` | `guide:tyrantAdmin.*` | `events/tyrant/admin/TyrantAdminGuide.tsx` | `TyrantPlayers` (cards, clickable chips/bars, filter bar + More filters, pills, URL filters, Strength, no gem total, no furnace, exports, Add player, delete, pages), `TyrantRoundSettings` (windows, closing time) |
| SVS admin guide | `/admin/guide?event=svs` (`#players`, `#plan`, `#share`) | `guide:svsAdmin.*` | `events/svs/admin/SvsAdminGuide.tsx` | `SvsPlayers` (cards, bars/chips, filters, table, exports, Add player, delete), `SvsRoundSettings` (battle start + duration, closing time), `SvsHeroes`, the planner `plan/*` (strategy, groups + minimums, leaders, disguise, split, pet buffs, named/other/extra joiners, double booking + Move here, quick add, hero picking, autosave + conflict banner, Share: create/copy/new link/turn off/real names) |
| Admin guide frame | `/admin/guide?event=<key>` | `guide:admin.title`, `guide:admin.backToDashboard`, `guide:basics.title/eventTab/hint` | `admin/AdminGuidePage.tsx` | The dashboard's "Admin Guide" button opens the CURRENT event's guide; the "<event> guide / Event Management basics" tabs sit at the top |

Links into the guides (`common:guideLinks.*`): `ministerLink` (Minister page), `playerLink` (Tyrant + SVS pages,
test ids `tyrant-guide-link`, `svs-guide-link`, `ministry-guide-link`), `wizardLink` (step 1 of each wizard, before the
FID lookup: `*-wizard-guide-link`), `planHelp` (shared plan view header -> `/svs/guide#plan`, `plan-help-link`; the
guide is static and shows nothing of a plan), `adminLink` (dashboard button `admin-guide-link`).

The SVS Players section is a plain list of keys (`table1..3` in `SvsAdminGuide.tsx`): to document a new Players
feature (e.g. "Add to rally"), add `table4`... in all 9 languages and to that list.

## Checklist for every change

1. Does the change alter anything a player or admin sees or does (a button, label, step, rule, default, limit)?
   Find the screen in the table above and read its guide section in English.
2. Update the guide text in **all 9 languages** in the same commit (en es fr de pl ko zh tr ar). Use the exact
   on-screen labels of each language (copy them from that language's locale file), plain words, short numbered steps.
   Never "Ministry" or the department word in any language (es Ministerio, fr Ministère, de Ministerium, pl
   Ministerstwo, tr Bakanlık, ko 부처, zh 部长/部门, ar وزارة): it is the Minister (person/position).
3. New guide or section: add it to the table above, to `e2e/test_guides.py` (route + test id) and, for a new page,
   to `pages.ts`/`App.tsx`; link it from the screen it explains.
4. No interpolation placeholders like `{{state}}` inside guide prose (only where the code passes the value).
5. `npm run build` (check-i18n), then `e2e/test_guides.py` (+ `test_i18n.py`, `test_mobile.py`) on a fresh stack.
   Look at the page on a phone in en and ar.
6. If you decide a change needs no guide update, say why in the commit message.
7. Add the player-facing line to the What's new page too (claude.md "Changelog rule").

## For claude.md (coordinator: paste next to the Changelog rule)

The docs agent could not write claude.md (protected file). Proposed text:

> **Documentation rule:** every section has a player guide and an admin guide in all 9 languages. Every user-visible
> change (a button, label, step, rule, default, limit) must update the guide that describes that screen, in all 9
> languages, in the same change; or the commit message says why no guide change is needed. Map and checklist:
> `docs/GUIDES.md`. Which guide covers which screen:
> - Minister player guide `/minister/guide` (`guide:player`): Minister page, application wizard, own assignments,
>   published schedule.
> - Frost Dragon Tyrant player guide `/tyrant/guide` (`guide:tyrantPlayer`): Tyrant page and wizard.
> - SVS player guide `/svs/guide` (`guide:svsPlayer`): SVS page, wizard, and the shared plan view
>   `/svs/plan/<token>` (`#plan`).
> - Event Management basics `/admin/guide?event=<key>&topic=basics` (`guide:basics`): login/logout, event switch,
>   rounds, Start new round, Rename, closing times, Add player, filters/exports, state number, hero generation,
>   links, rate limits.
> - Admin guides `/admin/guide?event=ministry|tyrant|svs` (`guide:admin`, `guide:tyrantAdmin`, `guide:svsAdmin`):
>   each event's admin tabs (SVS incl. the Battle plan and Share).
> `e2e/test_guides.py` renders every guide in all 9 languages (no raw keys, no "Ministry") and checks the links.

Version History entry:

> - **v2.2.1** (docs part, branch p7/docs): help guides for every section, in 9 languages. New player guides
>   `/tyrant/guide` (`TyrantGuide.tsx`) and `/svs/guide` (`SvsGuide.tsx`, incl. reading the shared plan and keeping
>   aliases secret); Minister player guide, the three admin guides and the new "Event Management basics"
>   (`admin/EventBasicsGuide.tsx`, `?topic=basics`) audited against the screens. Shared `shared/guide/`
>   (`GuideBits`, `GuideLink`, `useGuidesReady`). The `guide` namespace is a lazy chunk per language (`guide-<lang>`,
>   `i18n/index.ts` `loadGuides`, vite `manualChunks`): sign-up pages no longer download guide text (en locale
>   chunk ~15.6 -> ~13.5 KB gzip). Link texts moved to `common:guideLinks.*`. Links: Tyrant/SVS pages, step 1 of
>   each wizard, the shared plan view (-> `/svs/guide#plan`); Admin Guide opens the current event with the basics
>   tab on top. Changelog key `v221docs`. e2e `test_guides.py`; guides in `ui.PUBLIC_PAGES` and the phone pass.
