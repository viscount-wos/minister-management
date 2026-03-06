from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import os
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
                        'points': player['points']
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
                    'preferred_times': list(player_time_prefs)
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

@app.route('/api/admin/export/<day>', methods=['GET'])
def export_assignments(day):
    """Export assignments to Excel."""
    try:
        # Simple auth check
        auth_header = request.headers.get('Authorization')
        if not auth_header or 'token' not in auth_header:
            return jsonify({'error': 'Unauthorized'}), 401

        # Create workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"{day.capitalize()} Assignments"

        # Headers
        headers = ['Time Slot', 'Player ID (FID)', 'Game Name', 'Points']
        ws.append(headers)

        # Style headers
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')

        # Get assignments
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            SELECT
                a.time_slot,
                p.fid,
                p.game_name,
                p.*
            FROM assignments a
            JOIN players p ON a.player_id = p.id
            WHERE a.day = ? AND a.is_assigned = 1
            ORDER BY a.time_slot, a.position
        ''', (day.lower(),))

        rows = cursor.fetchall()
        for row in rows:
            player = dict(row)
            points = calculate_points(player, day.lower())
            ws.append([
                row['time_slot'],
                row['fid'],
                row['game_name'],
                points
            ])

        # Adjust column widths
        ws.column_dimensions['A'].width = 15
        ws.column_dimensions['B'].width = 20
        ws.column_dimensions['C'].width = 30
        ws.column_dimensions['D'].width = 15

        # Save to BytesIO
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        return Response(
            output.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition': f'attachment; filename={day}_assignments_{datetime.now().strftime("%Y%m%d")}.xlsx'
            }
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_ENV') == 'development')
