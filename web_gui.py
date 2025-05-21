import os
import requests
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')
app.secret_key = os.urandom(24)

SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001")

def format_datetime(date_str, time_str):
    """Format date and time strings into ISO format with +2 timezone offset."""
    return f"{date_str}T{time_str}:00+02:00"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calendar')
def calendar():
    return render_template('calendar.html')

@app.route('/create_event', methods=['GET', 'POST'])
def create_event():
    if request.method == 'POST':
        summary = request.form.get('summary')
        start_date = request.form.get('start_date')
        start_time = request.form.get('start_time')
        end_date = request.form.get('end_date') or start_date
        end_time = request.form.get('end_time')
        attendees_str = request.form.get('attendees', '')
        attendees = [a.strip() for a in attendees_str.split(',') if a.strip()]
        
        start = format_datetime(start_date, start_time)
        end = format_datetime(end_date, end_time)
        
        payload = {
            "name": "create_calendar_event",
            "arguments": {
                "summary": summary,
                "start": start,
                "end": end,
                "attendees": attendees,
            },
        }
        
        try:
            resp = requests.post(f"{SERVER_URL}/call_tool", json=payload, timeout=30)
            resp.raise_for_status()
            flash('Event created successfully!', 'success')
            return redirect(url_for('calendar'))
        except requests.RequestException as e:
            flash(f'Error creating event: {str(e)}', 'error')
    
    return render_template('create_event.html')

@app.route('/check_availability', methods=['GET', 'POST'])
def check_availability():
    availability_data = None
    
    if request.method == 'POST':
        date_str = request.form.get('date')
        
        payload = {
            "name": "check_day_availability",
            "arguments": {"date": date_str},
        }
        
        try:
            resp = requests.post(f"{SERVER_URL}/call_tool", json=payload, timeout=30)
            resp.raise_for_status()
            availability_data = resp.json().get("text", "")
        except requests.RequestException as e:
            flash(f'Error checking availability: {str(e)}', 'error')
    
    return render_template('availability.html', availability_data=availability_data)

@app.route('/api/list_events', methods=['GET'])
def list_events_api():
    try:
        from datetime import datetime, timedelta
        
        start = datetime.utcnow()
        end = start + timedelta(days=7)
        
        payload = {
            "name": "list_calendar_events",
            "arguments": {
                "time_min": start.isoformat() + "Z",
                "time_max": end.isoformat() + "Z",
                "max_results": 20,
            },
        }
        
        resp = requests.post(f"{SERVER_URL}/call_tool", json=payload, timeout=30)
        resp.raise_for_status()
        return jsonify(resp.json())
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    app.run(debug=True, port=5000)
