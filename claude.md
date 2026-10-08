# Claude Context: Ministry Management System

## Project Overview

This is a **Ministry Management System** for Whiteout Survival game, specifically for managing State vs State (SVS) ministry assignments. The application automates the process of assigning ministry positions to players based on their resources (speedups, fire crystals) and time availability.

## Tech Stack

**Backend:**
- Python 3.11+ with Flask 3.0
- SQLite database
- Location: `backend/`
- Entry point: `backend/app.py`
- Database logic: `backend/database.py`

**Frontend:**
- React 18 with TypeScript
- Vite (build tool)
- Tailwind CSS (styling)
- react-i18next (internationalization)
- @dnd-kit (drag and drop)
- Location: `frontend/`
- Entry point: `frontend/src/main.tsx`

**Deployment:**
- Docker + Docker Compose for local development
- Google Cloud Run for production
- SQLite database with persistent storage

## Project Structure

```
minister_management/
├── backend/
│   ├── app.py              # Main Flask application, API endpoints
│   ├── database.py         # Database schema, queries, point calculations
│   ├── requirements.txt    # Python dependencies
│   └── .env               # Environment variables (gitignored)
├── frontend/
│   ├── src/
│   │   ├── pages/         # Main page components
│   │   │   ├── Home.tsx              # Landing page
│   │   │   ├── PlayerForm.tsx        # 3-page submission form
│   │   │   ├── UpdateSubmission.tsx  # Update existing submission
│   │   │   ├── AdminLogin.tsx        # Admin authentication
│   │   │   └── AdminDashboard.tsx    # Admin main interface
│   │   ├── components/
│   │   │   ├── LanguageSelector.tsx  # Language switcher
│   │   │   └── admin/
│   │   │       ├── PlayerManagement.tsx      # CRUD table for players
│   │   │       └── AssignmentManagement.tsx  # Drag-drop assignments
│   │   ├── i18n.ts        # Translations (EN, ES, FR, DE, PL, KO, ZH, TR, AR)
│   │   ├── App.tsx        # Main app with routing
│   │   └── main.tsx       # Entry point
│   ├── package.json
│   └── vite.config.ts
├── data/                  # SQLite database (created at runtime)
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── Documentation files (.md)
```

## Important Business Logic

### Point Calculation System

Located in: `backend/database.py` → `calculate_points()` function

**Monday (Construction Day):**
```python
points = (construction_speedups_days * 1440) + (general_speedups_days * 1440)
         + (refined_fire_crystals * 30000) + (fire_crystals * 2000)
```

**Tuesday (Research Day):**
```python
points = (research_speedups_days * 1440) + (general_speedups_days * 1440)
         + (fire_crystal_shards * 1000)
```

**Thursday (Troop Training Day):**
```python
points = troop_training_speedups_days  # 1 point per day
```

Note: 1 day = 1440 minutes

### Auto-Assignment Algorithm

Located in: `backend/app.py` → `/api/admin/assignments/auto-assign`

1. Calculates points for all players for the selected day
2. Sorts players by points (descending)
3. Generates 30-minute time slots (00:00, 00:30, 01:00, etc.)
4. Matches player hourly preferences to 30-min slots
5. Assigns highest-point players first to their preferred slots
6. Tracks unassigned players

### Database Schema

**players:**
- `id`, `fid` (unique player identifier, REQUIRED)
- `game_name`, `alliance` (3-char tag, optional)
- Speedups: `construction_speedups_days`, `research_speedups_days`, `troop_training_speedups_days`, `general_speedups_days`
- Resources: `fire_crystals`, `refined_fire_crystals`, `fire_crystal_shards`
- Legacy WOS API data: `avatar_image` (URL), `stove_lv` (furnace level int), `stove_lv_content` (furnace icon URL)
  - Columns retained so pre-2026-08 rows still render their avatar/furnace icon; nothing populates them any more (see v1.3.0)
- Timestamps: `created_at`, `updated_at`

**time_preferences:**
- `id`, `player_id`, `time_slot`
- One row per time slot preference

**assignments:**
- `id`, `player_id`, `day`, `time_slot`, `position`, `is_assigned`
- Stores final ministry assignments per day

## Key Design Decisions

### 1. Player ID (FID) is Required
- Players MUST provide their own FID
- No auto-generation
- Used for updating submissions
- Validation enforced on both frontend and backend

### 2. Time Slot Granularity
- Players select preferences in 1-hour increments (00:00 to 23:00)
- System assigns in 30-minute increments (00:00, 00:30, etc.)
- Each hourly preference covers two 30-minute slots

### 3. Multi-Language Support
- 9 languages: English, Spanish, French, German, Polish, Korean, Chinese, Turkish, Arabic

### 5. Theming
- Colours resolve through CSS custom properties; palettes in `src/index.css`
- Never hardcode a hex or an off-palette Tailwind colour (e.g. `amber-500`) in a component
- Theme preference is client-side only (`localStorage`), never sent to the server
- RTL support for Arabic
- All UI text in `frontend/src/i18n.ts`
- Language state managed via react-i18next

### 4. Authentication
- Simple password-based auth for admin/minister
- Two passwords (same permissions): ADMIN_PASSWORD, MINISTER_PASSWORD
- Tokens stored in localStorage
- Not production-grade security - meant for trusted users

## Environment Variables

Located in: `.env` (created from `.env.example`)

Required variables:
```env
FLASK_ENV=development|production
SECRET_KEY=flask-secret-key
ADMIN_PASSWORD=admin-password
MINISTER_PASSWORD=minister-password
DATABASE_PATH=/path/to/minister.db
PORT=8080
```

## Running Locally

### Quick Start
```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
# Runs on http://localhost:8080

# Frontend (new terminal)
cd frontend
npm install
npm run dev
# Runs on http://localhost:5173
```

### With Docker
```bash
docker compose up --build
# Runs on http://localhost:8080
```

## API Endpoints

### Public Endpoints
- `POST /api/player/submit` - Submit/update player info
- `GET /api/player/<fid>` - Get player by FID
- `GET /health` - Health check

### Admin Endpoints (require Authorization header)
- `POST /api/admin/login` - Authenticate
- `GET /api/admin/players` - Get all players with calculated points
- `PUT /api/admin/player/<id>` - Update player
- `DELETE /api/admin/player/<id>` - Delete player
- `DELETE /api/admin/players/delete-all` - Delete all players
- `POST /api/admin/assignments/auto-assign` - Run auto-assignment
- `GET /api/admin/assignments/<day>` - Get assignments for day
- `POST /api/admin/assignments/update` - Save manual assignments
- `GET /api/admin/export` - Export all-day Excel workbook (Monday, Tuesday, Thursday tabs + Unassigned)

## Common Tasks

### Checking whether the WOS player lookup is available again

`backend/test_wos_api.py` probes the live gift-code API and reports whether a
player-lookup endpoint exists. Run `python backend/test_wos_api.py [FID] [STATE]`
(exit 0 = a usable lookup exists, 1 = not). See v1.3.0 for why the feature was
removed.

### Adding a New Language
1. Edit `frontend/src/i18n.ts`
2. Add new language code to resources
3. Add translation keys matching existing structure
4. Update `languages` array in `LanguageSelector.tsx`

### Modifying Point Calculation
1. Edit `backend/database.py` → `calculate_points()` function
2. Update documentation in README.md and USER_GUIDE.md
3. No database migration needed (calculated on-the-fly)

### Adding New Resource Types
1. Add column to players table in `backend/database.py` → `init_db()`
2. Add to form in `frontend/src/pages/PlayerForm.tsx`
3. Update point calculation if needed
4. Add translations to `frontend/src/i18n.ts`

### Changing Time Slot Granularity
1. Frontend input: `PlayerForm.tsx` → `timeSlots` array
2. Backend assignment: `app.py` → `/api/admin/assignments/auto-assign`
3. Admin display: `AssignmentManagement.tsx` → `generateTimeSlots()`

## Testing Guidelines

### Manual Testing Checklist
- [ ] Submit player with all fields
- [ ] Submit player without FID (should fail)
- [ ] Update existing player via FID
- [ ] Admin login with correct password
- [ ] Admin login with wrong password (should fail)
- [ ] View all players in admin table
- [ ] Sort players by different columns
- [ ] Edit player information
- [ ] Delete player
- [ ] Auto-assign for Monday
- [ ] Auto-assign for Tuesday
- [ ] Auto-assign for Thursday
- [ ] Drag-drop player between time slots
- [ ] Export to Excel
- [ ] Switch languages
- [ ] Test Arabic RTL layout

### Edge Cases to Consider
- Player with no time preferences
- Player with 0 points
- Multiple players wanting same time slot
- Very large numbers of speedups
- Empty database state
- Browser refresh during form submission

## Known Limitations

1. **Authentication**: Simple password-based, not production-grade
2. **SQLite Limitations**: Not ideal for high concurrency; use single gunicorn worker
3. **No Email Notifications**: Players must manually check assignments
4. **Single State Only**: No multi-state/multi-organization support
5. **No Audit Log**: Changes aren't tracked historically
6. **Browser Storage**: Admin tokens in localStorage (not secure for production)

## Development Workflow

### Making Changes
1. Backend changes: Flask auto-reloads in development mode
2. Frontend changes: Vite hot-reloads automatically
3. Database changes: Delete `data/minister.db` to recreate schema
4. Translation changes: Edit `i18n.ts`, Vite hot-reloads

### Before Committing
- Update relevant documentation (.md files)
- Test both English and one RTL language (Arabic)
- Verify both admin and player flows
- Check mobile responsiveness

### Deploying to Cloud Run
Production is project `viscount-wos-tools`, region `us-central1`, service **`ministry-management`**
(with a "y" — `minister-management` is only the container image name and fails as a service name),
served at `ministry.hunterisadonkey.com`. Deploy from source:

```bash
gcloud run deploy ministry-management --source . --region us-central1
```

This rebuilds the frontend fresh via the multi-stage Dockerfile and preserves existing
config (secrets, GCS FUSE volume, min-instances). The SQLite DB lives on the GCS bucket
`viscount-wos-tools-ministry-data` and survives redeploys — spot-check player data after
any infra event.

See `DEPLOYMENT.md` for full instructions covering bare metal, Docker, Cloud Run, and other platforms.

## Deployment Lessons Learned (Cloud Run + GCS FUSE)

These were discovered during production deployment and are critical knowledge:

### GCS FUSE Requires journal_mode=DELETE
SQLite WAL mode creates `-shm` and `-wal` sidecar files. GCS FUSE cannot handle out-of-order writes to these files, producing `BufferedWriteHandler.OutOfOrderError`. The fix is `PRAGMA journal_mode=DELETE` (set in `database.py` → `init_db()`). If you see this error, delete the database from the GCS bucket and let it recreate.

### Cloud Run Needs min-instances=1
Without `--min-instances 1`, Cloud Run aggressively scales to zero. On cold start, the container crash-loops (starts, runs ~90 seconds, gets SIGTERM, restarts). This produces 429 "Rate Exceeded" errors for users. Setting min-instances=1 keeps one warm instance and prevents this.

### Single Gunicorn Worker for SQLite
Multiple gunicorn workers cause concurrent SQLite writes. On GCS FUSE this produces `OutOfOrderError` on journal files. On local filesystems it can cause database lock errors. The Dockerfile uses `--workers 1 --threads 2` which is safe.

### Cloud Run gen2 Required
GCS FUSE volume mounts require `--execution-environment gen2`. Gen1 does not support volume mounts.

## Troubleshooting

### Backend won't start
- Check `.env` file exists and has DATABASE_PATH
- Verify virtual environment is activated
- Check port 8080 is not in use: `lsof -i :8080`

### Frontend won't start
- Clear npm cache if permission errors
- Check node version (need 18+)
- Port 5173 conflict: change in `vite.config.ts`

### Database errors
- Path doesn't exist: Check DATABASE_PATH in .env
- Permission denied: Ensure write access to data directory
- Locked database: Close other connections

### Drag-drop not working
- Check @dnd-kit packages installed
- Verify browser JavaScript enabled
- Check console for errors

## File Conventions

### Code Style
- **Backend**: Python PEP 8, 4-space indentation
- **Frontend**: TypeScript, 2-space indentation, functional components
- **CSS**: Tailwind utility classes, avoid custom CSS

### Naming Conventions
- **Components**: PascalCase (e.g., `PlayerForm.tsx`)
- **Functions**: camelCase (e.g., `handleSubmit()`)
- **API routes**: kebab-case (e.g., `/api/admin/auto-assign`)
- **Database**: snake_case (e.g., `construction_speedups_days`)

### File Organization
- Pages: Top-level routes (`pages/`)
- Components: Reusable UI (`components/`)
- Admin-specific: In `components/admin/`
- Types: Inline in TypeScript files
- Translations: Centralized in `i18n.ts`

## Security Considerations

⚠️ **This application is designed for trusted users within a game state**

### Current Security
- Password-based admin access
- CORS enabled for frontend
- SQL injection prevention (parameterized queries)
- Input validation

### NOT Included
- Rate limiting
- CSRF protection
- XSS sanitization (React provides basic protection)
- Encryption at rest
- Session management
- Password hashing for admin passwords
- Audit logging

### For Production
- Use Google Secret Manager for passwords
- Implement proper authentication (OAuth, JWT)
- Add rate limiting
- Enable HTTPS only
- Implement audit logging
- Add data backup strategy

## Support & Resources

- **Main Docs**: README.md
- **Quick Start**: QUICK_START.md
- **User Guide**: USER_GUIDE.md
- **Deployment**: DEPLOYMENT.md
- **Technical Overview**: PROJECT_SUMMARY.md
- **This File**: claude.md (AI assistant context)

## Version History

**Changelog rule:** every user-visible feature or fix gets a short, player-friendly line on the
What's new page (`/changelog`) in the same change. The text goes in the `changelog` namespace for
all 9 languages, and `RELEASES` in `frontend/src/shell/Changelog.tsx` must be updated. Add new
items to the latest release until it ships; start a new release block once a version is deployed.
Record the developer-level detail here as well.

- **v2.0.0** (October 2026): State event hub (wos-events). Deployed as Cloud Run service `wos-events` at hunterisadonkey.com.
  Details in `docs/SPEC.md`.
  - Event registry: Minister (key `ministry`, shown as "Minister"), Frost Dragon Tyrant, SVS and
    Tundra Arms League placeholders. Shared per-FID profiles; one application per FID per round.
  - Frost Dragon Tyrant wizard and admin: per-troop camp FC level (FC1-FC10) and tier, no main
    furnace. Admin filters on almost every column, clickable summary chips, URL filter state,
    filtered exports, a joiner-strength sort.
  - The Event Management admin shell covers every event, with per-event guides.
  - Phone-first pass: compact header dropdowns; language auto-detected from the browser language;
    the timezone is auto-detected too. Sticky wizard navigation, 44px tap targets, tap-to-move on
    the assignment board.
  - Furnace dropdown: FC10..FC1 then 30..1.
  - Security: real admin tokens replace v1.4's fixed 'admin-token'. Production refuses default
    passwords. Login rate limit, formula-injection-safe exports, closed rounds read-only on the server.
  - The MCP server (`mcp/`) sits in front of the HTTP API.
  - Migration from v1.4 is a separate step (`python -m core.migrate`); see `docs/DEPLOY-CUTOVER.md`.

- **v1.4.0** (September 2026): Themes, accessibility, changelog
  - **Colour themes**: three user-selectable schemes — `ministry-dark` (default, unchanged),
    `reading` (warm light ground, dark non-black text, bronze accent) and `low-glare`
    (dark with the gold desaturated). Chosen in the header; stored in `localStorage`
    under `preferred_theme`; applied by stamping `data-theme` on `<html>`.
    The default stamps nothing, so an unknown or missing value falls back to the
    original scheme. See `frontend/src/utils/theme.ts` and `components/ThemeSelector.tsx`.
  - **Theme token layer**: `tailwind.config.js` colours now resolve through CSS custom
    properties (`rgb(var(--c-*) / <alpha-value>)`), with the palettes defined in
    `src/index.css`. The `<alpha-value>` form is required so tinted utilities like
    `bg-accent/20` stay correct in every theme. Adding a theme = one more
    `:root[data-theme='...']` block; no component changes.
  - Added `heat.low` / `heat.mid` / `heat.high` tokens. The demand heat map previously
    wrote 12 inline `rgba()` values that no theme could override, and the guide's legend
    swatches were hand-matched to them in a separate file; both now share the tokens.
    Note: heat classes must be written as **complete literal strings** in source
    (`'bg-heat-low/25 border-heat-low/60'`) or Tailwind will not generate them.
  - **Contrast fixes**: `danger` raised to #f0685a (was #e74c3c, which measured 3.98:1 on
    cards and failed AA for 17 error messages); `theme-border` raised to #63768a (was
    #2d3e4f at 1.62:1, below the 3:1 non-text threshold). Every text pair in all three
    themes now clears AA, and borders clear 3:1.
  - `prefers-reduced-motion` honoured: the blanket `* { transition }` rule and the hover
    lifts are disabled when the OS asks for less motion.
  - **Changelog page** at `/changelog`, linked from the home page. Entries live in the
    `changelog` i18n section; `RELEASES` in `pages/Changelog.tsx` maps them to keys.
  - Speedup and fire crystal field labels reworded to "Number of days to be used for X"
    and "Number of X to be used", after players missed that General speedups had to be
    folded into the Construction and Research totals.
  - Schedule days now sort by weekday rather than alphabetically (see `sort_days_by_week`
    in `app.py` and `frontend/src/utils/days.ts`).

- **v1.3.0** (August 2026): Removed "Load from WOS"
  - Century Games reworked the Gift Code Center in July 2026: it no longer logs the
    player in behind a captcha, it just takes a Player ID + State and redeems in one POST.
    `POST /api/player` and `POST /api/captcha` were deleted from
    `wos-giftcode-api.centurygame.com` as part of that change (both now 404 on every
    method; `/api/gift_code` and `/api/gift_code_config` still answer, so the API itself
    is up). Request signing is unchanged — the secret `tB87#kPtkxqOS2` and the
    sort-keys/urlencode-values/`md5(canonical + secret)` scheme still validate.
  - No public endpoint resolves a FID into nickname / avatar / furnace level any more,
    so the button could not be repaired and was removed. Players type their own game name.
  - Removed: `POST /api/player/wos-lookup`, the "Load from WOS" button and avatar
    previews in `PlayerForm.tsx`, the `loadFromWOS` / `enterFidFirst` / `wosLookupFailed` /
    `playerGuide.step1Wos` translation keys, and `WOS_API_SECRET`
  - Kept: the `avatar_image`, `stove_lv`, `stove_lv_content` DB columns and the admin/
    assignment UI that renders them, so players who submitted before this change keep
    their avatar and furnace icon
  - Added `backend/test_wos_api.py` — re-run it if Century Games ever restores a lookup endpoint

- **v1.2.0** (July 2026): Time Slot Schemes & Scheduling Fixes
  - **Time slot scheme** setting (`exact_alignment` default vs `max_slots`), selectable in the Settings tab
    - `exact_alignment`: hour-aligned slots (00:00, 00:30 … 23:30, 48/day)
    - `max_slots`: legacy 23:50-boundary grid (23:50, 00:20 … 23:50+, 49/day)
    - Slot generation lives in `generate_time_slots()` / `matching_slots_for_pref()` (`app.py`) and `generateAssignmentSlots(scheme)` (`timezone.ts`)
    - Switching schemes remaps existing placements via `remap_assignments_between_schemes()` (nearest slot by wall-clock minutes; collisions → higher points wins)
  - **Shared 23:50 boundary slot** (max_slots + calendar-adjacent active days: Mon↔Tue or Thu↔Fri): one player holds the same real time on both days, chosen by highest COMBINED score. See `get_shared_slot_link()`, `compute_shared_winner()`, `sync_shared_boundary()`. Shown on both days in the UI and synced on manual edit.
  - **Fixed**: unassigned players now returned by `GET /api/admin/assignments/<day>` (shape is now `{assignments, unassigned}`) so they show on first load, not only after re-running auto-assign
  - Migration: installs with existing assignment data are pinned to `max_slots` to preserve behavior; fresh installs default to `exact_alignment`
  - New API endpoints: `GET /api/settings/time-slot-scheme`, `PUT /api/admin/settings/time-slot-scheme`
  - Removed LootBar affiliate integration (no longer active for Whiteout Survival)

- **v1.1.0** (March 2026): WOS API Integration & Enhancements
  - "Load from WOS" button auto-fills player name, avatar, and furnace level from FID
  - Alliance tag field (3 chars max, displayed as `[TAG]` next to player names)
  - Player avatars and furnace level icons on assignment cards and player table
  - Multi-day Excel export (Monday/Tuesday/Thursday tabs + Unassigned tab)
  - Alliance as separate column in Excel export
  - "Remove All Players" button with confirmation
  - New API endpoints: `POST /api/player/wos-lookup`, `DELETE /api/admin/players/delete-all`
  - New DB columns: `avatar_image`, `stove_lv`, `stove_lv_content`, `alliance`

- **v1.0.0** (March 2026): Initial release
  - 3-page player submission form
  - Admin panel with auto-assignment
  - Drag-and-drop manual assignment
  - 5-language support
  - Excel export
  - FID now required (no auto-generation)

---

**Last Updated**: September 11, 2026
**Maintained By**: State Technical Administrator
**Purpose**: Ministry assignment automation for Whiteout Survival SVS events
