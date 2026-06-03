# Weekly journey screenshotter

Automatically screenshots every page of your **Quote & Buy** journey (public)
and your **Renewals** screens (login required), then builds a browsable
catalogue. Runs weekly, entirely on free tools.

## What it produces

```
screenshots/
  catalogue.html          <- master index of every weekly run
  2026-06-01/
    index.html            <- thumbnail gallery for this run
    manifest.json         <- machine-readable list (order, label, url, time)
    01_quote_landing-page.png
    02_quote_your-details.png
    ...
```

Open `screenshots/catalogue.html` in a browser to browse everything.

## One-time setup

```bash
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env          # then edit .env with your URLs + login
```

## Record your real journey (the important bit)

The script ships with placeholder steps. To capture *your* pages, you map out
each step once. The easiest way is Playwright's recorder, which writes the
selectors for you as you click:

```bash
playwright codegen https://your-site.com/quote
```

Click through the journey; copy the generated `page.fill(...)` / `page.click(...)`
lines into the `capture_quote_journey()` function in `capture.py`, adding a
`shotter.shot("Page name", "quote")` after each page loads. Do the same for the
login + renewals flow in `capture_renewals_journey()`.

## Run it

```bash
# load .env then run (mac/Linux)
set -a; source .env; set +a
python capture.py
```

## Schedule it weekly — pick one (both free)

### Option A: GitHub Actions (recommended, runs in the cloud)
1. Push this folder to a GitHub repo.
2. In **Settings -> Secrets and variables -> Actions**:
   - add **secrets** `PORTAL_USERNAME`, `PORTAL_PASSWORD`
   - add **variables** `QUOTE_START_URL`, `RENEWAL_LOGIN_URL`
3. The workflow in `.github/workflows/` runs every Monday and commits the new
   screenshots back to the repo. Free for public repos and within the free
   minutes for private ones. (Optional: enable GitHub Pages to view the
   catalogue as a website.)

### Option B: Your own machine
- **mac/Linux** — `crontab -e`, then:
  ```
  0 6 * * 1 cd /path/to/journey-shots && /usr/bin/python3 capture.py
  ```
- **Windows** — Task Scheduler -> Create Task -> weekly trigger ->
  action runs `python C:\path\to\capture.py`.

## Notes
- Screenshots are full-page by default. Change `VIEWPORT` in `capture.py` for
  mobile sizes.
- Use a dedicated **test login** for renewals, never a real customer account.
- Keep credentials in `.env` / GitHub Secrets — never hard-code them.
