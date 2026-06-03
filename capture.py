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
QUOTE_START_URL   = os.environ.get("QUOTE_START_URL", "https://quote.staysure.co.uk/")
RENEWAL_LOGIN_URL = os.environ.get("RENEWAL_LOGIN_URL", "https://example.com/login")
USERNAME          = os.environ.get("PORTAL_USERNAME", "")
PASSWORD          = os.environ.get("PORTAL_PASSWORD", "")

# Travel start date is generated ~30 days ahead every run, so it never
# becomes a past (invalid) date. Format matches what the site expects.
TRAVEL_START = (dt.date.today() + dt.timedelta(days=30)).strftime("%d/%m/%Y")

VIEWPORT    = {"width": 1440, "height": 900}
OUTPUT_ROOT = Path("screenshots")

# Set HEADED=1 to watch the browser work (useful for debugging a stuck step).
HEADED = os.environ.get("HEADED") == "1"
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
            self.page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass
        self.page.wait_for_timeout(800)
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


def goto_with_retry(page, url, attempts=3, pause_ms=6000):
    """Open a URL, retrying a few times if the connection is reset/refused."""
    for i in range(1, attempts + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return
        except Exception as e:
            print(f"  connection attempt {i} of {attempts} failed: {e}")
            if i == attempts:
                raise
            page.wait_for_timeout(pause_ms)


# --------------------------------------------------------------------------
# THE PUBLIC QUOTE & BUY JOURNEY  (no login)
# Steps recorded from the live site; a screenshot is taken on arrival at
# each page (before filling it in), so you see the page as a customer does.
# --------------------------------------------------------------------------
def capture_quote_journey(shotter):
    page = shotter.page

    # Page 1 - Landing / trip type
    goto_with_retry(page, QUOTE_START_URL)
    page.get_by_role("button", name="Accept All Cookies").click()
    shotter.shot("Cover type", "quote")
    page.get_by_test_id("cover-type-buttons-group-2").click()
    shotter.shot("Cover type filled", "quote")
    page.get_by_test_id("cover-type-footer-page-submit-button").click()

    # Page 2 - Travelling to
    shotter.shot("Travelling to", "quote")
    page.get_by_test_id("to-location-buttons-group-3").click()
    page.get_by_test_id("worldwide-location-buttons-group-2").click()
    shotter.shot("Travelling to filled", "quote")
    page.get_by_test_id("travelling-to-page-submit-button").click()

    # Page 3 - Cruise question
    shotter.shot("Cruise", "quote")
    page.get_by_test_id("cruise-buttons-group-2").click()
    shotter.shot("Cruise filled", "quote")
    page.get_by_test_id("cruise-page-submit-button").click()

    # Page 4 - Travel dates
    shotter.shot("Travel dates", "quote")
    page.get_by_role("textbox", name="From").click()
    page.get_by_role("textbox", name="From").fill(TRAVEL_START)
    shotter.shot("Travel dates filled", "quote")
    page.get_by_test_id("travel-dates-page-submit-button").click()

    # Page 5 - Cover for
    shotter.shot("Cover for", "quote")
    page.get_by_test_id("party-type-buttons-group-INDIVIDUAL").click()
    shotter.shot("Cover for filled", "quote")
    page.get_by_test_id("cover-for-footer-page-submit-button").click()

    # Page 6 - Organiser
    shotter.shot("Organiser", "quote")
    page.get_by_test_id("personal-status-dropdown").click()
    page.get_by_role("option", name="Ms", exact=True).click()   # exact=True so it matches one option only
    page.get_by_test_id("first-name-organiser-input").click()
    page.get_by_test_id("first-name-organiser-input").fill("test")
    page.get_by_test_id("last-name-organiser-input").click()
    page.get_by_test_id("last-name-organiser-input").fill("test")
    page.get_by_test_id("scrollableInput-input").click()
    page.get_by_test_id("scrollableInput-input").fill("midsummer")
    page.get_by_role("button", name="Midsummer House, Forden").click()
    page.locator("#scrollableInput").click()
    page.get_by_test_id("day-input").fill("09")
    page.get_by_test_id("month-input").fill("09")
    page.get_by_test_id("year-input").fill("1990")
    page.get_by_test_id("organiser-main-buttons-group-1").click()
    page.get_by_test_id("organiser-buttons-group-2").click()
    shotter.shot("Organiser filled", "quote")
    page.get_by_test_id("organiser-page-submit-button").click()

    # Page 7 - Medical confirmation
    shotter.shot("Medical confirmation", "quote")
    page.get_by_test_id("medical-confirmation-buttons-group-2").click()
    page.get_by_test_id("undiagnosed-medical-confirmation-buttons-group-2").click()
    shotter.shot("Medical confirmation filled", "quote")
    page.get_by_test_id("medical-confirmation-page-submit-button").click()

    # Page 8 - Medical treatments
    shotter.shot("Medical treatments", "quote")
    page.get_by_test_id("medical-treatments-buttons-group-2").click()
    shotter.shot("Medical treatments filled", "quote")
    page.get_by_test_id("medical-treatments-page-submit-button").click()

    # Page 9 - Contact details
    shotter.shot("Contact details", "quote")
    # No .click() here: on this page the field labels sit over the inputs and
    # intercept clicks. fill() types into the field directly, avoiding that.
    page.get_by_test_id("contact-email-input").fill("test@gmail.com")
    page.get_by_test_id("contact-mobile-input").fill("03303334444")
    shotter.shot("Contact details filled", "quote")
    page.get_by_test_id("contact-details-footer-page-submit-button").click()

    # Page 10 - Quote
    shotter.shot("Quote", "quote")
    page.get_by_test_id("cover-level-selection-1-card-select-button").click()
    page.locator("#toggle-button-label-6").click()
    shotter.shot("Quote filled", "quote")
    page.get_by_test_id("quote-submit-button").click()

    # Page 11 - Quote review (nothing to fill here)
    shotter.shot("Quote review", "quote")

    # The payment screen. Reaching it does NOT buy anything (no card details
    # are entered). Delete these two lines if you'd rather stop at the review.
    page.get_by_role("button", name="Pay now").click()
    shotter.shot("Payment", "quote")


# --------------------------------------------------------------------------
# THE RENEWALS JOURNEY  (requires login) - we'll fill this in next
# --------------------------------------------------------------------------
def capture_renewals_journey(shotter):
    page = shotter.page
    if not (USERNAME and PASSWORD):
        print("  skipping renewals: PORTAL_USERNAME / PORTAL_PASSWORD not set")
        return

    page.goto(RENEWAL_LOGIN_URL, wait_until="domcontentloaded")
    shotter.shot("Login page", "renewal")
    # TODO: record the renewals login + screens the same way, paste here.


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
        browser = p.chromium.launch(
            headless=not HEADED,
            slow_mo=500 if HEADED else 0,  # slow down so you can watch each step
        )
        context = browser.new_context(
            viewport=VIEWPORT,
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        shotter = Shotter(page, RUN_DIR)

        print("Capturing quote & buy journey...")
        try:
            capture_quote_journey(shotter)
        except Exception as e:
            print(f"  quote journey error: {e}")
            # capture whatever page we got stuck on, so we can see why
            try:
                shotter.shot("STUCK - where it stopped", "quote")
            except Exception:
                pass

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
