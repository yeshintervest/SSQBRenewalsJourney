"""
Weekly journey screenshotter.

Captures every page of:
  1. The public Quote & Buy journey (no login)
  2. The Renewals screens (requires login)

Saves full-page screenshots into screenshots/<date>/, writes a per-run
index.html, and rebuilds a master catalogue.html linking every weekly run.

Configure URLs/credentials via environment variables (see .env.example).
"""

import os
import json
import html
import datetime as dt
from pathlib import Path
from playwright.sync_api import sync_playwright

# --------------------------------------------------------------------------
# Settings (override with environment variables)
# --------------------------------------------------------------------------
QUOTE_START_URL   = os.environ.get("QUOTE_START_URL", "https://example.com/quote")
RENEWAL_LOGIN_URL = os.environ.get("RENEWAL_LOGIN_URL", "https://example.com/login")
USERNAME          = os.environ.get("PORTAL_USERNAME", "")
PASSWORD          = os.environ.get("PORTAL_PASSWORD", "")

VIEWPORT    = {"width": 1440, "height": 900}
OUTPUT_ROOT = Path("screenshots")
RUN_DATE    = dt.date.today().isoformat()
RUN_DIR     = OUTPUT_ROOT / RUN_DATE


# --------------------------------------------------------------------------
# Screenshot helper
# --------------------------------------------------------------------------
class Shotter:
    def __init__(self, page, run_dir):
        self.page = page
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.n = 0
        self.manifest = []

    def shot(self, label, section):
        """Take a full-page screenshot and record it in the manifest."""
        self.n += 1
        slug = label.lower().replace(" ", "-").replace("/", "-")
        filename = f"{self.n:02d}_{section}_{slug}.png"
        # let the page settle; don't hang forever on chatty sites
        try:
            self.page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        self.page.screenshot(path=str(self.run_dir / filename), full_page=True)
        self.manifest.append({
            "order": self.n,
            "section": section,
            "label": label,
            "file": filename,
            "url": self.page.url,
            "captured_at": dt.datetime.now().isoformat(timespec="seconds"),
        })
        print(f"  captured {filename}")


# --------------------------------------------------------------------------
# THE PUBLIC QUOTE & BUY JOURNEY  (no login)
# --------------------------------------------------------------------------
def capture_quote_journey(shotter):
    page = shotter.page
    page.goto(QUOTE_START_URL, wait_until="domcontentloaded")
    shotter.shot("Landing page", "quote")

    # ----------------------------------------------------------------------
    # TODO: replace the block below with YOUR real journey.
    # The pattern is always: act -> screenshot. One shot() per page.
    # Tip: run `playwright codegen <your-url>` to record clicks/typing and
    # have the selectors written for you, then paste them here.
    #
    # page.fill("#postcode", "SW1A 1AA")
    # page.click("button:has-text('Get a quote')")
    # shotter.shot("Your details", "quote")
    #
    # page.fill("#dob", "01/01/1990")
    # page.click("button:has-text('Continue')")
    # shotter.shot("Cover options", "quote")
    #
    # page.click("text=Buy now")
    # shotter.shot("Payment", "quote")
    # ----------------------------------------------------------------------


# --------------------------------------------------------------------------
# THE RENEWALS JOURNEY  (requires login)
# --------------------------------------------------------------------------
def capture_renewals_journey(shotter):
    page = shotter.page
    if not (USERNAME and PASSWORD):
        print("  skipping renewals: PORTAL_USERNAME / PORTAL_PASSWORD not set")
        return

    page.goto(RENEWAL_LOGIN_URL, wait_until="domcontentloaded")
    shotter.shot("Login page", "renewal")

    # ----------------------------------------------------------------------
    # TODO: replace these selectors with your real login form, then add a
    # shot() for each renewals screen you want to capture.
    #
    # page.fill("input[name='username']", USERNAME)
    # page.fill("input[name='password']", PASSWORD)
    # page.click("button[type='submit']")
    # page.wait_for_load_state("domcontentloaded")
    # shotter.shot("Dashboard", "renewal")
    #
    # page.click("text=My renewals")
    # shotter.shot("Renewal summary", "renewal")
    #
    # page.click("text=Renew now")
    # shotter.shot("Renewal quote", "renewal")
    # ----------------------------------------------------------------------


# --------------------------------------------------------------------------
# Catalogue generation
# --------------------------------------------------------------------------
PAGE_CSS = """
  body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
       margin:0;background:#0f1115;color:#e8eaed}
  header{padding:24px 32px;border-bottom:1px solid #262a33}
  h1{margin:0;font-size:20px}
  .sub{color:#9aa0aa;font-size:13px;margin-top:4px}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
        gap:20px;padding:24px 32px}
  figure{margin:0;background:#1a1d24;border:1px solid #262a33;border-radius:10px;
         overflow:hidden}
  figure img{width:100%;display:block;border-bottom:1px solid #262a33}
  figcaption{padding:12px 14px;display:flex;flex-direction:column;gap:4px}
  figcaption strong{font-size:14px}
  figcaption small{color:#7d828c;font-size:11px;word-break:break-all}
  .tag{display:inline-block;font-size:10px;text-transform:uppercase;
       letter-spacing:.5px;padding:2px 8px;border-radius:99px;width:fit-content}
  .tag.quote{background:#16331f;color:#5fd98a}
  .tag.renewal{background:#1c2740;color:#7aa7ff}
  ul.runs{list-style:none;padding:24px 32px;margin:0}
  ul.runs li{padding:12px 0;border-bottom:1px solid #262a33}
  a{color:#7aa7ff;text-decoration:none}
  a:hover{text-decoration:underline}
"""


def write_run_index(run_dir, manifest, run_date):
    cards = []
    for item in manifest:
        cards.append(
            '<figure>'
            f'<a href="{item["file"]}" target="_blank">'
            f'<img src="{item["file"]}" loading="lazy" alt="{html.escape(item["label"])}"></a>'
            '<figcaption>'
            f'<span class="tag {item["section"]}">{item["section"]}</span>'
            f'<strong>{item["order"]:02d}. {html.escape(item["label"])}</strong>'
            f'<small>{html.escape(item["url"])}</small>'
            '</figcaption></figure>'
        )
    doc = (
        "<!doctype html><meta charset='utf-8'>"
        f"<title>Journey screenshots {run_date}</title>"
        "<style>" + PAGE_CSS + "</style>"
        "<header><h1>Journey screenshots</h1>"
        f"<div class='sub'>Run: {run_date} &middot; {len(manifest)} pages &middot; "
        "<a href='../catalogue.html'>&larr; all runs</a></div></header>"
        "<div class='grid'>" + "".join(cards) + "</div>"
    )
    (run_dir / "index.html").write_text(doc, encoding="utf-8")


def write_master_catalogue():
    runs = sorted((p for p in OUTPUT_ROOT.iterdir() if p.is_dir()), reverse=True)
    items = []
    for r in runs:
        count = 0
        mf = r / "manifest.json"
        if mf.exists():
            try:
                count = len(json.loads(mf.read_text()))
            except Exception:
                pass
        items.append(
            f"<li><a href='{r.name}/index.html'>{r.name}</a> "
            f"&mdash; {count} screenshots</li>"
        )
    doc = (
        "<!doctype html><meta charset='utf-8'><title>Screenshot catalogue</title>"
        "<style>" + PAGE_CSS + "</style>"
        "<header><h1>Screenshot catalogue</h1>"
        f"<div class='sub'>{len(runs)} weekly runs</div></header>"
        "<ul class='runs'>" + "".join(items) + "</ul>"
    )
    (OUTPUT_ROOT / "catalogue.html").write_text(doc, encoding="utf-8")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    OUTPUT_ROOT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()
        shotter = Shotter(page, RUN_DIR)

        print("Capturing quote & buy journey...")
        try:
            capture_quote_journey(shotter)
        except Exception as e:
            print(f"  quote journey error: {e}")

        print("Capturing renewals journey...")
        try:
            capture_renewals_journey(shotter)
        except Exception as e:
            print(f"  renewals journey error: {e}")

        browser.close()

    (RUN_DIR / "manifest.json").write_text(
        json.dumps(shotter.manifest, indent=2), encoding="utf-8"
    )
    write_run_index(RUN_DIR, shotter.manifest, RUN_DATE)
    write_master_catalogue()
    print(f"\nDone. {len(shotter.manifest)} screenshots in {RUN_DIR}")
    print(f"Open {OUTPUT_ROOT / 'catalogue.html'} to browse.")


if __name__ == "__main__":
    main()
