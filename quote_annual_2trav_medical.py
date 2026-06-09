"""
Quote & Buy journey screenshotter -- ANNUAL multi-trip, 2 travellers, with medical.

Walks the live Quote & Buy journey for this variant, taking two screenshots of
each page (empty on arrival, and filled in before Continue). On every page it
also reads Optimizely's on-page data layer and flags any page the visitor was
bucketed into an A/B test for.

Saves full-page screenshots into screenshots/quote/<date>/<variant>/, writes a
per-run index.html, and rebuilds screenshots/quote/catalogue.html linking every
run (across all variants).

Same structure as the other quote scripts -- only the journey steps and the
output folder differ. This variant adds a second traveller and a full medical
declaration (asthma + screening).
"""

import os
import re
import json
import html
import datetime as dt
from pathlib import Path
from playwright.sync_api import sync_playwright

# --------------------------------------------------------------------------
# Settings (override with environment variables)
# --------------------------------------------------------------------------
QUOTE_START_URL = os.environ.get("QUOTE_START_URL", "https://quote.staysure.co.uk/")

# Which journey this file captures. Drives the output sub-folder name.
VARIANT = "annual-2trav-medical"

# Travel start date is generated ~30 days ahead every run, so it never becomes
# a past (invalid) date. Annual multi-trip only needs a start date.
TRAVEL_START = (dt.date.today() + dt.timedelta(days=30)).strftime("%d/%m/%Y")

VIEWPORT    = {"width": 1440, "height": 900}
OUTPUT_ROOT = Path("screenshots") / "quote"            # quote journeys live here
RUN_DATE    = dt.date.today().isoformat()
RUN_DIR     = OUTPUT_ROOT / RUN_DATE / VARIANT          # <date>/<variant>/

# Set HEADED=1 to watch the browser work (useful for debugging a stuck step).
HEADED = os.environ.get("HEADED") == "1"


# --------------------------------------------------------------------------
# Optimizely A/B test detection
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
    """Return a list of active Optimizely experiments/variations on this page."""
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
        """Take a full-page screenshot and record it in the manifest."""
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
        if experiments:
            tags = ", ".join(f"{e['experiment']} -> {e['variation']}" for e in experiments)
            print(f"  captured {filename}   [A/B: {tags}]")
        else:
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
# THE QUOTE & BUY JOURNEY -- ANNUAL, 2 travellers, with medical
# Steps taken from your codegen recording. A screenshot is taken on arrival at
# each page (before filling it in) and again once filled.
# --------------------------------------------------------------------------
def capture_quote_journey(shotter):
    page = shotter.page

    # Page 1 - Landing / trip type
    goto_with_retry(page, QUOTE_START_URL)
    page.get_by_role("button", name="Accept All Cookies").click()
    shotter.shot("Cover type", "quote")
    page.get_by_test_id("cover-type-buttons-group-2").click()   # group-2 = Annual multi-trip
    shotter.shot("Cover type filled", "quote")
    page.get_by_test_id("cover-type-footer-page-submit-button").click()

    # Page 2 - Travelling to (kept as recorded; has some back-and-forth)
    shotter.shot("Travelling to", "quote")
    page.get_by_test_id("to-location-buttons-group-1").click()
    page.get_by_test_id("confirm-button").click()
    page.get_by_test_id("to-location-buttons-group-2").click()
    page.get_by_test_id("to-location-buttons-group-3").click()
    page.get_by_test_id("worldwide-location-buttons-group-2").click()
    shotter.shot("Travelling to filled", "quote")
    page.get_by_test_id("travelling-to-page-submit-button").click()

    # Page 3 - Cruise question
    shotter.shot("Cruise", "quote")
    page.get_by_test_id("cruise-buttons-group-1").click()
    shotter.shot("Cruise filled", "quote")
    page.get_by_test_id("cruise-page-submit-button").click()

    # Page 4 - Travel dates (annual = start date only; proven 'From' box fill)
    shotter.shot("Travel dates", "quote")
    page.get_by_role("textbox", name="From").click()
    page.get_by_role("textbox", name="From").fill(TRAVEL_START)
    shotter.shot("Travel dates filled", "quote")
    page.get_by_test_id("travel-dates-page-submit-button").click()

    # Page 5 - Cover for
    shotter.shot("Cover for", "quote")
    page.get_by_test_id("party-type-buttons-group-COUPLE").click()   # COUPLE = 2 travellers
    shotter.shot("Cover for filled", "quote")
    page.get_by_test_id("cover-for-footer-page-submit-button").click()

    # Page 6 - Organiser (traveller 1)
    shotter.shot("Organiser", "quote")
    page.get_by_test_id("personal-status-dropdown").click()
    # robust selector (recorded react-aria id regenerates each load)
    page.get_by_role("option", name="Ms", exact=True).click()
    page.get_by_test_id("fist-name-scroll-id").click()
    page.get_by_test_id("first-name-organiser-input").fill("test")
    page.get_by_test_id("last-name-scroll-id").click()
    page.get_by_test_id("last-name-organiser-input").fill("test")
    page.get_by_test_id("scrollableInput-input").click()
    page.get_by_test_id("scrollableInput-input").fill("midsummer")
    page.get_by_role("button", name="Midsummer House, Forden").click()
    page.locator("#scrollableInput").click()
    page.get_by_test_id("day-input").fill("09")
    page.get_by_test_id("month-input").fill("09")
    page.get_by_test_id("year-input").fill("1990")
    page.get_by_test_id("organiser-main-buttons-group-1").click()
    shotter.shot("Organiser filled", "quote")
    page.get_by_test_id("organiser-page-submit-button").click()

    # Page 7 - Travellers (traveller 2)
    shotter.shot("Travellers", "quote")
    page.get_by_test_id("traveler-form-dropdown").click()
    page.get_by_role("option", name="Ms", exact=True).click()   # robust (was a react-aria id)
    page.get_by_test_id("traveller-first-name-1-input").click()
    page.get_by_test_id("traveller-first-name-1-input").fill("test two")
    page.get_by_test_id("traveller-last-name-1-1-input").click()
    page.get_by_test_id("traveller-last-name-1-1-input").fill("test")
    page.locator("#scrollableInput-0").click()
    page.get_by_test_id("traveller-form-day-0").fill("09")
    page.get_by_test_id("traveller-form-month-0").fill("09")
    page.get_by_test_id("traveller-form-year-0").fill("1990")
    page.get_by_test_id("traveller-buttons-group-2").click()
    shotter.shot("Travellers filled", "quote")
    page.get_by_test_id("travellers-page-submit-button").click()

    # Page 8 - Medical confirmation
    shotter.shot("Medical confirmation", "quote")
    page.get_by_test_id("medical-confirmation-buttons-group-2").click()
    page.get_by_test_id("undiagnosed-medical-confirmation-buttons-group-1").click()
    shotter.shot("Medical confirmation filled", "quote")
    page.get_by_test_id("medical-confirmation-page-submit-button").click()

    # Page 9 - Medical treatments
    shotter.shot("Medical treatments", "quote")
    page.get_by_test_id("medical-treatments-buttons-group-1").click()
    shotter.shot("Medical treatments filled", "quote")
    page.get_by_test_id("medical-treatments-page-submit-button").click()

    # Page 10 - Medical dashboard: declare a condition (asthma) and screen it
    shotter.shot("Medical dashboard", "quote")
    # The add button's id carries a per-session hash, so match it by prefix.
    page.locator('[data-testid^="medical-dashboard-add-button-"]').first.click()
    page.get_by_role("combobox", name="Search for a condition").click()
    page.get_by_placeholder("Search for a condition").fill("asthma")
    page.get_by_text("Asthma", exact=True).first.click()
    page.get_by_role("button", name="Start screening").click()

    # --- Asthma screening questionnaire -------------------------------------
    # NOTE: SAME screening as single-2trav-medical, which is not yet solved
    # (the condition wasn't getting added). Answers below are hardened (exact
    # matching, one extra "No" before Finish), but this will still need the
    # real fix once we can see the questions. If it stops here, the "STUCK"
    # screenshot shows which question it was on.
    def click_no():
        page.locator("label").filter(has_text=re.compile(r"^No$")).first.click()
        page.wait_for_timeout(400)

    click_no()
    page.locator("label").filter(has_text=re.compile(r"^3$")).first.click()
    page.wait_for_timeout(400)
    click_no()
    page.locator("label").filter(has_text=re.compile(r"^0$")).first.click()
    page.wait_for_timeout(400)
    click_no()
    click_no()
    # the "No" that tends to be missed just before finishing (harmless if the
    # questionnaire is already complete -- finds nothing and moves on)
    try:
        click_no()
    except Exception:
        pass

    page.get_by_role("button", name="Finish").click()
    page.wait_for_timeout(500)
    finish_again = page.get_by_role("button", name="Finish")
    if finish_again.count() > 0:
        try:
            finish_again.first.click()
        except Exception:
            pass
    # ------------------------------------------------------------------------

   
    shotter.shot("Medical dashboard filled", "quote")
    # Submit only enables once a condition has actually been saved onto the
    # dashboard. Wait for that rather than clicking a disabled button forever.
    submit = page.get_by_test_id("medical-dashboard-submit-button")
    try:
        page.wait_for_function(
            "() => { const b = document.querySelector("
            "'[data-testid=\\\"medical-dashboard-submit-button\\\"]');"
            " return b && !b.disabled; }",
            timeout=10000,
        )
    except Exception:
        raise RuntimeError(
            "medical dashboard Submit is still disabled -- the asthma condition "
            "was not added (the screening didn't complete). See the "
            "'Medical dashboard filled' screenshot."
        )
    submit.click()

    # Page 11 - Contact details
    shotter.shot("Contact details", "quote")
    # No .click() before .fill(): the field labels intercept the click.
    page.get_by_test_id("contact-email-input").fill("test@gmail.com")
    page.get_by_test_id("contact-mobile-input").fill("03332227777")
    shotter.shot("Contact details filled", "quote")
    page.get_by_test_id("contact-details-footer-page-submit-button").click()

    # Page 12 - Quote (annual offers a monthly payment toggle)
    shotter.shot("Quote", "quote")
    page.get_by_test_id("cover-level-selection-1-card-select-button").click()
    page.locator("#toggle-button-label-6").click()
    page.get_by_test_id("monthly-toggle-btn").click()
    shotter.shot("Quote filled", "quote")
    page.get_by_test_id("quote-submit-button").click()

    # Page 13 - Quote review (annual shows an auto-renewal preference)
    shotter.shot("Quote review", "quote")
    page.get_by_test_id("policy-renewal-expand-button").click()
    page.get_by_test_id("policy-renewal-buttons-group-1").click()
    shotter.shot("Quote review filled", "quote")

    # Payment screen. Reaching it does NOT buy anything (no card details are
    # entered). Delete these two lines if you'd rather stop at the review.
    page.get_by_role("button", name="Pay now").click()
    shotter.shot("Payment", "quote")


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
  .exp{display:block;font-size:11px;background:#3a2a12;color:#ffcf6b;
       border:1px solid #5c4418;border-radius:6px;padding:4px 8px;margin-top:2px}
  .exp b{color:#ffe3a3}
  .noexp{display:block;font-size:11px;color:#5fd98a;margin-top:2px}
  figure.has-exp{border-color:#5c4418}
  .summary{background:#3a2a12;color:#ffcf6b;border:1px solid #5c4418;
           border-radius:8px;padding:10px 14px;margin:0 32px 0;font-size:13px}
  ul.runs{list-style:none;padding:24px 32px;margin:0}
  ul.runs li{padding:12px 0;border-bottom:1px solid #262a33}
  a{color:#7aa7ff;text-decoration:none}
  a:hover{text-decoration:underline}
"""


def write_run_index(run_dir, manifest, run_date):
    cards = []
    ab_pages = 0
    for item in manifest:
        exps = item.get("experiments") or []
        exp_html = ""
        cls = ""
        if exps:
            ab_pages += 1
            cls = " has-exp"
            for e in exps:
                exp_html += (
                    '<span class="exp">&#9888; A/B test: '
                    f'<b>{html.escape(str(e["experiment"]))}</b> &rarr; '
                    f'{html.escape(str(e["variation"]))}</span>'
                )
        else:
            exp_html = '<span class="noexp">&#10003; No A/B test detected</span>'
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
    summary = (
        f"<div class='summary'>A/B check complete: {ab_pages} of {len(manifest)} "
        "screenshots were in an active A/B test"
        + (" &mdash; see the amber flags before using any as a baseline frame."
           if ab_pages else " &mdash; all pages were clean this run.")
        + "</div>"
    )
    doc = (
        "<!doctype html><meta charset='utf-8'>"
        f"<title>Journey screenshots {run_date} {html.escape(VARIANT)}</title>"
        "<style>" + PAGE_CSS + "</style>"
        "<header><h1>Journey screenshots</h1>"
        f"<div class='sub'>Run: {run_date} &middot; {html.escape(VARIANT)} &middot; "
        f"{len(manifest)} pages &middot; "
        "<a href='../../catalogue.html'>&larr; all runs</a></div></header>"
        + summary +
        "<div class='grid'>" + "".join(cards) + "</div>"
    )
    (run_dir / "index.html").write_text(doc, encoding="utf-8")


def _manifest_count(mf):
    try:
        return len(json.loads(mf.read_text()))
    except Exception:
        return 0


def write_master_catalogue():
    """Rebuild the top-level catalogue. Handles the new <date>/<variant>/ layout
    and still lists any older flat <date>/ runs so nothing drops off."""
    items = []
    run_count = 0
    date_dirs = sorted((p for p in OUTPUT_ROOT.iterdir() if p.is_dir()), reverse=True)
    for d in date_dirs:
        for v in sorted(x for x in d.iterdir() if x.is_dir()):
            mf = v / "manifest.json"
            if mf.exists():
                run_count += 1
                items.append(
                    f"<li><a href='{d.name}/{v.name}/index.html'>"
                    f"{d.name} &middot; {v.name}</a> "
                    f"&mdash; {_manifest_count(mf)} screenshots</li>"
                )
        mf = d / "manifest.json"
        if mf.exists():
            run_count += 1
            items.append(
                f"<li><a href='{d.name}/index.html'>{d.name}</a> "
                f"&mdash; {_manifest_count(mf)} screenshots</li>"
            )
    doc = (
        "<!doctype html><meta charset='utf-8'><title>Screenshot catalogue</title>"
        "<style>" + PAGE_CSS + "</style>"
        "<header><h1>Screenshot catalogue</h1>"
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

        print(f"Capturing quote & buy journey [{VARIANT}]...")
        try:
            capture_quote_journey(shotter)
        except Exception as e:
            print(f"  quote journey error: {e}")
            try:
                shotter.shot("STUCK - where it stopped", "quote")
            except Exception:
                pass

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
