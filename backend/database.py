import sqlite3
import os
from flask import g

# Database path - set via DATABASE_PATH env var
DB_PATH = os.environ.get('DATABASE_PATH', '/data/minister.db')


def get_db():
    """Get database connection using Flask g context (matches tyrant-poll pattern)."""
    if 'db' not in g:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(exc=None):
    """Close database connection on teardown."""
    db = g.pop('db', None)
    if db:
        db.close()


def init_db(app):
    """Initialize the database with required tables."""
    app.teardown_appcontext(close_db)

    with app.app_context():
        db = get_db()
        # Force DELETE journal mode - WAL mode creates -shm/-wal files
        # that are incompatible with GCS FUSE (out-of-order writes)
        db.execute('PRAGMA journal_mode=DELETE')
        cursor = db.cursor()

        # Players table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fid TEXT UNIQUE NOT NULL,
                game_name TEXT NOT NULL,
                construction_speedups_days REAL DEFAULT 0,
                research_speedups_days REAL DEFAULT 0,
                troop_training_speedups_days REAL DEFAULT 0,
                general_speedups_days REAL DEFAULT 0,
                fire_crystals INTEGER DEFAULT 0,
                refined_fire_crystals INTEGER DEFAULT 0,
                fire_crystal_shards INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Time preferences table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS time_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                time_slot TEXT NOT NULL,
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
                UNIQUE(player_id, time_slot)
            )
        ''')

        # Assignments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                day TEXT NOT NULL,
                time_slot TEXT NOT NULL,
                position INTEGER DEFAULT 0,
                is_assigned BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
                UNIQUE(day, time_slot, position)
            )
        ''')

        # Admin users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_players_fid ON players(fid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_time_prefs_player ON time_preferences(player_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_assignments_day ON assignments(day)')

        db.commit()

        # Schema migrations (idempotent - safe to re-run)
        migrations = [
            'ALTER TABLE players ADD COLUMN avatar_image TEXT DEFAULT NULL',
            'ALTER TABLE players ADD COLUMN stove_lv INTEGER DEFAULT NULL',
            'ALTER TABLE players ADD COLUMN stove_lv_content TEXT DEFAULT NULL',
            'ALTER TABLE players ADD COLUMN alliance TEXT DEFAULT NULL',
        ]
        for migration in migrations:
            try:
                cursor.execute(migration)
            except Exception:
                pass  # Column already exists
        db.commit()


def calculate_points(player, day):
    """
    Calculate points for a player based on the day type.

    Args:
        player: dict with player data
        day: 'monday' (construction), 'tuesday' (research), or 'thursday' (troop)

    Returns:
        int: calculated points
    """
    construction_mins = player['construction_speedups_days'] * 24 * 60
    research_mins = player['research_speedups_days'] * 24 * 60
    troop_days = player['troop_training_speedups_days']
    general_mins = player['general_speedups_days'] * 24 * 60

    if day.lower() == 'monday':
        # Construction: 1 pt/min construction+general, 30k/refined crystal, 2k/fire crystal
        points = (construction_mins + general_mins)
        points += player['refined_fire_crystals'] * 30000
        points += player['fire_crystals'] * 2000
        return int(points)

    elif day.lower() == 'tuesday':
        # Research: 1 pt/min research+general, 1k/crystal shard
        points = (research_mins + general_mins)
        points += player['fire_crystal_shards'] * 1000
        return int(points)

    elif day.lower() == 'thursday':
        # Troop: 1 pt/day troop training
        return int(troop_days)

    return 0


def get_all_players():
    """Get all players with their time preferences."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        SELECT
            p.*,
            GROUP_CONCAT(tp.time_slot) as time_slots
        FROM players p
        LEFT JOIN time_preferences tp ON p.id = tp.player_id
        GROUP BY p.id
        ORDER BY p.created_at DESC
    ''')
    players = []
    for row in cursor.fetchall():
        player = dict(row)
        player['time_slots'] = player['time_slots'].split(',') if player['time_slots'] else []
        players.append(player)
    return players


def get_player_by_fid(fid):
    """Get a player by their FID."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM players WHERE fid = ?', (fid,))
    row = cursor.fetchone()
    if row:
        player = dict(row)
        # Get time preferences
        cursor.execute('SELECT time_slot FROM time_preferences WHERE player_id = ?', (player['id'],))
        player['time_slots'] = [r['time_slot'] for r in cursor.fetchall()]
        return player
    return None


def save_player(data, time_slots):
    """Save or update a player and their time preferences."""
    db = get_db()
    cursor = db.cursor()

    # Check if player exists
    cursor.execute('SELECT id FROM players WHERE fid = ?', (data['fid'],))
    existing = cursor.fetchone()

    if existing:
        # Update existing player
        player_id = existing['id']
        cursor.execute('''
            UPDATE players SET
                game_name = ?,
                construction_speedups_days = ?,
                research_speedups_days = ?,
                troop_training_speedups_days = ?,
                general_speedups_days = ?,
                fire_crystals = ?,
                refined_fire_crystals = ?,
                fire_crystal_shards = ?,
                avatar_image = ?,
                stove_lv = ?,
                stove_lv_content = ?,
                alliance = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE fid = ?
        ''', (
            data['game_name'],
            data['construction_speedups_days'],
            data['research_speedups_days'],
            data['troop_training_speedups_days'],
            data['general_speedups_days'],
            data['fire_crystals'],
            data['refined_fire_crystals'],
            data['fire_crystal_shards'],
            data.get('avatar_image'),
            data.get('stove_lv'),
            data.get('stove_lv_content'),
            data.get('alliance'),
            data['fid']
        ))

        # Delete old time preferences
        cursor.execute('DELETE FROM time_preferences WHERE player_id = ?', (player_id,))
    else:
        # Insert new player
        cursor.execute('''
            INSERT INTO players (
                fid, game_name, construction_speedups_days, research_speedups_days,
                troop_training_speedups_days, general_speedups_days, fire_crystals,
                refined_fire_crystals, fire_crystal_shards,
                avatar_image, stove_lv, stove_lv_content, alliance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['fid'],
            data['game_name'],
            data['construction_speedups_days'],
            data['research_speedups_days'],
            data['troop_training_speedups_days'],
            data['general_speedups_days'],
            data['fire_crystals'],
            data['refined_fire_crystals'],
            data['fire_crystal_shards'],
            data.get('avatar_image'),
            data.get('stove_lv'),
            data.get('stove_lv_content'),
            data.get('alliance')
        ))
        player_id = cursor.lastrowid

    # Insert time preferences
    for time_slot in time_slots:
        cursor.execute('''
            INSERT INTO time_preferences (player_id, time_slot)
            VALUES (?, ?)
        ''', (player_id, time_slot))

    db.commit()
    return player_id


def delete_player(player_id):
    """Delete a player and all related data."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('DELETE FROM players WHERE id = ?', (player_id,))
    db.commit()
