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
TXT_LOG_FILE = "activity_log.txt"
CHECK_INTERVAL_SECONDS = 5

app = Flask(__name__)

# State Trackers
best_scores = {p: {} for p in PROJECTS}
last_seen = {p: {} for p in PROJECTS}
activity_log = []
flagged_cheaters = set()  # Tracks (team, raw_str) so alerts print ONCE


def is_hummingbird(team_name):
    """Strict check to purge and ignore The Hummingbirds everywhere."""
    return "hummingbird" in str(team_name).strip().lower()


# --- LOAD & SANITIZE JSON BEST SCORES ON STARTUP ---
if os.path.exists(LOG_FILE):
    try:
        with open(LOG_FILE, "r") as f:
            loaded_data = json.load(f)
            for p in PROJECTS:
                if p in loaded_data and isinstance(loaded_data[p], dict):
                    for team, info in loaded_data[p].items():
                        if not is_hummingbird(team):
                            if isinstance(info, dict):
                                if "raw" not in info:
                                    info["raw"] = str(
                                        info.get("score", info.get("display", "")))
                                best_scores[p][team] = info
    except Exception as e:
        print(f"Notice: Initializing clean database ({e})", flush=True)

# --- LOAD EXISTING TXT LOGS ON STARTUP ---
if os.path.exists(TXT_LOG_FILE):
    try:
        with open(TXT_LOG_FILE, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
            activity_log = lines[::-1][:50]
    except Exception as e:
        print(f"Notice: Could not load text log file ({e})", flush=True)


def append_to_txt_log(msg):
    try:
        with open(TXT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
            f.flush()
    except Exception as e:
        print(f"Error writing to {TXT_LOG_FILE}: {e}", flush=True)

# ==========================================
# 2. EXACT JSON PARSER
# ==========================================


def parse_entry_metrics(entry):
    if "mse" in entry and entry["mse"] is not None:
        val = float(entry["mse"])
        return val, f"{val:.2f}", str(entry["mse"])

    if "restweg_h" in entry and entry["restweg_h"] is not None:
        val = float(entry["restweg_h"])
        cov = entry.get("covered", "-")
        return val, f"Cov: {cov} | Dist: {val:.2f}", f"Cov: {cov} | Raw: {entry['restweg_h']}"

    if "path_length" in entry and entry["path_length"] is not None:
        val = float(entry["path_length"])
        return val, f"Path: {val:.2f}", f"Path: {entry['path_length']}"

    for key in ["remaining_distance", "distance", "score"]:
        if key in entry and entry[key] is not None:
            val = float(entry[key])
            return val, f"{val:.2f}", str(entry[key])

    return None, None, None

# ==========================================
# 3. BACKGROUND SCRAPER DAEMON
# ==========================================


def monitor_leaderboards():
    global best_scores, last_seen, activity_log, flagged_cheaters
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
                    if not team or is_hummingbird(team):
                        continue

                    score, display_str, raw_str = parse_entry_metrics(entry)
                    if score is None:
                        continue

                    # --- REQUIREMENT: TP03 CHEATER DETECTION LOGGING (< 9.70) ---
                    if project == "tp03" and score < 9.70:
                        cheat_key = (team, raw_str)

                        # 1. LOG ALERT ONCE
                        if cheat_key not in flagged_cheaters:
                            flagged_cheaters.add(cheat_key)
                            timestamp = time.strftime("%H:%M:%S")
                            alert = f"[{timestamp}] 🚨 CHEATER DETECTED: {team} submitted {raw_str} (< 9.70 threshold)!"
                            activity_log.insert(0, alert)
                            append_to_txt_log(alert)
                            print(alert, flush=True)

                        # 2. LOG MULTIPLE ENTRIES ON TP03 LEADERBOARD
                        entry_key = f"{team} 🚨 ({raw_str})"
                        project_scores[entry_key] = {
                            "score": score,
                            "display": display_str,
                            "raw": raw_str,
                            "team_display": f"{team} 🚨"
                        }

                    # --- ACTIVITY LOG TRACKING (Standard movement) ---
                    if team not in last_seen[project]:
                        last_seen[project][team] = display_str
                    elif last_seen[project][team] != display_str:
                        old_val = last_seen[project][team]
                        timestamp = time.strftime("%H:%M:%S")
                        log_msg = f"[{timestamp}] {team} ({project.upper()}) went from {old_val} to {display_str} (Raw: {raw_str})!"

                        activity_log.insert(0, log_msg)
                        append_to_txt_log(log_msg)

                        if len(activity_log) > 50:
                            activity_log.pop()

                        print(log_msg, flush=True)
                        last_seen[project][team] = display_str

                    # --- HISTORICAL BEST TRACKING (Standard Teams) ---
                    if project == "tp03" and score < 9.70:
                        continue  # Handled above as multiple flagged entries

                    if team not in project_scores:
                        project_scores[team] = {
                            "score": score,
                            "display": display_str,
                            "raw": raw_str,
                            "team_display": team
                        }
                    elif score < project_scores[team]["score"]:
                        project_scores[team] = {
                            "score": score,
                            "display": display_str,
                            "raw": raw_str,
                            "team_display": team
                        }

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
	<link rel="icon" type="image/x-icon" href="https://rule34.xxx/favicon.ico?v=2">
	<style>
		body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #121212; color: #ffffff; padding: 15px; margin: 0; }
		h1 { color: #bb86fc; text-align: center; margin-top: 10px; margin-bottom: 20px; font-size: 1.5em; }
		.project-section { margin-bottom: 25px; }
		.project-header { font-size: 1.2em; font-weight: bold; color: #03dac6; border-bottom: 2px solid #03dac6; padding-bottom: 4px; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 1px; }
		.card { background: #1e1e1e; border-radius: 8px; padding: 12px 16px; margin-bottom: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); display: flex; justify-content: space-between; align-items: center; }
		.team-name { font-size: 1em; font-weight: 500; color: #e0e0e0; }
		.score-box { text-align: right; }
		.score { font-size: 1.1em; font-weight: bold; color: #cf6679; }
		.raw-score { font-size: 0.78em; color: #ff79c6; font-family: monospace; display: block; margin-top: 3px; word-break: break-all; }
		.empty { color: #666; font-style: italic; font-size: 0.85em; padding: 6px 0; }
		
		.log-container { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 10px; max-height: 300px; overflow-y: auto; font-family: 'Courier New', Courier, monospace; font-size: 0.82em; color: #a9a9a9; }
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
				<span class="team-name">{{ info.team_display if info.team_display else team }}</span>
				<div class="score-box">
					<span class="score">{{ info.display }}</span>
					<span class="raw-score">{{ info.raw if info.raw else info.score }}</span>
				</div>
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

	<div class="footer">Tracking historical bests + live persistent logging. Auto-refreshes in background.</div>
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
