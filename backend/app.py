from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import os
import hashlib
import time as time_module
import requests as http_requests
from dotenv import load_dotenv
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from io import BytesIO

# Load environment variables FIRST
load_dotenv()

from database import (
    init_db, get_all_players, get_player_by_fid,
    save_player, delete_player, calculate_points, get_db
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

app = Flask(__name__, static_folder=None)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
CORS(app)

# Admin credentials
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
MINISTER_PASSWORD = os.getenv('MINISTER_PASSWORD', 'minister123')

# Initialize database (registers teardown handler)
init_db(app)

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

# Serve React app - handles SPA routing for all non-API paths
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path and os.path.exists(os.path.join(STATIC_DIR, path)):
        return send_from_directory(STATIC_DIR, path)
    return send_from_directory(STATIC_DIR, 'index.html')

# API Routes

@app.route('/api/player/submit', methods=['POST'])
def submit_player():
    """Submit or update player information."""
    try:
        data = request.json

        # Validate required fields
        required_fields = ['fid', 'game_name']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Extract time slots
        time_slots = data.pop('time_slots', [])

        # Set defaults for numeric fields
        numeric_fields = [
            'construction_speedups_days', 'research_speedups_days',
            'troop_training_speedups_days', 'general_speedups_days',
            'fire_crystals', 'refined_fire_crystals', 'fire_crystal_shards'
        ]
        for field in numeric_fields:
            if field not in data:
                data[field] = 0
            else:
                data[field] = float(data[field]) if '.' in str(data[field]) or 'speedups' in field else int(data[field])

        # Save player
        player_id = save_player(data, time_slots)

        return jsonify({
            'success': True,
            'player_id': player_id,
            'message': 'Player information saved successfully'
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/player/<fid>', methods=['GET'])
def get_player(fid):
    """Get player information by FID."""
    try:
        player = get_player_by_fid(fid)
        if player:
            return jsonify(player), 200
        return jsonify({'error': 'Player not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/player/wos-lookup', methods=['POST'])
def wos_lookup():
    """Look up player info from the WOS game API."""
    try:
        data = request.json
        fid = data.get('fid', '').strip()

        if not fid:
            return jsonify({'error': 'FID is required'}), 400

        # Build signed request for WOS API
        secret = 'tB87#kPtkxqOS2'
        ts = str(int(time_module.time() * 1e9))
        form_data = f'fid={fid}&time={ts}'
        sign = hashlib.md5((form_data + secret).encode()).hexdigest()
        body = f'sign={sign}&{form_data}'

        response = http_requests.post(
            'https://wos-giftcode-api.centurygame.com/api/player',
            data=body,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Origin': 'https://wos-giftcode.centurygame.com',
                'Referer': 'https://wos-giftcode.centurygame.com/',
            },
            timeout=10
        )

        result = response.json()

        if result.get('code') != 0:
            return jsonify({'error': 'Player not found in WOS'}), 404

        wos_data = result['data']
        return jsonify({
            'success': True,
            'fid': str(wos_data['fid']),
            'nickname': wos_data.get('nickname', ''),
            'kid': wos_data.get('kid'),
            'stove_lv': wos_data.get('stove_lv'),
            'stove_lv_content': wos_data.get('stove_lv_content', ''),
            'avatar_image': wos_data.get('avatar_image', ''),
        }), 200

    except http_requests.exceptions.Timeout:
        return jsonify({'error': 'WOS API timed out'}), 504
    except http_requests.exceptions.RequestException as e:
        return jsonify({'error': f'Failed to reach WOS API: {str(e)}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    """Authenticate admin or minister user."""
    try:
        data = request.json
        password = data.get('password', '')

        if password == ADMIN_PASSWORD:
            return jsonify({
                'success': True,
                'role': 'admin',
                'token': 'admin-token'
            }), 200
        elif password == MINISTER_PASSWORD:
            return jsonify({
                'success': True,
                'role': 'minister',
                'token': 'minister-token'
            }), 200
        else:
            return jsonify({'error': 'Invalid password'}), 401

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/players', methods=['GET'])
def get_players():
    """Get all players with calculated points."""
    try:
        # Simple auth check
        auth_header = request.headers.get('Authorization')
        if not auth_header or 'token' not in auth_header:
            return jsonify({'error': 'Unauthorized'}), 401

        players = get_all_players()

        # Add calculated points for each day
        for player in players:
            player['monday_points'] = calculate_points(player, 'monday')
            player['tuesday_points'] = calculate_points(player, 'tuesday')
            player['thursday_points'] = calculate_points(player, 'thursday')

        return jsonify(players), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/player/<int:player_id>', methods=['PUT'])
def update_player(player_id):
    """Update player information."""
    try:
        # Simple auth check
        auth_header = request.headers.get('Authorization')
        if not auth_header or 'token' not in auth_header:
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.json
        time_slots = data.pop('time_slots', [])

        # Update player
        save_player(data, time_slots)

        return jsonify({'success': True, 'message': 'Player updated'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/player/<int:player_id>', methods=['DELETE'])
def remove_player(player_id):
    """Delete a player."""
    try:
        # Simple auth check
        auth_header = request.headers.get('Authorization')
        if not auth_header or 'token' not in auth_header:
            return jsonify({'error': 'Unauthorized'}), 401

        delete_player(player_id)
        return jsonify({'success': True, 'message': 'Player deleted'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/assignments/auto-assign', methods=['POST'])
def auto_assign():
    """Auto-assign players to time slots based on points."""
    try:
        # Simple auth check
        auth_header = request.headers.get('Authorization')
        if not auth_header or 'token' not in auth_header:
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.json
        day = data.get('day', '').lower()

        if day not in ['monday', 'tuesday', 'thursday']:
            return jsonify({'error': 'Invalid day'}), 400

        players = get_all_players()

        # Calculate points for this day
        for player in players:
            player['points'] = calculate_points(player, day)

        # Sort by points (descending)
        players.sort(key=lambda p: p['points'], reverse=True)

        # Generate 30-minute time slots (00:00-23:30)
        time_slots = []
        for hour in range(24):
            time_slots.append(f"{hour:02d}:00")
            time_slots.append(f"{hour:02d}:30")

        # Assignment logic
        assignments = {slot: [] for slot in time_slots}
        unassigned = []

        for player in players:
            player_time_prefs = set(player.get('time_slots', []))

            # Find matching 30-min slots for player's hourly preferences
            matching_slots = []
            for pref in player_time_prefs:
                # Convert HH:00 preference to both HH:00 and HH:30 slots
                if ':' in pref:
                    hour = pref.split(':')[0]
                    matching_slots.append(f"{hour}:00")
                    matching_slots.append(f"{hour}:30")

            assigned = False
            for slot in matching_slots:
                if slot in assignments and len(assignments[slot]) == 0:
                    assignments[slot].append({
                        'id': player['id'],
                        'player_id': player['id'],
                        'fid': player['fid'],
                        'game_name': player['game_name'],
                        'points': player['points'],
                        'avatar_image': player.get('avatar_image', ''),
                        'stove_lv': player.get('stove_lv'),
                        'stove_lv_content': player.get('stove_lv_content', ''),
                    })
                    assigned = True
                    break

            if not assigned:
                unassigned.append({
                    'id': player['id'],
                    'player_id': player['id'],
                    'fid': player['fid'],
                    'game_name': player['game_name'],
                    'points': player['points'],
                    'preferred_times': list(player_time_prefs),
                    'avatar_image': player.get('avatar_image', ''),
                    'stove_lv': player.get('stove_lv'),
                    'stove_lv_content': player.get('stove_lv_content', ''),
                })

        # Clear existing assignments for this day
        db = get_db()
        cursor = db.cursor()
        cursor.execute('DELETE FROM assignments WHERE day = ?', (day,))

        # Save new assignments
        for time_slot, slot_players in assignments.items():
            for position, player in enumerate(slot_players):
                cursor.execute('''
                    INSERT INTO assignments (player_id, day, time_slot, position, is_assigned)
                    VALUES (?, ?, ?, ?, 1)
                ''', (player['id'], day, time_slot, position))

        db.commit()

        return jsonify({
            'success': True,
            'assignments': assignments,
            'unassigned': unassigned
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/assignments/<day>', methods=['GET'])
def get_assignments(day):
    """Get assignments for a specific day."""
    try:
        # Simple auth check
        auth_header = request.headers.get('Authorization')
        if not auth_header or 'token' not in auth_header:
            return jsonify({'error': 'Unauthorized'}), 401

        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            SELECT
                a.id, a.time_slot, a.position, a.is_assigned,
                p.id as player_id, p.fid, p.game_name,
                p.construction_speedups_days, p.research_speedups_days,
                p.troop_training_speedups_days, p.general_speedups_days,
                p.fire_crystals, p.refined_fire_crystals, p.fire_crystal_shards
            FROM assignments a
            JOIN players p ON a.player_id = p.id
            WHERE a.day = ?
            ORDER BY a.time_slot, a.position
        ''', (day.lower(),))

        rows = cursor.fetchall()
        assignments = {}
        for row in rows:
            slot = row['time_slot']
            if slot not in assignments:
                assignments[slot] = []
            row_dict = dict(row)
            row_dict['points'] = calculate_points(row_dict, day.lower())
            assignments[slot].append(row_dict)

        return jsonify(assignments), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/assignments/update', methods=['POST'])
def update_assignments():
    """Update assignments after drag-and-drop."""
    try:
        # Simple auth check
        auth_header = request.headers.get('Authorization')
        if not auth_header or 'token' not in auth_header:
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.json
        day = data.get('day')
        assignments = data.get('assignments', {})

        db = get_db()
        cursor = db.cursor()

        # Clear existing assignments
        cursor.execute('DELETE FROM assignments WHERE day = ?', (day,))

        # Save new assignments (enforce max 1 player per slot)
        for time_slot, slot_players in assignments.items():
            if slot_players:
                player = slot_players[0]  # Only take first player per slot
                cursor.execute('''
                    INSERT INTO assignments (player_id, day, time_slot, position, is_assigned)
                    VALUES (?, ?, ?, ?, ?)
                ''', (player['player_id'], day, time_slot, 0, player.get('is_assigned', True)))

        db.commit()

        return jsonify({'success': True}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/export', methods=['GET'])
def export_assignments():
    """Export assignments for all days to a single Excel workbook."""
    try:
        # Simple auth check
        auth_header = request.headers.get('Authorization')
        if not auth_header or 'token' not in auth_header:
            return jsonify({'error': 'Unauthorized'}), 401

        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # Remove default sheet

        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        separator_fill = PatternFill(start_color="F4B942", end_color="F4B942", fill_type="solid")
        separator_font = Font(bold=True, color="000000")

        headers = [
            'Time Slot', 'FID', 'Game Name',
            'Construction (days)', 'Research (days)',
            'Troop Training (days)', 'General (days)',
            'Fire Crystals', 'Refined Fire Crystals',
            'Crystal Shards', 'Points'
        ]

        col_widths = [15, 15, 25, 18, 15, 20, 15, 13, 18, 14, 12]

        days = [
            ('monday', 'Monday - Construction'),
            ('tuesday', 'Tuesday - Research'),
            ('thursday', 'Thursday - Troop Training'),
        ]

        db = get_db()
        cursor = db.cursor()

        for day_key, day_title in days:
            ws = wb.create_sheet(title=day_title)
            ws.append(headers)

            # Style headers
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal='center')

            # Get assigned players
            cursor.execute('''
                SELECT a.time_slot, p.*
                FROM assignments a
                JOIN players p ON a.player_id = p.id
                WHERE a.day = ? AND a.is_assigned = 1
                ORDER BY a.time_slot, a.position
            ''', (day_key,))

            assigned_rows = cursor.fetchall()
            assigned_player_ids = set()

            for row in assigned_rows:
                player = dict(row)
                assigned_player_ids.add(player['id'])
                points = calculate_points(player, day_key)
                ws.append([
                    row['time_slot'],
                    player['fid'],
                    player['game_name'],
                    player['construction_speedups_days'],
                    player['research_speedups_days'],
                    player['troop_training_speedups_days'],
                    player['general_speedups_days'],
                    player['fire_crystals'],
                    player['refined_fire_crystals'],
                    player['fire_crystal_shards'],
                    points,
                ])

            # Get all players to find unassigned ones
            cursor.execute('SELECT * FROM players ORDER BY id')
            all_players = [dict(r) for r in cursor.fetchall()]
            unassigned = [p for p in all_players if p['id'] not in assigned_player_ids]

            # Sort unassigned by points descending
            for p in unassigned:
                p['_points'] = calculate_points(p, day_key)
            unassigned.sort(key=lambda p: p['_points'], reverse=True)

            if unassigned:
                # Separator row
                sep_row_num = ws.max_row + 2  # skip a blank row
                ws.append([])  # blank row
                ws.append(['UNASSIGNED PLAYERS'] + [''] * (len(headers) - 1))
                for cell in ws[sep_row_num]:
                    cell.fill = separator_fill
                    cell.font = separator_font

                for player in unassigned:
                    ws.append([
                        'Unassigned',
                        player['fid'],
                        player['game_name'],
                        player['construction_speedups_days'],
                        player['research_speedups_days'],
                        player['troop_training_speedups_days'],
                        player['general_speedups_days'],
                        player['fire_crystals'],
                        player['refined_fire_crystals'],
                        player['fire_crystal_shards'],
                        player['_points'],
                    ])

            # Set column widths
            for i, width in enumerate(col_widths):
                ws.column_dimensions[chr(65 + i)].width = width

        # Save to BytesIO
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f'ministry_assignments_{datetime.now().strftime("%Y%m%d")}.xlsx'
        return Response(
            output.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/players/delete-all', methods=['DELETE'])
def delete_all_players():
    """Delete all players and their assignments."""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or 'token' not in auth_header:
            return jsonify({'error': 'Unauthorized'}), 401

        db = get_db()
        cursor = db.cursor()
        cursor.execute('DELETE FROM assignments')
        cursor.execute('DELETE FROM time_preferences')
        cursor.execute('DELETE FROM players')
        db.commit()

        return jsonify({'success': True, 'message': 'All players deleted'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_ENV') == 'development')
