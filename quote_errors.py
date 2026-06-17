"""
Quote & Buy ERROR-state screenshotter.

Follows ONE recorded walk through the journey (annual, 1 traveller), pausing to
screenshot the error / decision states along the way:
  - the Organiser page validation error (Continue pressed with the form empty)
  - the medical confirmation answer states (Medical 1 / Medical 2)
  - the medical-declaration outcome after the high-risk cancer answers

One browser, one pass. All screenshots go into screenshots/quote-errors/<date>/.
"""

import os
import re
import json
import html
import datetime as dt
from pathlib import Path
from playwright.sync_api import sync_playwright

# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------
QUOTE_START_URL = os.environ.get("QUOTE_START_URL", "https://quote.staysure.co.uk/")

VIEWPORT    = {"width": 1440, "height": 900}
OUTPUT_ROOT = Path("screenshots") / "quote-errors"
RUN_DATE    = dt.date.today().isoformat()
RUN_DIR     = OUTPUT_ROOT / RUN_DATE          # everything for a run lives here
HEADED      = os.environ.get("HEADED") == "1"


# --------------------------------------------------------------------------
# Optimizely A/B detection (so we can tell if an error page is under a test)
# --------------------------------------------------------------------------
OPTIMIZELY_PROBE = """
() => {
  try {
    if (!window.optimizely || typeof window.optimizely.get !== 'function') return [];
    const state = window.optimizely.get('state');
    const data  = window.optimizely.get('data') || {};
    if (!state || typeof state.getVariationMap !== 'function') return [];
    const vmap = state.getVariationMap();
    const out = [];
    Object.keys(vmap || {}).forEach(function (expId) {
      const v = vmap[expId] || {};
      const exp = (data.experiments && data.experiments[expId]) || {};
      out.push({
        experimentId: expId,
        experiment: exp.name || expId,
        variation: v.name || (v.id ? String(v.id) : 'unknown'),
        variationId: v.id || null
      });
    });
    return out;
  } catch (e) { return []; }
}
"""


def read_active_experiments(page):
    try:
        page.wait_for_function(
            "() => window.optimizely && typeof window.optimizely.get === 'function'",
            timeout=2500,
        )
    except Exception:
        return []
    try:
        return page.evaluate(OPTIMIZELY_PROBE) or []
    except Exception:
        return []


# --------------------------------------------------------------------------
class Shotter:
    def __init__(self, page, run_dir):
        self.page = page
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.n = 0
        self.manifest = []

    def shot(self, label, section):
        self.n += 1
        slug = label.lower().replace(" ", "-").replace("/", "-")
        filename = f"{self.n:02d}_{section}_{slug}.png"
        try:
            self.page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass
        self.page.wait_for_timeout(800)
        experiments = read_active_experiments(self.page)
        self.page.screenshot(path=str(self.run_dir / filename), full_page=True)
        self.manifest.append({
            "order": self.n,
            "section": section,
            "label": label,
            "file": filename,
            "url": self.page.url,
            "captured_at": dt.datetime.now().isoformat(timespec="seconds"),
            "experiments": experiments,
        })
        print(f"  captured {filename}")


def goto_with_retry(page, url, attempts=3, pause_ms=6000):
    for i in range(1, attempts + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return
        except Exception as e:
            print(f"  connection attempt {i} of {attempts} failed: {e}")
            if i == attempts:
                raise
            page.wait_for_timeout(pause_ms)


def _click_calendar_day(page, day):
    """Click a day-number cell; step the calendar forward a month if needed."""
    try:
        page.get_by_role("gridcell", name=str(day), exact=True).first.click(timeout=4000)
        return
    except Exception:
        pass
    for label in ["Next month", "Next Month", "Next", "\u203a", "\u00bb"]:
        nxt = page.get_by_role("button", name=label)
        if nxt.count() > 0:
            nxt.first.click()
            page.wait_for_timeout(400)
            break
    page.get_by_role("gridcell", name=str(day), exact=True).first.click(timeout=4000)


# --------------------------------------------------------------------------
# THE ERROR WALK -- one pass, screenshots at the marked points.
# This is your recorded flow; only the broken bits were fixed (curly quotes,
# the hard-coded calendar day, the hashed add-condition id, and .first on the
# screening answers so a duplicate label doesn't crash it).
# --------------------------------------------------------------------------
def capture_error_journey(shotter):
    page = shotter.page

    goto_with_retry(page, QUOTE_START_URL)
    page.get_by_role("button", name="Accept All Cookies").click()
    page.get_by_test_id("cover-type-buttons-group-2").click()
    page.get_by_test_id("cover-type-footer-page-submit-button").click()
    page.get_by_test_id("to-location-buttons-group-3").click()
    page.get_by_test_id("worldwide-location-buttons-group-1").click()
    page.get_by_test_id("travelling-to-page-submit-button").click()
    page.get_by_test_id("cruise-buttons-group-2").click()
    page.get_by_test_id("cruise-page-submit-button").click()

    # Travel dates -- calendar, dynamic future day (was hard-coded "27")
    page.get_by_role("button", name="calendar").click()
    _click_calendar_day(page, (dt.date.today() + dt.timedelta(days=10)).day)
    page.get_by_test_id("travel-dates-page-submit-button").click()

    page.get_by_test_id("party-type-buttons-group-INDIVIDUAL").click()
    page.get_by_test_id("cover-for-footer-page-submit-button").click()

    # --- Organiser: press Continue with the form EMPTY -> validation error
    page.get_by_test_id("organiser-page-submit-button").click()
    page.wait_for_timeout(1000)
    shotter.shot("Organiser validation error", "errors")

    # now fill it in and carry on
    page.get_by_test_id("personal-status-dropdown").click()
    page.get_by_role("option", name="Ms", exact=True).click()
    page.get_by_test_id("first-name-organiser-input").click()
    page.get_by_test_id("first-name-organiser-input").fill("test")
    page.get_by_test_id("last-name-organiser-input").click()
    page.get_by_test_id("last-name-organiser-input").fill("test")
    page.get_by_test_id("scrollableInput-input").click()
    page.get_by_test_id("scrollableInput-input").fill("midsummer")
    page.get_by_role("button", name="Midsummer House, Forden").click()
    page.get_by_test_id("year-input").click()
    page.get_by_test_id("day-input").fill("09")
    page.get_by_test_id("month-input").fill("09")
    page.get_by_test_id("year-input").fill("1990")
    page.get_by_test_id("organiser-main-buttons-group-1").click()
    page.get_by_test_id("organiser-buttons-group-2").click()
    page.get_by_test_id("organiser-page-submit-button").click()

    # --- Medical confirmation
    page.get_by_test_id("medical-confirmation-buttons-group-1").click()
    shotter.shot("Medical 1", "errors")
    page.get_by_test_id("medical-confirmation-buttons-group-2").click()
    page.get_by_test_id("undiagnosed-medical-confirmation-buttons-group-1").click()
    shotter.shot("Medical 2", "errors")
    page.get_by_test_id("undiagnosed-medical-confirmation-buttons-group-2").click()
    page.get_by_test_id("medical-confirmation-page-submit-button").click()

    page.get_by_test_id("medical-treatments-buttons-group-1").click()
    page.get_by_test_id("medical-treatments-page-submit-button").click()

    # add the cancer condition (id has a session hash -> match by prefix)
    page.locator('[data-testid^="medical-dashboard-add-button-"]').first.click()
    page.wait_for_timeout(800)
    # search exactly as you recorded: click, Enter, type, Enter, then the
    # "Search for a medical condition" button, then pick the condition.
    page.locator(".inline-flex.w-full.items-center.h-full").click()
    page.get_by_placeholder("Search for a condition").fill("cancer of")
    page.get_by_label("Cancer of boneCancer of the").get_by_text("Cancer of the bile duct").click()
    page.get_by_role("button", name="Start screening").click()
    page.locator("label").filter(has_text="Yes").click()
    page.locator("label").filter(has_text="Within the last 5 years").click()
    page.locator("label").filter(has_text="Chemotherapy tablets").click()
    page.locator("label").filter(has_text="Yes").click()
    page.locator("label").filter(has_text="There has been an increase in").click()
    page.locator("label").filter(has_text="Yes").click()
    page.locator("label").filter(has_text="Yes - all of the time").click()
    page.locator(".flex").first.click()
    page.get_by_role("button", name="Finish").click()
    page.goto("https://quote.staysure.co.uk/unable-to-quote/")

    page.wait_for_timeout(1500)
    shotter.shot("Unable to cover", "errors")
    


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
  .tag.errors{background:#3a1620;color:#ff9e9e}
  .exp{display:block;font-size:11px;background:#3a2a12;color:#ffcf6b;
       border:1px solid #5c4418;border-radius:6px;padding:4px 8px;margin-top:2px}
  .noexp{display:block;font-size:11px;color:#5fd98a;margin-top:2px}
  figure.has-exp{border-color:#5c4418}
  ul.runs{list-style:none;padding:24px 32px;margin:0}
  ul.runs li{padding:12px 0;border-bottom:1px solid #262a33}
  a{color:#7aa7ff;text-decoration:none}
  a:hover{text-decoration:underline}
"""


def write_run_index(run_dir, manifest, run_date):
    cards = []
    for item in manifest:
        exps = item.get("experiments") or []
        if exps:
            exp_html = ""
            for e in exps:
                exp_html += ('<span class="exp">&#9888; A/B test: '
                             f'<b>{html.escape(str(e["experiment"]))}</b> &rarr; '
                             f'{html.escape(str(e["variation"]))}</span>')
            cls = " has-exp"
        else:
            exp_html = '<span class="noexp">&#10003; No A/B test detected</span>'
            cls = ""
        cards.append(
            f'<figure class="card{cls}">'
            f'<a href="{item["file"]}" target="_blank">'
            f'<img src="{item["file"]}" loading="lazy" alt="{html.escape(item["label"])}"></a>'
            '<figcaption>'
            f'<span class="tag {item["section"]}">{item["section"]}</span>'
            f'<strong>{item["order"]:02d}. {html.escape(item["label"])}</strong>'
            f'<small>{html.escape(item["url"])}</small>'
            f'{exp_html}'
            '</figcaption></figure>'
        )
    doc = (
        "<!doctype html><meta charset='utf-8'>"
        f"<title>Error screenshots {run_date}</title>"
        "<style>" + PAGE_CSS + "</style>"
        "<header><h1>Error screenshots</h1>"
        f"<div class='sub'>{run_date} &middot; {len(manifest)} shots &middot; "
        "<a href='../catalogue.html'>&larr; all runs</a></div></header>"
        "<div class='grid'>" + "".join(cards) + "</div>"
    )
    (run_dir / "index.html").write_text(doc, encoding="utf-8")


def _manifest_count(mf):
    try:
        return len(json.loads(mf.read_text()))
    except Exception:
        return 0


def write_master_catalogue():
    items = []
    run_count = 0
    if OUTPUT_ROOT.exists():
        for d in sorted((p for p in OUTPUT_ROOT.iterdir() if p.is_dir()), reverse=True):
            mf = d / "manifest.json"
            if mf.exists():
                run_count += 1
                items.append(
                    f"<li><a href='{d.name}/index.html'>{d.name}</a> "
                    f"&mdash; {_manifest_count(mf)} shots</li>"
                )
    doc = (
        "<!doctype html><meta charset='utf-8'><title>Error catalogue</title>"
        "<style>" + PAGE_CSS + "</style>"
        "<header><h1>Error screenshot catalogue</h1>"
        f"<div class='sub'>{run_count} runs</div></header>"
        "<ul class='runs'>" + "".join(items) + "</ul>"
    )
    (OUTPUT_ROOT / "catalogue.html").write_text(doc, encoding="utf-8")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not HEADED,
            slow_mo=500 if HEADED else 0,
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

        print("Capturing error walk...")
        try:
            capture_error_journey(shotter)
        except Exception as e:
            print(f"  error walk stopped: {e}")
            try:
                shotter.shot("STUCK - where it stopped", "errors")
            except Exception:
                pass

        browser.close()

    (RUN_DIR / "manifest.json").write_text(
        json.dumps(shotter.manifest, indent=2), encoding="utf-8"
    )
    write_run_index(RUN_DIR, shotter.manifest, RUN_DATE)
    write_master_catalogue()
    print(f"\nDone. {len(shotter.manifest)} shots in {RUN_DIR}")
    print(f"Open {OUTPUT_ROOT / 'catalogue.html'} to browse.")


if __name__ == "__main__":
    main()
