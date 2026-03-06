# Whiteout Survival - Ministry Management System

A web application for managing ministry assignments during State vs State (SVS) events in Whiteout Survival. Features a dark navy and gold themed interface, automatic point-based player assignment, drag-and-drop scheduling, and multi-language support.

## Features

- **Player Submission Form** - 3-step form for players to submit speedups, resources, and time preferences (FID required)
- **Player Updates** - Players update their submissions anytime using their FID
- **Admin Panel** - Password-protected interface with:
  - Player management (view, sort, search, edit, delete)
  - Auto-assignment based on point calculations
  - Drag-and-drop time slot management
  - Excel export
- **5 Languages** - English, Korean, Chinese, Turkish, Arabic (with RTL support)
- **Dark Theme** - Navy and gold themed UI
- **Dockerized** - Multi-stage Docker build for easy deployment

## Point Calculation System

### Monday - Construction
- 1 point per minute of construction or general speedups
- 30,000 points per refined fire crystal
- 2,000 points per fire crystal

### Tuesday - Research
- 1 point per minute of research or general speedups
- 1,000 points per fire crystal shard

### Thursday - Troop Training
- 1 point per day of troop training speedups

## Quick Start

### Option A: Docker Compose (easiest)

```bash
cp .env.example .env
# Edit .env with your passwords
docker compose up --build
# Open http://localhost:8080
```

### Option B: Local Development (bare metal)

**Terminal 1 - Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
# Create .env with DATABASE_PATH=./data/minister.db
python app.py
# Backend runs on http://localhost:8080
```

**Terminal 2 - Frontend (hot reload):**
```bash
cd frontend
npm install
npm run dev
# Frontend runs on http://localhost:5173 (proxies API to :8080)
```

### Option C: Production Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for Docker, Google Cloud Run, and other platform instructions.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 / Flask 3.0 / SQLite |
| Frontend | React 18 / TypeScript / Vite |
| Styling | Tailwind CSS |
| i18n | react-i18next (5 languages) |
| Drag & Drop | @dnd-kit |
| Production Server | gunicorn |
| Containerization | Docker (multi-stage build) |

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_ENV` | `development` or `production` | `production` |
| `SECRET_KEY` | Flask session secret | `dev-secret-key` |
| `ADMIN_PASSWORD` | Admin login password | `admin123` |
| `MINISTER_PASSWORD` | Minister login password | `minister123` |
| `DATABASE_PATH` | Path to SQLite database file | `/data/minister.db` |
| `PORT` | Server port | `8080` |

## Project Structure

```
minister_management/
├── backend/
│   ├── app.py              # Flask app + API routes
│   ├── database.py         # Schema, queries, point calculations
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/          # Home, PlayerForm, AdminDashboard, etc.
│   │   ├── components/     # LanguageSelector, admin/ subcomponents
│   │   └── i18n.ts         # All translations
│   ├── package.json
│   └── vite.config.ts
├── Dockerfile              # Multi-stage build (Node + Python)
├── docker-compose.yml      # Local development
├── .env.example            # Environment template
└── start.sh                # Docker quick-start script
```

## Documentation

- [Quick Start Guide](QUICK_START.md) - Get running in 5 minutes
- [Deployment Guide](DEPLOYMENT.md) - Bare metal, Docker, Cloud Run, and more
- [User Guide](USER_GUIDE.md) - For players and ministers
- [Project Summary](PROJECT_SUMMARY.md) - Technical overview

## License

Private - For Whiteout Survival State Management Only
