# Quick Start Guide

Get the Ministry Management System running in 5 minutes.

## Option 1: Docker Compose (Recommended)

```bash
# 1. Copy and edit the environment file
cp .env.example .env
nano .env  # Set your passwords

# 2. Start the application
docker compose up --build

# 3. Open http://localhost:8080
```

To stop: `Ctrl+C` or `docker compose down`

## Option 2: Bare Metal Development

### Backend (Terminal 1)

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env in backend/
cat > .env << 'EOF'
FLASK_ENV=development
SECRET_KEY=dev-secret-key
ADMIN_PASSWORD=admin123
MINISTER_PASSWORD=minister123
DATABASE_PATH=./data/minister.db
PORT=8080
EOF

mkdir -p data
python app.py
# Backend runs on http://localhost:8080
```

### Frontend (Terminal 2)

```bash
cd frontend
npm install
npm run dev
# Frontend runs on http://localhost:5173 (proxies API to :8080)
```

## Default Credentials

| Role | Password |
|------|----------|
| Admin | `admin123` |
| Minister | `minister123` |

**Change these before deploying to production!**

## First Steps

1. Open http://localhost:8080 (Docker) or http://localhost:5173 (dev)
2. Click **Submit New Application** and create a test player
   - Enter your FID and click **Load from WOS** to auto-fill name and avatar
   - Add your alliance tag (3 chars) and resource amounts
3. Click **Minister Administration** and log in with your password
4. Go to the **Assignments** tab and try **Auto Assign**
5. Drag and drop players between time slots
6. Click **Export to Excel** to download a multi-tab workbook

## Production Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for:
- Bare metal production setup with gunicorn, systemd, and nginx
- Docker deployment
- Google Cloud Run with persistent storage
- AWS, Azure, DigitalOcean, and PaaS platforms

## Troubleshooting

**Port already in use?**
```bash
lsof -i :8080  # Find what's using the port
# Change PORT in .env or docker-compose.yml
```

**Database not persisting?**
```bash
mkdir -p data
# For Docker: check that ./data is mounted as a volume
```

**Can't access admin panel?**
- Verify your password in `.env`
- Clear browser cache and try again

## Quick Commands

```bash
# Docker
docker compose up --build       # Start
docker compose down             # Stop
docker compose logs -f          # View logs
docker compose restart          # Restart

# Health check
curl http://localhost:8080/health

# Access database directly
sqlite3 data/minister.db
```

## Further Reading

- [User Guide](USER_GUIDE.md) - Player and admin workflows
- [Deployment Guide](DEPLOYMENT.md) - Production deployment options
- [Project Summary](PROJECT_SUMMARY.md) - Technical overview
