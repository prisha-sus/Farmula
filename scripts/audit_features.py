# -*- coding: utf-8 -*-
"""
End-to-end audit of all Day 1-3 features.
Outputs a clear PASS/FAIL report to console + writes to audit_report.md
"""
import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = "http://127.0.0.1:8001"
FRONTEND_URL = "http://127.0.0.1:5173"

results = []

def check(name: str, passed: bool, detail: str = ""):
    icon = "PASS" if passed else "FAIL"
    results.append({"name": name, "passed": passed, "detail": detail})
    print(f"[{icon}] {name}: {detail}")


# === DAY 1 — Multilingual i18n ===
print("\n=== DAY 1: MULTILINGUAL ===")

# Check translation files exist
for lang in ["en", "hi", "mr"]:
    path = Path(f"frontend/src/i18n/locales/{lang}.json")
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            required_sections = ["app", "auth", "nav", "dashboard", "parameters",
                                 "commodities", "alerts", "harvest", "trader"]
            missing = [s for s in required_sections if s not in data]
            if missing:
                check(f"Translation file {lang}.json complete", False,
                      f"Missing sections: {missing}")
            else:
                check(f"Translation file {lang}.json complete", True,
                      f"All {len(required_sections)} sections present")
        except Exception as e:
            check(f"Translation file {lang}.json valid JSON", False, str(e))
    else:
        check(f"Translation file {lang}.json exists", False, "File not found")

# Check i18n init file
i18n_init = Path("frontend/src/i18n/index.js")
check("i18n init file exists", i18n_init.exists(),
      "frontend/src/i18n/index.js" if i18n_init.exists() else "Missing")

# Check LanguageSwitcher component
lang_switcher = Path("frontend/src/components/LanguageSwitcher.jsx")
check("LanguageSwitcher component exists", lang_switcher.exists(), "")

# Check App.jsx uses useTranslation
app_jsx = Path("frontend/src/App.jsx").read_text(encoding="utf-8")
check("App.jsx imports useTranslation",
      "useTranslation" in app_jsx,
      "Found useTranslation import" if "useTranslation" in app_jsx else "Not found")
check("App.jsx uses t() function calls",
      app_jsx.count("t('") + app_jsx.count('t("') > 20,
      f"{app_jsx.count(chr(39)+')')+app_jsx.count(chr(34)+')')} translation calls found"
      .replace(")", "t(')", 1).replace(")", 't(")', 1))

# More precise count
t_single = app_jsx.count("t('")
t_double = app_jsx.count('t("')
total_t = t_single + t_double
check("App.jsx has sufficient t() calls",
      total_t > 20,
      f"{total_t} calls (t('...') + t(\"...\"))")


# === DAY 2 — SMS + Harvest + Trader ===
print("\n=== DAY 2: SMS / HARVEST / TRADER ===")

# Check sms_service.py exists
sms_service = Path("src/sms_service.py")
check("sms_service.py exists", sms_service.exists(), "")

# Check Fast2SMS key is configured
fast2sms_key = os.getenv("FAST2SMS_API_KEY")
check("FAST2SMS_API_KEY in .env", bool(fast2sms_key),
      f"Key present ({len(fast2sms_key or '')} chars)" if fast2sms_key else "Missing — SMS will not send")

# Check new components exist
for comp in ["HarvestRecommendation.jsx", "TraderCompare.jsx", "AlertsPanel.jsx"]:
    path = Path(f"frontend/src/components/{comp}")
    check(f"Component {comp} exists", path.exists(), "")

# Check backend endpoints are registered in main.py
main_py = Path("api/main.py").read_text(encoding="utf-8")
for route in ["/harvest/recommendation", "/trader/compare", "/alerts/list",
              "/alerts/subscribe", "/sms/test"]:
    check(f"Route {route} registered in main.py",
          route in main_py, "")

# Try to hit each backend endpoint (server must be running)
try:
    r = requests.get(f"{BACKEND_URL}/", timeout=5)
    backend_up = r.status_code == 200
    check("Backend is running on port 8001", backend_up,
          f"Status: {r.status_code}" if backend_up else "Cannot reach backend")
except Exception as e:
    backend_up = False
    check("Backend is running on port 8001", False, f"Connection failed: {e}")

if backend_up:
    # Test /harvest/recommendation
    try:
        r = requests.post(f"{BACKEND_URL}/harvest/recommendation",
                         json={"commodity": "potato", "district": "pune",
                               "horizon": 7, "language": "en"},
                         timeout=10)
        if r.status_code == 200:
            data = r.json()
            has_keys = all(k in data for k in ["recommendation", "today_price",
                                                "future_price_p50", "message"])
            check("/harvest/recommendation returns valid data", has_keys,
                  f"Recommendation: {data.get('recommendation')}, "
                  f"Today: Rs.{data.get('today_price')}")
        else:
            check("/harvest/recommendation works", False,
                  f"Status {r.status_code}: {r.text[:200]}")
    except Exception as e:
        check("/harvest/recommendation works", False, str(e)[:200])

    # Test /trader/compare
    try:
        r = requests.post(f"{BACKEND_URL}/trader/compare",
                         json={"commodity": "potato", "district": "pune",
                               "trader_offer": 1000},
                         timeout=10)
        if r.status_code == 200:
            data = r.json()
            check("/trader/compare returns valid data",
                  "verdict" in data and "mandi_average" in data,
                  f"Verdict: {data.get('verdict')}, "
                  f"Mandi avg: Rs.{data.get('mandi_average')}")
        else:
            check("/trader/compare works", False,
                  f"Status {r.status_code}: {r.text[:200]}")
    except Exception as e:
        check("/trader/compare works", False, str(e)[:200])

    # Test /alerts/list
    try:
        r = requests.get(f"{BACKEND_URL}/alerts/list",
                        params={"user_email": "test@audit.com"},
                        timeout=5)
        check("/alerts/list works", r.status_code == 200,
              f"Status {r.status_code}")
    except Exception as e:
        check("/alerts/list works", False, str(e)[:200])

    # Test /sms/test endpoint exists (without actually sending)
    try:
        r = requests.post(f"{BACKEND_URL}/sms/test", json={}, timeout=5)
        check("/sms/test endpoint registered", r.status_code != 404,
              f"Status {r.status_code} (404 means endpoint missing)")
    except Exception as e:
        check("/sms/test endpoint registered", False, str(e)[:200])


# === DAY 3 — Visual Identity + Mobile ===
print("\n=== DAY 3: VISUAL IDENTITY + MOBILE ===")

# Check theme files
theme_js = Path("frontend/src/theme/themes.js")
check("Theme system file exists", theme_js.exists(), "")

theme_provider = Path("frontend/src/theme/ThemeProvider.jsx")
check("ThemeProvider exists", theme_provider.exists(), "")

theme_preview = Path("frontend/src/ThemePreview.jsx")
check("ThemePreview exists", theme_preview.exists(), "")

# Check styles.css uses CSS variables
styles = Path("frontend/src/styles.css").read_text(encoding="utf-8")
var_count = styles.count("var(--theme-")
check("styles.css uses theme variables", var_count >= 10,
      f"{var_count} theme variable references found")

# Check responsive media queries exist
has_mobile_breakpoint = ("@media (max-width: 768px)" in styles
                        or "@media (max-width: 767px)" in styles)
check("Mobile breakpoint exists in styles.css", has_mobile_breakpoint, "")

# Check hamburger/mobile toolbar in App.jsx
check("Mobile toolbar (hamburger menu) in App.jsx",
      "mobile-toolbar" in app_jsx or "menu-toggle" in app_jsx,
      "Found mobile-toolbar/menu-toggle" if ("mobile-toolbar" in app_jsx or "menu-toggle" in app_jsx) else "Not found")

check("Sidebar overlay/drawer in App.jsx",
      "sidebarOpen" in app_jsx,
      "Found sidebarOpen state" if "sidebarOpen" in app_jsx else "Not found")

# Check animations in styles.css
check("fadeInUp animation defined",
      "fadeInUp" in styles, "")
check("shimmer skeleton animation defined",
      "shimmer" in styles, "")
check("pulse-soft animation defined",
      "pulse-soft" in styles, "")

# Check favicon
favicon = Path("frontend/public/favicon.svg")
check("Favicon SVG exists", favicon.exists(), "")

# Check index.html has favicon link
index_html = Path("frontend/index.html").read_text(encoding="utf-8")
check("index.html references favicon.svg",
      "favicon.svg" in index_html, "")
check("index.html has theme-color meta",
      "theme-color" in index_html, "")

# Check main.jsx wraps with ThemeProvider
main_jsx = Path("frontend/src/main.jsx").read_text(encoding="utf-8")
check("main.jsx wraps app with ThemeProvider",
      "ThemeProvider" in main_jsx, "")
check("main.jsx has /theme-preview route",
      "theme-preview" in main_jsx, "")


# === SUMMARY ===
print("\n=== SUMMARY ===")
total = len(results)
passed = sum(1 for r in results if r["passed"])
pct = passed * 100 // total if total else 0
print(f"\n{passed}/{total} checks passed ({pct}%)")
failed = [r for r in results if not r["passed"]]
if failed:
    print(f"\n{len(failed)} FAILURES:")
    for r in failed:
        print(f"  - {r['name']}: {r['detail']}")


# Write report to file
report_lines = [
    "# Farmula Audit Report\n\n",
    f"**Result: {passed}/{total} checks passed ({pct}%)**\n\n",
    "## Detailed Results\n\n",
]
for r in results:
    icon = "✅" if r["passed"] else "❌"
    report_lines.append(f"- {icon} **{r['name']}** — {r['detail']}\n")
Path("audit_report.md").write_text("".join(report_lines), encoding="utf-8")
print(f"\nFull report written to audit_report.md")
