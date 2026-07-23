import time
import json
import os
import threading
from flask import Flask, render_template_string
import requests

# ==========================================
# 1. CONFIGURATION
# ==========================================
PROJECTS = ["tp01", "tp02", "tp03"]
BASE_URL = "https://ids-challenge.imi-services.imi.kit.edu/{project}/leaderboard"
LOG_FILE = "team_high_scores.json"
CHECK_INTERVAL_SECONDS = 5

app = Flask(__name__)

# State Trackers
best_scores = {p: {} for p in PROJECTS}
# Tracks exact last state to catch non-improvements
last_seen = {p: {} for p in PROJECTS}
activity_log = []  # Rolling log of the last 50 movements

if os.path.exists(LOG_FILE):
    try:
        with open(LOG_FILE, "r") as f:
            loaded_data = json.load(f)
            for p in PROJECTS:
                if p in loaded_data and isinstance(loaded_data[p], dict):
                    best_scores[p] = loaded_data[p]
    except Exception as e:
        print(f"Notice: Initializing clean database ({e})", flush=True)

# ==========================================
# 2. EXACT JSON PARSER
# ==========================================


def parse_entry_metrics(entry):
    if "mse" in entry and entry["mse"] is not None:
        val = float(entry["mse"])
        return val, f"{val:.2f}"

    if "restweg_h" in entry and entry["restweg_h"] is not None:
        val = float(entry["restweg_h"])
        cov = entry.get("covered", "-")
        return val, f"Cov: {cov} | Dist: {val:.2f}"

    if "path_length" in entry and entry["path_length"] is not None:
        val = float(entry["path_length"])
        return val, f"Path: {val:.2f}"

    for key in ["remaining_distance", "distance", "score"]:
        if key in entry and entry[key] is not None:
            val = float(entry[key])
            return val, f"{val:.2f}"

    return None, None

# ==========================================
# 3. BACKGROUND SCRAPER DAEMON
# ==========================================


def monitor_leaderboards():
    global best_scores, last_seen, activity_log
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "Accept": "*/*"
    }

    print("--- Background Leaderboard Monitor Started ---", flush=True)

    while True:
        for project in PROJECTS:
            url = BASE_URL.format(project=project)
            try:
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()

                data = response.json()
                project_scores = best_scores[project]

                for entry in data:
                    team = entry.get("group_name")
                    if not team:
                        continue

                    score, display_str = parse_entry_metrics(entry)
                    if score is None:
                        continue

                    # --- 1. ACTIVITY LOG TRACKING (Catches ALL movement) ---
                    if team not in last_seen[project]:
                        last_seen[project][team] = display_str
                    elif last_seen[project][team] != display_str:
                        old_val = last_seen[project][team]
                        timestamp = time.strftime("%H:%M:%S")
                        log_msg = f"[{timestamp}] {team} ({project.upper()}) went from {old_val} to {display_str}!"

                        activity_log.insert(0, log_msg)
                        if len(activity_log) > 50:  # Keep UI clean, max 50 events
                            activity_log.pop()

                        print(log_msg, flush=True)
                        last_seen[project][team] = display_str

                    # --- 2. HISTORICAL BEST TRACKING ---
                    if team not in project_scores:
                        project_scores[team] = {
                            "score": score, "display": display_str}
                    elif score < project_scores[team]["score"]:
                        project_scores[team] = {
                            "score": score, "display": display_str}

            except Exception as e:
                print(f"[{project.upper()}] Scraper Error: {e}", flush=True)

        try:
            with open(LOG_FILE, "w") as f:
                json.dump(best_scores, f, indent=4)
        except Exception as e:
            print(f"Save Error: {e}", flush=True)

        time.sleep(CHECK_INTERVAL_SECONDS)


# ==========================================
# 4. WEB SERVER
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="UTF-8">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>KIT Radar | Multi-Board</title>
	<style>
		body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #121212; color: #ffffff; padding: 15px; margin: 0; }
		h1 { color: #bb86fc; text-align: center; margin-top: 10px; margin-bottom: 20px; font-size: 1.5em; }
		.project-section { margin-bottom: 25px; }
		.project-header { font-size: 1.2em; font-weight: bold; color: #03dac6; border-bottom: 2px solid #03dac6; padding-bottom: 4px; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 1px; }
		.card { background: #1e1e1e; border-radius: 8px; padding: 12px 16px; margin-bottom: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); display: flex; justify-content: space-between; align-items: center; }
		.team-name { font-size: 1em; font-weight: 500; color: #e0e0e0; }
		.score { font-size: 1.1em; font-weight: bold; color: #cf6679; }
		.empty { color: #666; font-style: italic; font-size: 0.85em; padding: 6px 0; }
		
		.log-container { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 10px; max-height: 250px; overflow-y: auto; font-family: 'Courier New', Courier, monospace; font-size: 0.85em; color: #a9a9a9; }
		.log-entry { padding: 4px 0; border-bottom: 1px solid #2a2a2a; }
		.log-entry:last-child { border-bottom: none; }
		
		.footer { text-align: center; margin-top: 30px; margin-bottom: 20px; font-size: 0.75em; color: #888; }
	</style>
</head>
<body>
	<h1>🎯 Leaderboard Radar</h1>
	
	{% for project, teams in scores.items() %}
	<div class="project-section">
		<div class="project-header">{{ project|upper }}</div>
		{% if teams %}
			{% for team, info in teams.items()|sort(attribute='1.score') %}
			<div class="card">
				<span class="team-name">{{ team }}</span>
				<span class="score">{{ info.display }}</span>
			</div>
			{% endfor %}
		{% else %}
			<div class="empty">No data captured yet for {{ project|upper }}...</div>
		{% endif %}
	</div>
	{% endfor %}

	<div class="project-section">
		<div class="project-header" style="color: #ffb86c; border-bottom-color: #ffb86c;">Live Activity Log</div>
		<div class="log-container">
			{% if logs %}
				{% for log in logs %}
					<div class="log-entry">{{ log }}</div>
				{% endfor %}
			{% else %}
				<div class="empty">Monitoring for incoming network changes...</div>
			{% endif %}
		</div>
	</div>

	<div class="footer">Tracking historical bests + live activity. Auto-refreshes in background.</div>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, scores=best_scores, logs=activity_log)


@app.route('/health')
def health():
    return "OK", 200


if __name__ == '__main__':
    scraper_thread = threading.Thread(target=monitor_leaderboards, daemon=True)
    scraper_thread.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
