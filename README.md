# TLDR

### Run the app locally

```bash
python app.py
```

(or `python3 app.py` if your system uses `python3`)

This will start the Flask app on port `5000`. You can access it at:

- http://localhost:5000/
- http://localhost:5000/health

### Install cloudflared

Open a new console and install `cloudflared` using the Windows Terminal:

```powershell
winget install --id Cloudflare.cloudflared
```

or Windows Command Prompt:

```cmd
winget install --id Cloudflare.cloudflared
```

### Expose the app with Cloudflare Tunnel

Make sure the Flask app is running, then in a separate console, run:

```bash
cloudflared tunnel --url http://localhost:5000
```

This will give you a random hostname like `random-words-12345.trycloudflare.com` that you can use to access the app from the internet.

---

# Leaderboard Scraper

This project runs a small Flask web app that scrapes several KIT leaderboards in the background, tracks the best scores seen so far, and displays them in a simple dashboard.

## What it does

- Polls the leaderboard endpoints every 5 seconds
- Stores the best scores in `team_high_scores.json`
- Serves a web UI at `/`
- Exposes a simple health check at `/health`

## Requirements

- Python 3.9+
- Internet access to reach the leaderboard URLs
- A Cloudflare account if you want to expose the app with Cloudflare Tunnel

## Local setup

### 1. Create and activate a virtual environment

Windows (PowerShell):

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the app

```bash
python app.py
```

(If you're using python3, you may need to run `python3 app.py` instead.)

The app will start on port `5000` by default.

Open these URLs in your browser:

- http://localhost:5000/
- http://localhost:5000/health

## Running with Cloudflare Tunnel (cloudflared)

Cloudflare Tunnel lets you expose your local Flask app to the internet without opening firewall ports.

### 1. Install cloudflared

Windows (PowerShell):

```powershell
winget install --id Cloudflare.cloudflared
```

(Or Windows Command Prompt):

```cmd
winget install --id Cloudflare.cloudflared
```

macOS:

```bash
brew install cloudflared
```

Linux (Debian/Ubuntu):

```bash
curl -L https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-archive-keyring.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-archive-keyring.gpg] https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update
sudo apt install cloudflared
```

Linux (RHEL/CentOS/Fedora):

```bash
sudo dnf install cloudflared
```

Linux (Arch):

```bash
sudo pacman -S cloudflared
```

### 2. Authenticate cloudflared

Run:

```bash
cloudflared tunnel login
```

This opens a browser window where you can log in to your Cloudflare account and authorize the tunnel.

### 3. Create a tunnel

```bash
cloudflared tunnel create leaderboard-scraper
```

This creates a new tunnel and prints a tunnel ID. Keep that ID for later.

### 4. Configure a local ingress rule

Create a file named `config.yml` in the project folder (or use a Cloudflare config file in your home directory) with content like this:

```yaml
tunnel: YOUR_TUNNEL_ID
credentials-file: ~/.cloudflared/YOUR_TUNNEL_ID.json

ingress:
    - hostname: leaderboard-scraper.example.com
      service: http://localhost:5000
    - service: http://localhost:8080
```

Replace:

- `YOUR_TUNNEL_ID` with the tunnel ID from the previous step
- `leaderboard-scraper.example.com` with your own hostname that you control in Cloudflare

### 5. Create a DNS record in Cloudflare

If you want a custom domain, run:

```bash
cloudflared tunnel route dns leaderboard-scraper leaderboard-scraper.example.com
```

Replace the hostname with your real domain name.

### 6. Start the tunnel

In a separate terminal, start the Python app IF IT IS NOT ALREADY RUNNING:

```bash
python app.py
```

(No need to run this if the app is already running.)

Then start the tunnel:

```bash
cloudflared tunnel run leaderboard-scraper
```

If you want to use the config file explicitly:

```bash
cloudflared --config config.yml tunnel run
```

Once it is running, Cloudflare will proxy traffic to your local app.

## Notes

- The scraper uses the public leaderboard URLs and may fail if those endpoints change or block requests.
- The app writes to `team_high_scores.json`, so it is best to keep that file in the project directory.
- If you expose the app publicly, consider protecting it with Cloudflare Access or another authentication layer.

## Troubleshooting

### Port already in use

If port `5000` is already occupied, stop the process using it or set a different port:

```bash
$env:PORT="5001"
python app.py
```

### Dependencies fail to install

Make sure you are using the virtual environment and that `pip` is up to date:

```bash
python -m pip install --upgrade pip
```

### Tunnel cannot connect

Check that:

- the Flask app is running locally
- the tunnel config points to `http://localhost:5000`
- your DNS hostname is correctly configured in Cloudflare
