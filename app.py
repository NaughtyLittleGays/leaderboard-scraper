import time
import json
import os
import threading
from datetime import datetime
import requests
from flask import Flask, render_template_string

# ==========================================
# 1. CONFIGURATION
# ==========================================
API_URL = "https://ids-challenge.imi-services.imi.kit.edu/tp02/leaderboard"
LOG_FILE = "team_high_scores.json"
CHECK_INTERVAL_SECONDS = 60

app = Flask(__name__)

# Load existing history to persist data
if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "r") as f:
        best_scores = json.load(f)
else:
    best_scores = {}

# ==========================================
# 2. BACKGROUND SCRAPER DAEMON
# ==========================================


def monitor_leaderboard():
    global best_scores

    # Headers to mimic the browser request you captured
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*"
    }

    while True:
        try:
            response = requests.get(API_URL, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()

                for entry in data:
                    team = entry.get("group_name")
                    current_mse = entry.get("mse")

                    if not team or current_mse is None:
                        continue

                    # Initialize or check for improvements
                    if team not in best_scores:
                        best_scores[team] = current_mse
                        print(f"Tracking new team: {team} @ {current_mse}")
                    elif current_mse < best_scores[team]:
                        print(
                            f"🚨 IMPROVEMENT: {team} dropped to {current_mse}!")
                        best_scores[team] = current_mse

                # Save to disk
                with open(LOG_FILE, "w") as f:
                    json.dump(best_scores, f, indent=4)

        except Exception as e:
            print(f"Scraper Error: {e}")

        time.sleep(CHECK_INTERVAL_SECONDS)


# ==========================================
# 3. WEB SERVER (Mobile Friendly View)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="UTF-8">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>KIT Radar | nekonyan.fun</title>
	<style>
		body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #121212; color: #ffffff; padding: 20px; }
		h1 { color: #bb86fc; text-align: center; }
		.card { background: #1e1e1e; border-radius: 8px; padding: 15px; margin-bottom: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
		.team-name { font-size: 1.2em; font-weight: bold; color: #03dac6; }
		.score { font-size: 1.5em; float: right; color: #cf6679; }
		.footer { text-align: center; margin-top: 30px; font-size: 0.8em; color: #888; }
	</style>
</head>
<body>
	<h1>🎯 Leaderboard Radar</h1>
	<div id="scores">
		{% for team, score in scores|dictsort(false, 'value') %}
		<div class="card">
			<span class="team-name">{{ team }}</span>
			<span class="score">{{ "%.2f"|format(score) }}</span>
		</div>
		{% endfor %}
	</div>
	<div class="footer">Tracking absolute lowest historical MSE. Auto-refreshes in background.</div>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, scores=best_scores)


@app.route('/health')
def health():
    return "OK", 200


# ==========================================
# 4. EXECUTION
# ==========================================
if __name__ == '__main__':
    # Start the scraper in a background thread
    scraper_thread = threading.Thread(target=monitor_leaderboard, daemon=True)
    scraper_thread.start()

    # Start the web server
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
