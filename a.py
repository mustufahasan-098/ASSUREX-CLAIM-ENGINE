"""addcharts.py - installs the admin analytics charts (5 Chart.js panels).

Patches:
  1. templates/admin.html  -> CDN script + 5 chart canvases + chart scripts
     (replaces the manual bar-row "Final decisions" section)
  2. app.py                -> admin() route computes chart datasets

Safety: exact-anchor matching, backup, py_compile check, rollback on
failure. Idempotent. If an anchor doesn't match, prints the manual step
instead of guessing.
"""
import py_compile
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app.py"
ADMIN_HTML = ROOT / "templates" / "admin.html"

# ---------------------------------------------------------------- content
CHARTS_BLOCK = '''{{ ui.section("📊", "Claim analytics") }}
<div class="ax-grid-2">
  <div class="ax-card">
    <h4>🥧 Final decisions</h4>
    <canvas id="chartDecisions" height="220"></canvas>
  </div>
  <div class="ax-card">
    <h4>🏭 Claims by category</h4>
    <canvas id="chartCategories" height="220"></canvas>
  </div>
  <div class="ax-card">
    <h4>🛠️ Most reported faults</h4>
    <canvas id="chartFaults" height="220"></canvas>
  </div>
  <div class="ax-card">
    <h4>📈 Claims by day</h4>
    <canvas id="chartDays" height="220"></canvas>
  </div>
</div>

<div class="ax-card" style="margin-top:14px;">
  <h4>🎯 Rejection reasons (rule-engine intelligence)</h4>
  <canvas id="chartReject" height="160"></canvas>
</div>
'''

CHART_SCRIPTS = '''<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script>
// dark-theme defaults for every chart
Chart.defaults.color = '#A8B3C7';
Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
Chart.defaults.font.family = "'Inter', 'Segoe UI', sans-serif";
Chart.defaults.plugins.legend.labels.boxWidth = 14;
Chart.defaults.plugins.legend.labels.usePointStyle = true;

const gridOpts = { grid: { color: 'rgba(255,255,255,0.05)' } };

new Chart(document.getElementById('chartDecisions'), {
  type: 'doughnut',
  data: {
    labels: {{ chart_labels | tojson }},
    datasets: [{
      data: {{ chart_values | tojson }},
      backgroundColor: ['#3DDC97', '#FF6B6B', '#FFC24B'],
      borderColor: '#0D1220',
      borderWidth: 3,
      hoverOffset: 6
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    cutout: '62%',
    plugins: { legend: { position: 'right' } }
  }
});

new Chart(document.getElementById('chartCategories'), {
  type: 'bar',
  data: {
    labels: {{ category_labels | tojson }},
    datasets: [{
      data: {{ category_values | tojson }},
      backgroundColor: ['#6D8BFF', '#58D6D0', '#B197FC'],
      borderRadius: 8,
      maxBarThickness: 64
    }]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: { y: { beginAtZero: true, ticks: { precision: 0 }, ...gridOpts },
              x: ...gridOpts }
  }
});

new Chart(document.getElementById('chartFaults'), {
  type: 'bar',
  data: {
    labels: {{ fault_labels | tojson }},
    datasets: [{
      data: {{ fault_values | tojson }},
      backgroundColor: '#FFC24B',
      borderRadius: 8,
      maxBarThickness: 22
    }]
  },
  options: {
    indexAxis: 'y',
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false },
               title: { display: true, text: 'Top 8 fault categories',
                        color: '#68738A', font: { size: 11 } } },
    scales: { x: { beginAtZero: true, ticks: { precision: 0 }, ...gridOpts } }
  }
});

new Chart(document.getElementById('chartDays'), {
  type: 'line',
  data: {
    labels: {{ day_labels | tojson }},
    datasets: [{
      data: {{ day_values | tojson }},
      borderColor: '#6D8BFF',
      backgroundColor: 'rgba(109,139,255,0.14)',
      fill: true,
      tension: 0.35,
      pointBackgroundColor: '#8CA4FF',
      pointRadius: 3
    }]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: { y: { beginAtZero: true, ticks: { precision: 0 }, ...gridOpts },
              x: ...gridOpts }
  }
});

new Chart(document.getElementById('chartReject'), {
  type: 'bar',
  data: {
    labels: {{ reject_labels | tojson }},
    datasets: [{
      data: {{ reject_values | tojson }},
      backgroundColor: '#FF6B6B',
      borderRadius: 8,
      maxBarThickness: 40
    }]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: { y: { beginAtZero: true, ticks: { precision: 0 }, ...gridOpts },
              x: { ticks: { maxRotation: 30, autoSkip: false, font: { size: 10 } },
                  ...gridOpts } }
  }
});
</script>
'''

# app.py: insert chart computation before the admin render call.
# Anchor: the existing render call start for admin.html
APP_ANCHOR = '    return render_template(\n        "admin.html", empty=False'
APP_INSERT = '''    from collections import Counter
    chart_labels = ["Likely Valid", "Likely Invalid", "Manual Review"]
    chart_values = [by_final.get(l, 0) for l in chart_labels]

    cat_counts = Counter(c.get("product_category", "Other") for c in claims)
    category_labels = list(cat_counts.keys())
    category_values = list(cat_counts.values())

    fault_counts = Counter(c.get("fault_category", "unknown").replace("_", " ")
                           for c in claims).most_common(8)
    fault_labels = [f for f, _ in fault_counts] or ["none"]
    fault_values = [n for _, n in fault_counts] or [0]

    day_counts = Counter((c.get("created_at") or "")[:10] for c in claims
                         if (c.get("created_at") or "")[:10])
    days_sorted = sorted(day_counts)
    day_labels = [d[5:] for d in days_sorted] or ["none"]
    day_values = [day_counts[d] for d in days_sorted] or [0]

    reject_reasons = Counter()
    for c in claims:
        for hf in (c.get("rules_outcome", {}).get("hard_fails") or []):
            reject_reasons[hf.split("(")[0].strip()[:38]] += 1
    reject_sorted = reject_reasons.most_common(6)
    reject_labels = [r for r, _ in reject_sorted] or ["no rejections yet"]
    reject_values = [n for _, n in reject_sorted] or [0]

    return render_template(
        "admin.html", empty=False'''


def ok(msg):
    print(f"  [OK]      {msg}")


def skip(msg):
    print(f"  [SKIP]    {msg} (already present)")


def abort_note(step, detail):
    print(f"  [MANUAL]  {step}: {detail}")
    print("            Nothing was changed for this step.")


def main():
    print("=" * 64)
    print("ADMIN CHARTS INSTALLER")
    print("=" * 64)

    # ------------------------------------------------------ admin.html
    print("\n[1] templates/admin.html")
    if not ADMIN_HTML.exists():
        sys.exit("admin.html not found.")
    html = ADMIN_HTML.read_text(encoding="utf-8")
    html_changed = False

    if "chartDecisions" in html:
        skip("chart canvases")
    else:
        # replace the old manual decisions section if present
        old_section_start = '{{ ui.section("🥧", "Final decisions") }}'
        if old_section_start in html:
            # find the section's card end: the card div that follows it
            start = html.find(old_section_start)
            # the old block runs until the next {{ ui.section( or {% if
            end_candidates = [html.find("{{ ui.section(", start + 10),
                              html.find("{% if", start + 10)]
            end = min((e for e in end_candidates if e != -1),
                      default=start)
            if end > start:
                html = html[:start] + CHARTS_BLOCK + "\\n" + html[end:]
                html_changed = True
                ok("replaced old decisions section with chart block")
            else:
                abort_note("chart canvases",
                           "could not locate the end of the old decisions "
                           "section - replace it manually with the CHARTS "
                           "block from addcharts source")
        else:
            # no old section: insert before the disagreement section
            anchor = '{{ ui.section("🔀", "Model disagreement monitor") }}'
            if anchor in html:
                pos = html.find(anchor)
                html = html[:pos] + CHARTS_BLOCK + "\\n" + html[pos:]
                html_changed = True
                ok("chart block inserted before disagreement monitor")
            else:
                abort_note("chart canvases",
                           "no insertion anchor found - insert the CHARTS "
                           "block manually after the stats row")

    if "chart.umd.min.js" in html:
        skip("Chart.js CDN + scripts")
    else:
        if "{% endblock %}" in html:
            html = html.replace(
                "{% endblock %}",
                CHART_SCRIPTS + "\\n{% endblock %}", 1)
            html_changed = True
            ok("Chart.js CDN + chart scripts appended")
        else:
            abort_note("Chart.js scripts", "no {% endblock %} found")

    if html_changed:
        shutil.copy(ADMIN_HTML, ROOT / "templates" / "admin.html.bak")
        ADMIN_HTML.write_text(html, encoding="utf-8")
        ok("admin.html written (backup: admin.html.bak)")

    # ------------------------------------------------------------ app.py
    print("\n[2] app.py admin() chart data")
    content = APP.read_text(encoding="utf-8")

    if "chart_labels" in content:
        skip("chart datasets")
    else:
        n = content.count(APP_ANCHOR)
        if n == 0:
            abort_note(
                "chart datasets",
                "the admin render call does not match the expected anchor "
                "exactly (your app.py may differ). MANUAL STEP: in the "
                "admin() route, add the chart computation block from "
                "addcharts source just BEFORE 'return render_template("
                " \"admin.html\"...' and add the chart_* variables to that "
                "render call.")
        elif n > 1:
            abort_note("chart datasets",
                       f"{n} anchor matches (expected 1) - apply manually")
        else:
            backup = ROOT / "app.py.bak3"
            shutil.copy(APP, backup)
            content = content.replace(APP_ANCHOR, APP_INSERT, 1)
            APP.write_text(content, encoding="utf-8")
            try:
                py_compile.compile(str(APP), doraise=True)
                ok("chart datasets inserted - syntax OK (backup: app.py.bak3)")
            except py_compile.PyCompileError as e:
                shutil.copy(backup, APP)
                sys.exit(f"[ABORT] syntax check failed - backup restored.\n{e}")

    # ------------------------------------------------------ requirements
    print("\n[3] note")
    print("  Chart.js loads from CDN - no new pip packages needed.")
    print("  Internet required for charts to render (app itself works "
          "without it).")

    print("\n" + "=" * 64)
    print("DONE. Next:")
    print("  1. Restart Flask:  Ctrl+C -> python app.py")
    print("  2. Login admin@assurex.com -> Admin Analytics")
    print("  3. Expect: doughnut + 2 bars + line + rejection-reasons chart")
    print("  4. If a [MANUAL] step was printed above, do that one edit,")
    print("     then restart.")
    print("=" * 64)


if __name__ == "__main__":
    main()