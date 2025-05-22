import os
import subprocess
import threading
import requests
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from dotenv import load_dotenv

load_dotenv()

MCP_DIR = os.path.join(os.path.dirname(__file__), "MCP")

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')
app.secret_key = os.urandom(24)

SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001")

def start_server() -> subprocess.Popen:
    """Launch workspace_mcp_server.py as a subprocess."""
    server_path = os.path.join(MCP_DIR, "workspace_mcp_server.py")
    return subprocess.Popen(
        ["python", str(server_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=MCP_DIR,
    )

server_output_lines = []

def stream_output(proc: subprocess.Popen) -> None:
    """Read server output and store it."""
    assert proc.stdout is not None
    for line in proc.stdout:
        server_output_lines.append(line)
        if len(server_output_lines) > 100:  # Keep last 100 lines
            server_output_lines.pop(0)

server_proc = start_server()
t = threading.Thread(target=stream_output, args=(server_proc,), daemon=True)
t.start()

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

@app.route('/summarize_emails', methods=['GET', 'POST'])
def summarize_emails():
    summary = None
    
    if request.method == 'POST':
        query = request.form.get('query', 'newer_than:7d')
        question = request.form.get('question', 'Summarize the last week\'s emails with important highlights and stats.')
        max_results = int(request.form.get('max_results', '10'))
        
        labels = []
        try:
            import csv
            from pathlib import Path
            
            LABEL_CSV = os.path.join(MCP_DIR, "gmail_labels.csv")
            if os.path.exists(LABEL_CSV):
                with open(LABEL_CSV, newline="") as fh:
                    for row in csv.DictReader(fh):
                        if row.get("important", "").lower() == "true":
                            labels.append(row["id"])
        except Exception as e:
            flash(f'Error loading labels: {str(e)}', 'error')
        
        try:
            payload = {
                "name": "list_recent_emails",
                "arguments": {
                    "query": query,
                    "label_ids": labels,
                    "max_results": max_results
                }
            }
            resp = requests.post(f"{SERVER_URL}/call_tool", json=payload, timeout=30)
            resp.raise_for_status()
            
            emails_text = resp.json().get("text", "")
            email_count = resp.json().get("count", 0)
            
            from MCP.llm_service import get_service
            
            llm = get_service()
            messages = [
                {
                    "role": "system",
                    "content": "You are an assistant that answers questions about the users recent emails based only on the snippets provided."
                },
                {"role": "user", "content": f"Emails:\n{emails_text}\n\nQuestion: {question}"}
            ]
            
            summary = llm.chat(messages)
            flash(f'Found {email_count} emails matching your query.', 'success')
        except Exception as e:
            flash(f'Error summarizing emails: {str(e)}', 'error')
    
    return render_template('summarize_emails.html', summary=summary)

@app.route('/review_day', methods=['GET', 'POST'])
def review_day():
    summary = None
    
    if request.method == 'POST':
        date_str = request.form.get('date')
        
        try:
            from datetime import datetime, timedelta
            date = datetime.strptime(date_str, "%Y-%m-%d")
            next_day = date + timedelta(days=1)
            query = f"after:{date.strftime('%Y/%m/%d')} before:{next_day.strftime('%Y/%m/%d')}"
            question = f"Summarize all emails from {date_str} in detail."
            
            payload = {
                "name": "list_recent_emails",
                "arguments": {
                    "query": query,
                    "max_results": 50
                }
            }
            resp = requests.post(f"{SERVER_URL}/call_tool", json=payload, timeout=30)
            resp.raise_for_status()
            
            emails_text = resp.json().get("text", "")
            email_count = resp.json().get("count", 0)
            
            from MCP.llm_service import get_service
            
            llm = get_service()
            messages = [
                {"role": "system", "content": "You are an assistant that answers questions about the users emails based only on the snippets provided."},
                {"role": "user", "content": f"Emails:\n{emails_text}\n\nQuestion: {question}"}
            ]
            
            summary = llm.chat(messages)
            flash(f'Found {email_count} emails on {date_str}.', 'success')
        except Exception as e:
            flash(f'Error reviewing day: {str(e)}', 'error')
    
    return render_template('review_day.html', summary=summary)

@app.route('/count_emails', methods=['GET', 'POST'])
def count_emails():
    labels = []
    count_result = None
    
    try:
        payload = {"name": "list_gmail_labels", "arguments": {}}
        resp = requests.post(f"{SERVER_URL}/call_tool", json=payload, timeout=30)
        resp.raise_for_status()
        
        text = resp.json().get("text", "")
        for line in text.splitlines():
            if ":" in line:
                label_id, name = line.split(":", 1)
                labels.append({"id": label_id.strip(), "name": name.strip()})
    except Exception as e:
        flash(f'Error loading labels: {str(e)}', 'error')
    
    if request.method == 'POST':
        label_id = request.form.get('label_id')
        
        try:
            payload = {
                "name": "count_emails_by_label",
                "arguments": {"label_id": label_id}
            }
            
            resp = requests.post(f"{SERVER_URL}/call_tool", json=payload, timeout=30)
            resp.raise_for_status()
            
            count = resp.json().get("text", "0")
            label_name = next((label['name'] for label in labels if label['id'] == label_id), label_id)
            
            count_result = {
                "label_id": label_id,
                "label_name": label_name,
                "count": count
            }
        except Exception as e:
            flash(f'Error counting emails: {str(e)}', 'error')
    
    return render_template('count_emails.html', labels=labels, count_result=count_result)

@app.route('/labels', methods=['GET', 'POST'])
def manage_labels():
    labels = []
    
    LABEL_CSV = os.path.join(MCP_DIR, "gmail_labels.csv")
    
    if os.path.exists(LABEL_CSV):
        try:
            import csv
            with open(LABEL_CSV, newline="") as fh:
                labels = list(csv.DictReader(fh))
        except Exception as e:
            flash(f'Error loading labels from CSV: {str(e)}', 'error')
    
    if request.method == 'POST':
        if 'sync_labels' in request.form:
            try:
                payload = {"name": "list_gmail_labels", "arguments": {}}
                resp = requests.post(f"{SERVER_URL}/call_tool", json=payload, timeout=30)
                resp.raise_for_status()
                
                text = resp.json().get("text", "")
                new_labels = []
                for line in text.splitlines():
                    if ":" in line:
                        label_id, name = line.split(":", 1)
                        label_id = label_id.strip()
                        name = name.strip()
                        
                        existing = next((lbl for lbl in labels if lbl['id'] == label_id), None)
                        important = "True" if existing and existing.get('important') == "True" else "False"
                        
                        new_labels.append({
                            "id": label_id,
                            "name": name,
                            "important": important
                        })
                
                with open(LABEL_CSV, "w", newline="") as fh:
                    writer = csv.DictWriter(fh, fieldnames=["id", "name", "important"])
                    writer.writeheader()
                    writer.writerows(new_labels)
                
                flash(f'Successfully synced {len(new_labels)} labels.', 'success')
                labels = new_labels
            except Exception as e:
                flash(f'Error syncing labels: {str(e)}', 'error')
        else:
            try:
                new_labels = []
                for label in labels:
                    label_id = label['id']
                    important = "True" if request.form.get(f'important_{label_id}') else "False"
                    new_labels.append({
                        "id": label_id,
                        "name": label['name'],
                        "important": important
                    })
                
                with open(LABEL_CSV, "w", newline="") as fh:
                    writer = csv.DictWriter(fh, fieldnames=["id", "name", "important"])
                    writer.writeheader()
                    writer.writerows(new_labels)
                
                flash('Label importance updated successfully.', 'success')
                labels = new_labels
            except Exception as e:
                flash(f'Error updating labels: {str(e)}', 'error')
    
    return render_template('manage_labels.html', labels=labels)

@app.route('/server_logs')
def server_logs():
    log_entries = []
    
    console_output = "\n".join(server_output_lines[-50:]) if server_output_lines else "No server output available."
    
    LOG_FILE = os.path.join(os.path.dirname(__file__), 'logs', 'app.log')
    if os.path.exists(LOG_FILE):
        try:
            import json
            with open(LOG_FILE, 'r') as f:
                log_lines = f.readlines()[-20:]  # Last 20 entries
                
                for line in log_lines:
                    try:
                        log_entry = json.loads(line.strip())
                        log_entries.append(log_entry)
                    except:
                        pass  # Skip malformed JSON lines
        except Exception as e:
            flash(f'Error reading log file: {str(e)}', 'error')
    
    return render_template('server_logs.html', log_entries=log_entries, console_output=console_output)

@app.template_filter('nl2br')
def nl2br(value):
    if value:
        return value.replace('\n', '<br>')
    return value

@app.template_filter('format_email')
def format_email(value):
    """Format email content with better HTML rendering.
    
    This filter:
    1. Converts newlines to <br> tags
    2. Formats paragraphs with proper spacing
    3. Handles bullet points and numbered lists
    4. Highlights important information
    """
    if not value:
        return ""
    
    import re
    import html
    
    text = html.escape(value)
    
    text = re.sub(r'\n\s*\n', '</p><p>', text)
    
    text = re.sub(r'(?m)^[-*•]\s+(.*?)$', r'<li>\1</li>', text)
    text = re.sub(r'(?s)<li>.*?</li>', r'<ul>\g<0></ul>', text)
    
    text = re.sub(r'(?m)^\d+\.\s+(.*?)$', r'<li>\1</li>', text)
    text = re.sub(r'(?s)(<li>.*?</li>)', r'<ol>\1</ol>', text)
    
    text = re.sub(r'<\/ul>\s*<ul>', '', text)
    text = re.sub(r'<\/ol>\s*<ol>', '', text)
    
    text = re.sub(r'(?i)important:?\s*(.*?)(?=\n|$)', r'<strong class="text-danger">Important: \1</strong>', text)
    
    text = re.sub(r'([A-Za-z0-9\s]+):\s*\n', r'<h5>\1:</h5>', text)
    
    text = text.replace('\n', '<br>')
    
    if not text.startswith('<p>'):
        text = '<p>' + text
    if not text.endswith('</p>'):
        text = text + '</p>'
    
    return text

if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    app.run(debug=True, port=5000)
