"""
CHICKEN TWIN - Backend Server
Handles session file operations and AI robot control
UPDATED: Uses OpenAI API v1.0.0+
"""

from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS
import os
import json
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='.')
CORS(app)

# Configuration
SESSIONS_FOLDER = 'sessions'
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Ensure sessions folder exists
os.makedirs(SESSIONS_FOLDER, exist_ok=True)

# Initialize OpenAI client (NEW API v1.0.0+)
client = None
if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)

# Security: Whitelist allowed static files
ALLOWED_STATIC_FILES = {
    'index.html', 'demo.html', 'dashboard.html', 'sessions.html', 'analytics.html',
    'style.css', 'fav.ico', 'favicon.ico',
    'js/session_manager.js', 'ai_detection.js'
}

ALLOWED_EXTENSIONS = {'.html', '.css', '.js', '.ico', '.png', '.jpg', '.jpeg', '.gif', '.mp4', '.webm'}

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_file(path):
    # Security check
    if path.startswith('.') or '..' in path:
        return abort(403)
    
    # Check extension
    ext = os.path.splitext(path)[1].lower()
    if ext not in ALLOWED_EXTENSIONS and path not in ALLOWED_STATIC_FILES:
        return abort(403)
    
    # Allow assets folder
    if path.startswith('assets/') or path.startswith('js/'):
        return send_from_directory('.', path)
    
    if path in ALLOWED_STATIC_FILES:
        return send_from_directory('.', path)
    
    return abort(404)

@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """Get all saved sessions"""
    sessions = []
    try:
        for filename in os.listdir(SESSIONS_FOLDER):
            if filename.endswith('.json'):
                filepath = os.path.join(SESSIONS_FOLDER, filename)
                with open(filepath, 'r') as f:
                    session_data = json.load(f)
                    sessions.append({
                        'id': session_data.get('id'),
                        'filename': filename,
                        'startTime': session_data.get('startTime'),
                        'duration': session_data.get('duration'),
                        'summary': session_data.get('summary', {})
                    })
    except Exception as e:
        print(f"Error loading sessions: {e}")
    return jsonify(sessions)

@app.route('/api/sessions/<session_id>', methods=['GET'])
def get_session(session_id):
    """Get a specific session by ID"""
    filename = f"{session_id}.json"
    filepath = os.path.join(SESSIONS_FOLDER, filename)
    
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return jsonify(json.load(f))
    return jsonify({'error': 'Session not found'}), 404

@app.route('/api/sessions', methods=['POST'])
def save_session():
    """Save a new session"""
    try:
        session_data = request.json
        session_id = session_data.get('id', f"session_{int(datetime.now().timestamp() * 1000)}")
        filename = f"{session_id}.json"
        filepath = os.path.join(SESSIONS_FOLDER, filename)
        
        with open(filepath, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        return jsonify({'success': True, 'filename': filename, 'id': session_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete a session"""
    filename = f"{session_id}.json"
    filepath = os.path.join(SESSIONS_FOLDER, filename)
    
    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({'success': True})
    return jsonify({'error': 'Session not found'}), 404

@app.route('/api/robot/analyze', methods=['POST'])
def analyze_chicken():
    """Use AI to analyze chicken health and decide action"""
    try:
        data = request.json
        chicken_data = data.get('chicken', {})
        
        # Validate input
        if not chicken_data:
            return jsonify({'error': 'No chicken data provided'}), 400
        
        prompt = f"""
        You are an AI agent controlling a poultry farm robot. Analyze this chicken's data and decide the action:
        
        Chicken ID: #{chicken_data.get('id', 'Unknown')}
        Current Temperature: {chicken_data.get('temperature', 0):.1f}°C
        Status: {chicken_data.get('status', 'unknown')}
        Risk Score: {chicken_data.get('riskScore', 0):.2f}
        Position: ({chicken_data.get('x', 0):.1f}, {chicken_data.get('z', 0):.1f})
        
        Normal chicken body temperature range: 40.6°C - 41.7°C
        Warning range: 39°C - 40.6°C or 41.7°C - 42.5°C
        Critical (fever/hypothermia): Below 39°C or Above 42.5°C
        
        Based on this data, respond with a JSON object containing:
        1. "action": "pickup" if chicken needs quarantine, "monitor" if just needs watching, "ignore" if healthy
        2. "priority": 1-10 (10 being most urgent)
        3. "diagnosis": brief explanation
        4. "recommended_treatment": what should be done
        5. "quarantine_temp": if pickup, what temperature should quarantine area be set to (20-35 range)
        
        Respond ONLY with valid JSON, no other text.
        """
        
        if client:
            # Use new OpenAI API v1.0.0+
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a veterinary AI assistant for poultry health monitoring. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.3
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            # Parse AI response
            try:
                decision = json.loads(ai_response)
            except json.JSONDecodeError:
                decision = get_fallback_decision(chicken_data)
        else:
            # Fallback if no API key
            decision = get_fallback_decision(chicken_data)
        
        return jsonify(decision)
        
    except Exception as e:
        print(f"AI Analysis Error: {e}")
        return jsonify(get_fallback_decision(chicken_data if 'chicken_data' in dir() else {}))

def get_fallback_decision(chicken_data):
    """Fallback decision when AI is unavailable"""
    temp = chicken_data.get('temperature', 40.0)
    risk = chicken_data.get('riskScore', 0)
    
    if temp > 42.5 or temp < 38.0 or risk > 0.8:
        return {
            "action": "pickup",
            "priority": 9,
            "diagnosis": "Critical temperature or risk level detected",
            "recommended_treatment": "Immediate isolation and veterinary attention",
            "quarantine_temp": 26.0 if temp > 42.5 else 30.0
        }
    elif temp > 41.7 or temp < 39.0 or risk > 0.6:
        return {
            "action": "monitor",
            "priority": 6,
            "diagnosis": "Elevated temperature or risk - monitoring required",
            "recommended_treatment": "Close observation for next 30 minutes",
            "quarantine_temp": 28.0
        }
    else:
        return {
            "action": "ignore",
            "priority": 1,
            "diagnosis": "Bird appears healthy",
            "recommended_treatment": "No action required",
            "quarantine_temp": 28.0
        }

@app.route('/api/robot/quarantine-temp', methods=['POST'])
def set_quarantine_temp():
    """AI decides optimal quarantine temperature based on chicken conditions"""
    try:
        data = request.json
        chickens = data.get('chickens', [])
        
        if not chickens:
            return jsonify({'temperature': 28.0, 'reason': 'No chickens in quarantine'})
        
        avg_temp = sum(c.get('temperature', 40) for c in chickens) / len(chickens)
        
        # Simple rule-based logic (fallback)
        if avg_temp > 42.0:
            room_temp = 24.0  # Cooling for fever
            reason = "Cooling environment for feverish birds"
        elif avg_temp < 39.0:
            room_temp = 32.0  # Warming for hypothermia
            reason = "Warming environment for hypothermic birds"
        else:
            room_temp = 28.0  # Normal
            reason = "Comfortable temperature for recovery"
        
        if client:
            try:
                prompt = f"""
                Calculate optimal ROOM temperature for quarantine area.
                
                Number of sick chickens: {len(chickens)}
                Average body temperature: {avg_temp:.1f}°C
                
                Respond with JSON only: {{"temperature": <number 20-35>, "reason": "<brief explanation>"}}
                """
                
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a poultry veterinary expert. Respond with valid JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=100,
                    temperature=0.3
                )
                
                result = json.loads(response.choices[0].message.content.strip())
                return jsonify(result)
            except:
                pass
        
        return jsonify({'temperature': room_temp, 'reason': reason})
        
    except Exception as e:
        return jsonify({'temperature': 28.0, 'reason': f'Error: {str(e)}'})

@app.route('/api/sessions/start', methods=['POST'])
def start_session_endpoint():
    """Log session start"""
    try:
        session_data = request.json
        print(f"[SESSION] Started: {session_data.get('id')}")
        
        session_id = session_data.get('id')
        if session_id:
            filename = f"{session_id}.json"
            filepath = os.path.join(SESSIONS_FOLDER, filename)
            
            with open(filepath, 'w') as f:
                json.dump(session_data, f, indent=2)
                
        return jsonify({'success': True, 'message': 'Session started and persisted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/summary', methods=['GET'])
def get_analytics_summary():
    """Get analytics summary data"""
    try:
        sessions = []
        for filename in os.listdir(SESSIONS_FOLDER):
            if filename.endswith('.json'):
                filepath = os.path.join(SESSIONS_FOLDER, filename)
                with open(filepath, 'r') as f:
                    sessions.append(json.load(f))
        
        if not sessions:
            return jsonify({
                'totalSessions': 0,
                'totalBirdsMonitored': 0,
                'avgHealthScore': 0,
                'totalInterventions': 0,
                'avgSessionDuration': 0
            })
        
        total_birds = sum(s.get('summary', {}).get('totalBirds', 0) for s in sessions)
        avg_health = sum(float(s.get('summary', {}).get('avgHealthScore', 0) or 0) for s in sessions) / len(sessions)
        total_interventions = sum(s.get('summary', {}).get('quarantined', 0) for s in sessions)
        avg_duration = sum(s.get('duration', 0) for s in sessions) / len(sessions)
        
        return jsonify({
            'totalSessions': len(sessions),
            'totalBirdsMonitored': total_birds,
            'avgHealthScore': round(avg_health, 2),
            'totalInterventions': total_interventions,
            'avgSessionDuration': round(avg_duration / 1000, 2)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'openai_configured': client is not None,
        'sessions_folder': os.path.exists(SESSIONS_FOLDER),
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    print("=" * 60)
    print("  CHICKEN TWIN - Backend Server")
    print("=" * 60)
    print(f"  Sessions folder: {os.path.abspath(SESSIONS_FOLDER)}")
    print(f"  OpenAI API configured: {'Yes' if OPENAI_API_KEY else 'No - Using fallback'}")
    print("  Starting server on http://localhost:5000")
    print("=" * 60)
    # SECURITY: Disable debug mode for production
    app.run(debug=False, port=5000, host='0.0.0.0')