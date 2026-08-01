#!/usr/bin/env python3
"""Inject the desktop phone-frame CSS into app/static/demo/index.html.

The Expo web export produces a bundle that expects the whole viewport to be
a phone-sized surface. On a desktop browser, the app therefore stretches to
1440+ px wide and the mountain ImageBackground fails to fill correctly.

To make the /demo page look like a mobile mockup on desktop (and remain
edge-to-edge on real phones), we inject a small `<style>` block into the
exported index.html that:

  * constrains #root to ~430px wide with a dark page background around it
    on viewports >= 640px (desktop / large tablet)
  * leaves phones alone (< 640px), so real mobile visitors get the full
    edge-to-edge app experience

Run after every `expo export -p web` copy step.
"""

from __future__ import annotations

from pathlib import Path

DEMO_INDEX = Path(__file__).resolve().parents[1] / "app" / "static" / "demo" / "index.html"

# Marker so re-running is idempotent.
MARKER = "/* injected-by-patch_demo_frame.py */"

FRAME_CSS = f"""<style id="mg-demo-frame">{MARKER}
  /* Dark page background around the phone frame, matches app navy. */
  html, body {{ background-color: #05090f; }}

  /* Desktop / wide tablet: render the app inside a phone-sized column. */
  @media (min-width: 640px) {{
    html {{ overflow: auto; }}
    body {{
      overflow: auto;
      min-height: 100%;
      display: flex;
      align-items: flex-start;
      justify-content: center;
      padding: 32px 16px;
      box-sizing: border-box;
    }}
    #root {{
      width: 100%;
      max-width: 430px;   /* iPhone 15 Pro logical width-ish */
      height: min(900px, calc(100vh - 64px));
      max-height: 900px;
      border-radius: 44px;
      overflow: hidden;
      box-shadow:
        0 30px 60px -20px rgba(0, 0, 0, 0.7),
        0 12px 24px -12px rgba(0, 0, 0, 0.5),
        0 0 0 8px #0b1220,          /* bezel */
        0 0 0 9px rgba(255,255,255,0.06); /* subtle bezel highlight */
      background-color: #0b1220;
      position: relative;
    }}
    /* Fix RN-Web ImageBackground: it hard-codes an inline width/height from
       the initial layout pass (~390px) and never resizes when the parent
       grows, leaving a strip of dark background on the right of the phone
       frame. Force the ImageBackground container (z-index: -1) and its
       inner background-image div + img fallback to fill their parent. */
    #root div[style*="z-index: -1"],
    #root div[style*="z-index: -1"] > div,
    #root div[style*="z-index: -1"] > img {{
      width: 100% !important;
      height: 100% !important;
      left: 0 !important;
      right: 0 !important;
      top: 0 !important;
      bottom: 0 !important;
    }}
  }}
</style>
"""

HYDRATE_SCRIPT = '<script type="module">globalThis.__EXPO_ROUTER_HYDRATE__=true;</script>'


def main() -> None:
    if not DEMO_INDEX.exists():
        raise SystemExit(
            f"index.html not found at {DEMO_INDEX}; did you run `expo export -p web` and copy dist/ into app/static/demo/?"
        )
    html = DEMO_INDEX.read_text(encoding="utf-8")

    if MARKER in html:
        print(f"already patched: {DEMO_INDEX}")
        return

    if HYDRATE_SCRIPT not in html:
        raise SystemExit(
            "could not find the Expo hydrate script marker in index.html; "
            "the export may have changed. Inspect the file and update this script."
        )

    # Inject just before the hydrate script so our CSS is parsed early but
    # AFTER the expo-reset style block (which sits in <head>).
    html = html.replace(HYDRATE_SCRIPT, FRAME_CSS + HYDRATE_SCRIPT, 1)
    DEMO_INDEX.write_text(html, encoding="utf-8")
    print(f"patched: {DEMO_INDEX}")


if __name__ == "__main__":
    main()
