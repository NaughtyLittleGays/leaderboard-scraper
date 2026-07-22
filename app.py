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
CHECK_INTERVAL_SECONDS = 60

app = Flask(__name__)

# Structured database: { "tp01": { "Team": { "score": float, "display": str } }, ... }
best_scores = {p: {} for p in PROJECTS}

if os.path.exists(LOG_FILE):
    try:
        with open(LOG_FILE, "r") as f:
            loaded_data = json.load(f)
            for p in PROJECTS:
                if p in loaded_data and isinstance(loaded_data[p], dict):
                    best_scores[p] = loaded_data[p]
    except Exception as e:
        print(f"Notice: Initializing clean database ({e})")

# ==========================================
# 2. EXACT JSON PARSER
# ==========================================


def parse_entry_metrics(entry):
    """
    Parses exact keys returned by TP01, TP02, and TP03 APIs.
    """
    # TP02 / Machine Learning (MSE)
    if "mse" in entry and entry["mse"] is not None:
        val = float(entry["mse"])
        return val, f"{val:.2f}"

    # TP01 / Optimization (restweg_h & covered)
    if "restweg_h" in entry and entry["restweg_h"] is not None:
        val = float(entry["restweg_h"])
        cov = entry.get("covered", "-")
        return val, f"Cov: {cov} | Dist: {val:.2f}"

    # TP03 / Robotics (path_length)
    if "path_length" in entry and entry["path_length"] is not None:
        val = float(entry["path_length"])
        return val, f"Path: {val:.2f}"

    # Generic Fallback
    for key in ["remaining_distance", "distance", "score"]:
        if key in entry and entry[key] is not None:
            val = float(entry[key])
            return val, f"{val:.2f}"

    return None, None

# ==========================================
# 3. BACKGROUND SCRAPER DAEMON
# ==========================================


def monitor_leaderboards():
    global best_scores
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*"
    }

    while True:
        for project in PROJECTS:
            url = BASE_URL.format(project=project)
            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    project_scores = best_scores[project]

                    for entry in data:
                        team = entry.get("group_name")
                        if not team:
                            continue

                        score, display_str = parse_entry_metrics(entry)
                        if score is None:
                            continue

                        # Initialize team or update if score improved (lower is better for all 3)
                        if team not in project_scores:
                            project_scores[team] = {
                                "score": score, "display": display_str}
                            print(
                                f"[{project.upper()}] Tracking {team}: {display_str}")
                        elif score < project_scores[team]["score"]:
                            prev = project_scores[team]["score"]
                            print(
                                f"[{project.upper()}] 🚨 IMPROVEMENT: {team} dropped from {prev:.2f} to {score:.2f}!")
                            project_scores[team] = {
                                "score": score, "display": display_str}

            except Exception as e:
                print(f"[{project.upper()}] Scraper Error: {e}")

        # Persist to disk
        try:
            with open(LOG_FILE, "w") as f:
                json.dump(best_scores, f, indent=4)
        except Exception as e:
            print(f"Save Error: {e}")

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
		.footer { text-align: center; margin-top: 30px; font-size: 0.75em; color: #888; }
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

	<div class="footer">Tracking historical best scores across TP01, TP02, & TP03. Auto-refreshes in background.</div>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, scores=best_scores)


@app.route('/health')
def health():
    return "OK", 200


if __name__ == '__main__':
    scraper_thread = threading.Thread(target=monitor_leaderboards, daemon=True)
    scraper_thread.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
