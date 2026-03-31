#!/usr/bin/python3

import subprocess
import html
import base64
import os
import cgi
import tempfile
import zipfile
import shutil

CGI_DIR           = os.path.dirname(os.path.abspath(__file__))
JAR_PATH          = os.path.join(CGI_DIR, "predict.jar")
VALIDATE_JAR_PATH = os.path.join(CGI_DIR, "validateGor.jar")
DEFAULT_MODELS = {
    "gor1": os.path.join(CGI_DIR, "gor1default.txt"),
    "gor3": os.path.join(CGI_DIR, "gor3default.txt"),
    "gor4": os.path.join(CGI_DIR, "gor4default.txt"),
}


def render_score_plot(score_lines):

    if not score_lines:
        return ""

    length = max(len(v) for v in score_lines.values())

    html_out = "<div class='score-plot-line'>"

    # Offset = prob-label width
    html_out += "<span class='score-plot-offset'></span> "

    html_out += "<span class='score-plot-bars'>"

    for i in range(length):

        best = 0

        for raw in score_lines.values():

            if i < len(raw) and raw[i].isdigit():
                best = max(best, int(raw[i]))

        h = best * 6

        html_out += f"<span class='score-bar' style='height:{h}px'></span>"

    html_out += "</span></div>"

    # zweite Zeile mit Text
    html_out += (
        "<div style='font-size:0.8em;color:var(--bio-green);"
        "margin-left:3ch;'>Confidence plot</div>"
    )

    return html_out

# ── 1:1 aus run_predict.py ────────────────────────────────────────────
def get_cartoon_style(seq_str):
    mapping = {'H': '(', 'E': '>', 'C': '.', '-': ' '}
    result = ""
    for c in seq_str:
        upper_c = c.upper()
        symbol = mapping.get(upper_c, '.')
        if upper_c in "HEC":
            result += f'<span class="char-{upper_c}">{html.escape(symbol)}</span>'
        else:
            result += html.escape(symbol)
    return result



def get_cartoon_aligned(ps_line):
    if len(ps_line) >= 3:
        return "   " + get_cartoon_style(ps_line[3:])
    return "   " + get_cartoon_style(ps_line)


def run_gor5_predict(model_path, maf_dir, fmt, probabilities, show_scores=False):
    cmd = [
        "java", "-cp", JAR_PATH, "de.lmu.ifi.bio.gor.cli.Predict",
        "--model", model_path,
        "--maf",   maf_dir,
        "--format", fmt,
    ]
    if probabilities:
        cmd.append("--probabilities")
    if show_scores:
        cmd.append("--show-scores")
    try:
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, timeout=300)
    except Exception as e:
        return e


def run_validate(pred_path, ref_path, summary_path, detailed_path):
    cmd = [
        "java", "-jar", VALIDATE_JAR_PATH,
        "-p", pred_path,
        "-r", ref_path,
        "-f", "txt",
        "-s", summary_path,
        "-d", detailed_path,
    ]
    try:
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, timeout=300)
    except Exception as e:
        return e


def parse_summary_scores(summary_text):
    scores = {}
    for line in summary_text.splitlines():
        for key in ("q3", "SOV", "qObs_H", "qObs_E", "qObs_C", "SOV_H", "SOV_E", "SOV_C"):
            stripped = line.strip()
            if stripped.startswith(key + ":") or stripped.startswith(key + " "):
                parts = line.split("Mean:")
                if len(parts) > 1:
                    try:
                        scores[key] = float(parts[1].strip().split()[0])
                    except:
                        pass
    return scores


def extract_reference_from_aln_dir(aln_dir):
    """Extrahiert SS-Zeilen aus .aln-Dateien und baut eine seclib-Referenzdatei."""
    tmp_ref = tempfile.NamedTemporaryFile(suffix=".seclib", delete=False, mode='w')
    count = 0
    for fname in sorted(os.listdir(aln_dir)):
        if not fname.endswith(".aln"):
            continue
        fpath = os.path.join(aln_dir, fname)
        try:
            with open(fpath, "r") as f:
                lines = f.read().splitlines()
            protein_id = as_line = ss_line = None
            for line in lines:
                line = line.strip()
                if line.startswith(">"):
                    protein_id = line[1:].strip().split()[0]
                elif line.startswith("AS "):
                    as_line = line[3:].strip()
                elif line.startswith("SS "):
                    ss_line = line[3:].strip()
            if protein_id and as_line and ss_line:
                tmp_ref.write(f"> {protein_id}\n")
                tmp_ref.write(f"AS {as_line}\n")
                tmp_ref.write(f"SS {ss_line}\n\n")
                count += 1
        except Exception:
            continue
    tmp_ref.close()
    return tmp_ref.name, count


# ── HTML – identisch zu run_predict.py, nur Titel angepasst ──────────
HTML_HEAD = """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GOR5 – Multiple Alignment Prediction</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bio-green: #0d6b5c; --bio-green-light: #d4ede8; --bio-green-pale: #e8f6f3;
            --bio-teal: #2a9d8f; --bio-dark: #0f2926; --bio-deep: #0a1f1c;
            --text: #1a2e2a; --text-muted: #4a6560; --card-bg: #ffffff; --border: #c5e0db;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: "DM Sans", system-ui, sans-serif;
            background: radial-gradient(circle at top right, #11594d, var(--bio-deep) 60%);
            color: var(--text);
            line-height: 1.6;
            min-height: 100vh;
        }
        body::before {
            content: "";
            position: fixed;
            inset: 0;
            background: linear-gradient(180deg, rgba(13,107,92,0.06) 0%, transparent 40%);
            pointer-events: none;
            z-index: 0;
        }
        .header {
            position: relative;
            background: transparent;
            color: #fff; padding: 40px 24px 48px; text-align: center; overflow: hidden;
        }
        .header::after { display: none; }
        .header-inner { position: relative; z-index: 1; }
        .header h1 { margin: 0 0 6px; font-size: 1.6rem; font-weight: 700; letter-spacing: 0.02em; }
        .header p  { margin: 0; opacity: 0.85; font-size: 0.95rem; }
        .hero-dots { display:flex; gap:8px; justify-content:center; margin-top:14px; }
        .hero-dots span { width:8px; height:8px; border-radius:50%; background:rgba(255,255,255,0.45); }
        .main { position:relative; z-index:1; max-width:900px; margin:-24px auto 0; padding:0 20px 56px; }
        .main-panel {
            background: linear-gradient(180deg, rgba(255,255,255,0.97) 0%, rgba(248,252,251,0.98) 100%);
            border-radius:20px; padding:36px 32px 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.25), 0 0 0 1px rgba(255,255,255,0.1) inset;
        }
        .card { background:var(--card-bg); border:1px solid var(--border); border-radius:14px;
                padding:24px 24px 20px; margin-bottom:20px; }
        .card-title { font-size:0.78em; font-weight:700; text-transform:uppercase;
                      letter-spacing:0.08em; color:var(--bio-green); margin-bottom:16px; }
        .tab-buttons { display:flex; gap:8px; margin-bottom:18px; }
        .tab-btn {
            flex:1; padding:9px 12px; border:2px solid var(--border); border-radius:10px;
            background:white; cursor:pointer; font-weight:600; font-size:0.88em;
            color:var(--bio-green); font-family:"DM Sans",sans-serif; transition:all 0.2s;
        }
        .tab-btn:hover  { border-color:var(--bio-teal); background:var(--bio-green-pale); }
        .tab-btn.active { border-color:var(--bio-green); background:var(--bio-green); color:white; }
        .tab-content { display:none; } .tab-content.active { display:block; }
        label { display:block; font-weight:600; font-size:0.9em; color:var(--text); margin-bottom:7px; }
        input[type="file"] {
            width:100%; padding:10px 13px; border:1.5px dashed var(--border); border-radius:10px;
            font-size:0.88em; font-family:"DM Sans",sans-serif; background:var(--bio-green-pale); cursor:pointer;
        }
        textarea {
            width:100%; padding:10px 13px; border:1.5px solid var(--border); border-radius:10px;
            font-size:0.88em; font-family:"JetBrains Mono",monospace; color:var(--text);
            background:var(--bio-green-pale); outline:none; resize:vertical; transition:border-color 0.2s;
        }
        textarea:focus { border-color:var(--bio-teal); background:white; }
        small { display:block; margin-top:6px; font-size:0.82em; color:var(--text-muted); }
        .checkbox-row { display:flex; align-items:center; gap:10px; }
        .checkbox-row input[type="checkbox"] { width:17px; height:17px; accent-color:var(--bio-green); cursor:pointer; }
        .checkbox-row label { margin:0; font-weight:500; cursor:pointer; font-size:0.93em; }
        .submit-btn {
            width:100%; padding:14px;
            background:linear-gradient(135deg, var(--bio-dark), var(--bio-green));
            color:white; border:none; border-radius:12px; font-size:1em; font-weight:700;
            font-family:"DM Sans",sans-serif; cursor:pointer; letter-spacing:0.03em;
            transition:opacity 0.2s; margin-top:5px;
        }
        .submit-btn:hover { opacity:0.88; }
        .status-msg { padding:13px 17px; border-radius:12px; margin:16px 0; font-size:0.93em; border-left:4px solid; }
        .error   { background:#fdf0ef; color:#8b2a22; border-color:#c0392b; }
        .success { background:var(--bio-green-pale); color:var(--bio-dark); border-color:var(--bio-green); }
        .info    { background:#eef5fb; color:#1a4d7a; border-color:#2980b9; }
        .result-title { font-weight:700; font-size:0.9em; color:var(--bio-green);
                        margin:20px 0 4px; text-transform:uppercase; letter-spacing:0.06em; }
        .download-btn {
            display:inline-block; background:linear-gradient(135deg, var(--bio-dark), var(--bio-green));
            color:white; padding:11px 22px; text-decoration:none; border-radius:10px;
            font-weight:700; font-size:0.92em; margin-top:14px; margin-right:8px; transition:opacity 0.2s;
        }
        .download-btn:hover { opacity:0.88; }
        .seq-block {
            background:#fff; border:1.5px solid var(--border); border-radius:14px;
            padding:20px 24px; margin-bottom:16px; font-family:"JetBrains Mono",monospace;
            font-size:0.88em; line-height:1.9; overflow-x:auto;
            box-shadow:0 2px 12px rgba(13,107,92,0.06);
        }
        .seq-block .seq-header {
            font-weight:700; color:var(--bio-green); font-size:0.95em;
            display:block; margin-bottom:6px;
        }
        .seq-block .seq-line { display:block; white-space:pre; }
        .seq-block .cartoon-line {
            display:block; white-space:pre; letter-spacing:0;
            color:#2a9d8f; font-size:1em; margin-top:0;
        }
        .prob-line { font-size:1em;}
        .prob-label { font-weight:normal; display:inline-block; width:2ch; }
        .prob-section-divider {
            display:block; border:none; border-top:1px dashed var(--border);
            margin:6px 0 4px;
        }
        .score-table { width:100%; border-collapse:collapse; margin-top:14px;
                       font-family:"JetBrains Mono",monospace; font-size:0.9em; }
        .score-table th { background:var(--bio-green); color:white; padding:10px 16px;
                          text-align:left; font-size:0.82em; letter-spacing:0.05em; }
        .score-table td { padding:9px 16px; border-bottom:1px solid var(--bio-green-light); }
        .score-table tr:last-child td { border-bottom:none; }
        .score-table tr:hover td { background:var(--bio-green-pale); }

	 .score-plot-line {
            display:block;
            white-space:pre;
            font-family:"JetBrains Mono", monospace;
            font-size:1em;
        }

        .score-plot-offset {
            display:inline-block;
            width:2ch;   
            color:var(--bio-green);
            font-weight:bold;
        }

        .score-plot-bars {
            display:inline-grid;
            grid-auto-flow:column;
            grid-auto-columns:1ch;   
            height:60px;
        }

        .score-bar {
            width:1ch;
            background:var(--bio-green);
            align-self:end;
        }



        .score-good { color:#0d6b5c; font-weight:700; }
        .score-mid  { color:#e07b00; font-weight:600; }
        .score-low  { color:#c0392b; font-weight:600; }
        .pagination { display:flex; gap:10px; margin:18px 0 10px; align-items:center; }
        .page-btn {
            padding:9px 20px; border:2px solid var(--border); border-radius:9px;
            background:white; cursor:pointer; font-weight:600; font-size:0.88em;
            color:var(--bio-green); font-family:"DM Sans",sans-serif; transition:all 0.2s;
        }
        .page-btn:hover:not(:disabled) { border-color:var(--bio-teal); background:var(--bio-green-pale); }
        .page-btn:disabled { opacity:0.35; cursor:default; }
        .page-info { font-size:0.88em; color:var(--text-muted); flex:1; text-align:center; font-weight:500; }
        footer { position:relative; z-index:1;
            background:linear-gradient(180deg, var(--bio-dark) 0%, var(--bio-deep) 100%);
            color:rgba(255,255,255,0.88); padding:22px 24px; font-size:0.88rem;
            text-align:center; border-top:1px solid rgba(13,107,92,0.4); margin-top:40px;
        }
        footer a { color:#9ae6d9; text-decoration:none; }
        footer a:hover { text-decoration:underline; }
        .info-icon {
            position:relative; display:inline-flex; align-items:center; justify-content:center;
            width:20px; height:20px; border-radius:50%; background:var(--bio-green);
            color:white; font-size:0.85em; font-weight:700; cursor:default;
            font-style:normal; flex-shrink:0; user-select:none;
        }
        .info-icon .tooltip {
            display:none; position:absolute; left:28px; top:50%; transform:translateY(-50%);
            background:#1a2e2a; color:#e8f6f3; padding:18px 20px; border-radius:12px;
            font-size:0.93em; font-weight:400; white-space:normal; z-index:100;
            box-shadow:0 6px 28px rgba(0,0,0,0.45); line-height:1.9;
            pointer-events:none; width:280px;
        }
        .info-icon .tooltip::before {
            content:""; position:absolute; right:100%; top:50%; transform:translateY(-50%);
            border:7px solid transparent; border-right-color:#1a2e2a;
        }
        .info-icon:hover .tooltip,
        .info-icon:focus .tooltip { display:block; }
        .char-H { color: #ba55d3; font-weight: bold; }
        .char-E { color: #1e90ff; font-weight: bold; }
        .char-C { color: #2e8b57; font-weight: bold; }
        .prob-filter {
            display:flex; gap:16px; align-items:center; flex-wrap:wrap;
            background:var(--bio-green-pale); border:1px solid var(--border);
            border-radius:10px; padding:10px 16px; margin:10px 0 14px;
            font-size:0.88em;
        }
        .prob-filter strong { color:var(--bio-green); margin-right:4px; }
        .prob-filter label { margin:0; font-weight:500; font-size:0.93em; cursor:pointer; display:flex; align-items:center; gap:6px; }
        .prob-filter input[type=checkbox] { width:15px; height:15px; accent-color:var(--bio-green); cursor:pointer; }
        .ph-color { color:#e63946; font-weight:700; }
        .pe-color { color:#f4a261; font-weight:700; }
        .pc-color { color:#457b9d; font-weight:700; }
    </style>
    <script>
        function switchModelTab(tabId) {
            document.querySelectorAll('.model-tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.model-tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById('model-tab-' + tabId).classList.add('active');
            document.getElementById('model-content-' + tabId).classList.add('active');
            document.getElementById('model_choice').value = tabId;
        }
        function switchRefTab(tabId) {
            document.querySelectorAll('.ref-tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.ref-tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById('ref-tab-' + tabId).classList.add('active');
            document.getElementById('ref-content-' + tabId).classList.add('active');
            document.getElementById('ref_mode').value = tabId;
        }
        var _currentPage = 1;
        function showPage(p) {
            var perPage = 5;
            var total   = document.querySelectorAll('.seq-block').length;
            var pages   = Math.ceil(total / perPage);
            if (p < 1 || p > pages) return;
            _currentPage = p;
            document.querySelectorAll('.seq-block').forEach(function(b, i) {
                b.style.display = (i >= (p-1)*perPage && i < p*perPage) ? 'block' : 'none';
            });
            var info = document.getElementById('page-info');
            if (info) info.textContent = 'Seite ' + p + ' von ' + pages + ' (' + total + ' Sequenzen)';
            document.getElementById('btn-prev').disabled = (p === 1);
            document.getElementById('btn-next').disabled = (p === pages);
        }
        function prevPage() { showPage(_currentPage - 1); }
        function nextPage() { showPage(_currentPage + 1); }
        function toggleProb(type) {
            var show = document.getElementById('show-p' + type).checked;
            document.querySelectorAll('.prob-row-' + type).forEach(function(el) {
                el.style.display = show ? 'block' : 'none';
            });
        }
    </script>
</head>
<body>
<header class="header">
    <div class="header-inner">
        <h1>GOR5 &ndash; Multiple Alignment Prediction</h1>
        <p>WS 2025/2026 <span>&middot;</span> Gruppe 17</p>
        <div class="hero-dots"><span></span><span></span><span></span></div>
    </div>
</header>
<main class="main">
<div class="main-panel">
"""

HTML_FORM = """
<form method="post" enctype="multipart/form-data">
    <input type="hidden" name="ref_mode"     id="ref_mode"     value="none">
    <input type="hidden" name="model_choice" id="model_choice" value="gor4">

    <!-- 1. ZIP-Archiv -->
    <div class="card">
        <div class="card-title">1. Alignment-Dateien hochladen</div>
        <label style="display:flex;align-items:center;gap:7px;">
            ZIP-Archiv mit .aln-Dateien
            <span class="info-icon" tabindex="0">&#9432;
                <span class="tooltip">
                    <strong>Erwartetes Format (.aln):</strong><br>
                    &gt;ProteinID<br>
                    AS ACDEFG...<br>
                    SS HHHCCC...<br><br>
                    Eine .aln-Datei pro Protein.<br>
                    Alle im ZIP verpacken.
                </span>
            </span>
        </label>
        <input type="file" name="maf_zip" accept=".zip">
        <small>Alle .aln-Dateien im ZIP werden als MSA-Eingabe verarbeitet.</small>
    </div>

    <!-- 2. Modell -->
    <div class="card">
        <div class="card-title">2. Modell wählen</div>
        <div class="tab-buttons">
            <button type="button" class="model-tab-btn tab-btn" id="model-tab-gor1"
                    onclick="switchModelTab('gor1')">GOR I</button>
            <button type="button" class="model-tab-btn tab-btn" id="model-tab-gor3"
                    onclick="switchModelTab('gor3')">GOR III</button>
            <button type="button" class="model-tab-btn tab-btn active" id="model-tab-gor4"
                    onclick="switchModelTab('gor4')">GOR IV</button>
            <button type="button" class="model-tab-btn tab-btn" id="model-tab-upload"
                    onclick="switchModelTab('upload')">Eigenes Modell</button>
        </div>
        <div class="model-tab-content tab-content" id="model-content-gor1">
            <small style="margin-top:0">GOR I &ndash; auf CB513 trainiert (Einzelresidue-Statistik).</small>
        </div>
        <div class="model-tab-content tab-content" id="model-content-gor3">
            <small style="margin-top:0">GOR III &ndash; auf CB513 trainiert (Paarkorrelationen).</small>
        </div>
        <div class="model-tab-content tab-content active" id="model-content-gor4">
            <small style="margin-top:0">GOR IV &ndash; auf CB513 trainiert (Direktionale Information, empfohlen).</small>
        </div>
        <div class="model-tab-content tab-content" id="model-content-upload">
            <label>Trainiertes GOR-Modell hochladen</label>
            <input type="file" name="model_file" accept=".txt,.model">
            <small>Modell-Datei aus dem Training-Tool (GOR I, III oder IV)</small>
        </div>
    </div>

    <!-- 3. Referenzstruktur (optional) -->
    <div class="card">
        <div class="card-title">3. Referenzstruktur (optional) &ndash; für Q3 &amp; SOV Scores</div>
        <div class="tab-buttons">
            <button type="button" class="ref-tab-btn tab-btn active" id="ref-tab-none"
                    onclick="switchRefTab('none')">Keine</button>
            <button type="button" class="ref-tab-btn tab-btn" id="ref-tab-auto"
                    onclick="switchRefTab('auto')">Aus ZIP (automatisch)</button>
            <button type="button" class="ref-tab-btn tab-btn" id="ref-tab-upload"
                    onclick="switchRefTab('upload')">Datei hochladen</button>
            <button type="button" class="ref-tab-btn tab-btn" id="ref-tab-text"
                    onclick="switchRefTab('text')">Text einfügen</button>
        </div>
        <div class="ref-tab-content tab-content active" id="ref-content-none">
            <small style="margin-top:0">Kein Vergleich &ndash; nur Vorhersage anzeigen.</small>
        </div>
        <div class="ref-tab-content tab-content" id="ref-content-auto">
            <small style="margin-top:0">Die <code>SS</code>-Zeilen werden automatisch aus den
            <code>.aln</code>-Dateien im ZIP als Referenz verwendet.</small>
        </div>
        <div class="ref-tab-content tab-content" id="ref-content-upload">
            <label>Referenz-Datei (.seclib)</label>
            <input type="file" name="ref_file" accept=".seclib,.txt">
            <small>Bekannte Sekundärstruktur im seclib-Format</small>
        </div>
        <div class="ref-tab-content tab-content" id="ref-content-text">
            <label>Referenz einfügen</label>
            <textarea name="ref_text" rows="5" placeholder="&gt; ProteinID&#10;AS ACDEFG...&#10;SS HHHCCC..."></textarea>
        </div>
    </div>

    <!-- 4. Optionen -->
    <div class="card">
        <div class="card-title">4. Optionen</div>
        <div class="checkbox-row" style="margin-bottom:12px">
            <input type="checkbox" name="probabilities" id="probabilities" value="1">
            <label for="probabilities">Benutze die Wahrscheinlichkeitsformel</label>
        </div>
        <div class="checkbox-row" style="margin-bottom:4px">
            <input type="checkbox" name="show_scores" id="show_scores" value="1">
            <label for="show_scores">Scores ausgeben (IH/IE/IC bzw. PH/PE/PC)
                <small style="display:inline;font-size:0.82em;color:var(--text-muted);font-weight:400;">
                    &ndash; Post-Processing wird deaktiviert
                </small>
            </label>
        </div>
    </div>

    <button type="submit" name="predict_action" class="submit-btn">GOR5 Vorhersage starten</button>
</form>
"""

HTML_FOOTER = """
</div>
</main>
<footer>
    ProgPrakt WS 2025/2026 &middot; Gruppe 17 &nbsp;|&nbsp;
    <a href="../index.html">&larr; Zurück zur Hauptseite</a>
</footer>
</body>
</html>
"""


def main():
    fs = cgi.FieldStorage()
    print("Content-Type: text/html; charset=utf-8\n")
    print(HTML_HEAD)
    print(HTML_FORM)

    if "predict_action" not in fs:
        print(HTML_FOOTER)
        return

    probabilities = fs.getvalue("probabilities") == "1"
    show_scores   = fs.getvalue("show_scores")   == "1"
    ref_mode      = fs.getvalue("ref_mode")      or "none"
    model_choice  = fs.getvalue("model_choice")  or "gor4"

    tmp_model   = None
    tmp_maf_dir = None
    tmp_ref     = None
    model_path  = None
    ref_path    = None
    error_msg   = None

    # ── Modell ───────────────────────────────────────────────────────
    if model_choice == "upload":
        if "model_file" in fs and fs["model_file"].filename:
            tmp_m = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
            tmp_m.write(fs["model_file"].file.read()); tmp_m.close()
            model_path = tmp_m.name; tmp_model = model_path
        else:
            error_msg = "Bitte ein Modell hochladen."
    else:
        default_path = DEFAULT_MODELS.get(model_choice)
        if default_path and os.path.exists(default_path):
            model_path = default_path
        else:
            error_msg = f"Default-Modell '{model_choice}' nicht gefunden. Bitte eigenes Modell hochladen."

    # ── ZIP entpacken ────────────────────────────────────────────────
    if not error_msg:
        if "maf_zip" in fs and fs["maf_zip"].filename:
            if not fs["maf_zip"].filename.lower().endswith(".zip"):
                error_msg = "Bitte eine ZIP-Datei hochladen."
            else:
                tmp_zip = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
                tmp_zip.write(fs["maf_zip"].file.read()); tmp_zip.close()
                tmp_maf_dir = tempfile.mkdtemp()
                try:
                    with zipfile.ZipFile(tmp_zip.name, 'r') as z:
                        aln_files = [f for f in z.namelist() if f.endswith(".aln")]
                        if not aln_files:
                            error_msg = "Keine .aln-Dateien im ZIP gefunden."
                        else:
                            z.extractall(tmp_maf_dir)
                except zipfile.BadZipFile:
                    error_msg = "Ungültige ZIP-Datei."
                finally:
                    os.unlink(tmp_zip.name)
        else:
            error_msg = "Bitte ein ZIP-Archiv mit .aln-Dateien hochladen."

    # ── Referenz ─────────────────────────────────────────────────────
    if not error_msg and ref_mode != "none":
        if ref_mode == "auto":
            pass  # wird nach maf_dir-Ermittlung gesetzt
        elif ref_mode == "upload":
            if "ref_file" in fs and fs["ref_file"].filename:
                tmp_r = tempfile.NamedTemporaryFile(suffix=".seclib", delete=False)
                tmp_r.write(fs["ref_file"].file.read()); tmp_r.close()
                ref_path = tmp_r.name; tmp_ref = ref_path
            else:
                error_msg = "Bitte eine Referenz-Datei hochladen."
        elif ref_mode == "text":
            ref_text = (fs.getvalue("ref_text") or "").strip()
            if not ref_text:
                error_msg = "Bitte Referenz-Inhalt einfügen."
            else:
                tmp_r = tempfile.NamedTemporaryFile(suffix=".seclib", delete=False, mode='w')
                tmp_r.write(ref_text); tmp_r.close()
                ref_path = tmp_r.name; tmp_ref = ref_path

    if error_msg:
        print(f"<div class='status-msg error'><strong>Fehler:</strong> {html.escape(error_msg)}</div>")
        if tmp_maf_dir and os.path.exists(tmp_maf_dir):
            shutil.rmtree(tmp_maf_dir, ignore_errors=True)
        print(HTML_FOOTER)
        return

    # ── .aln-Verzeichnis finden ──────────────────────────────────────
    maf_dir = tmp_maf_dir
    for root, dirs, files in os.walk(tmp_maf_dir):
        if any(f.endswith(".aln") for f in files):
            maf_dir = root
            break

    # ── Referenz aus .aln automatisch ───────────────────────────────
    if ref_mode == "auto":
        ref_path, ref_count = extract_reference_from_aln_dir(maf_dir)
        tmp_ref = ref_path
        if ref_count == 0:
            print("<div class='status-msg info'>Keine SS-Zeilen in den .aln-Dateien &ndash; Validierung übersprungen.</div>")
            ref_path = None
        else:
            print(f"<div class='status-msg info'>Referenz aus <strong>{ref_count}</strong> .aln-Datei(en) automatisch extrahiert.</div>")

    # ── Vorhersage ───────────────────────────────────────────────────
    res_txt = run_gor5_predict(model_path, maf_dir, "txt", probabilities, show_scores)

    if not isinstance(res_txt, subprocess.CompletedProcess):
        print(f"<div class='status-msg error'><strong>Systemfehler:</strong> {html.escape(str(res_txt))}</div>")
        print(HTML_FOOTER)
        return

    if res_txt.returncode != 0 or not res_txt.stdout.strip():
        stderr = res_txt.stderr
        if "loadModel" in stderr or "NumberFormatException" in stderr or "NoSuchElementException" in stderr:
            msg = "Ungültiges Modell."
        elif "IOException" in stderr:
            msg = "Fehler beim Lesen der Eingabedatei."
        elif not res_txt.stdout.strip():
            msg = "Keine Ausgabe &ndash; .aln-Dateien und Modell prüfen."
        else:
            msg = f"Fehler bei der Vorhersage.<br><small style='font-family:monospace'>{html.escape(stderr[:300])}</small>"
        print(f"<div class='status-msg error'><strong>Fehler:</strong> {msg}</div>")
        print(HTML_FOOTER)
        return

    print("<div class='status-msg success'><strong>Vorhersage erfolgreich!</strong></div>")

    # ── Blöcke aufteilen ─────────────────────────────────────────────
    blocks = []
    current = []
    for line in res_txt.stdout.splitlines():
        if line.startswith(">"):
            if current:
                blocks.append(current)
            current = [line]
        else:
            if line.strip():
                current.append(line)
    if current:
        blocks.append(current)

    total     = len(blocks)
    per_page  = 5
    num_pages = max(1, (total + per_page - 1) // per_page)

    print("<div class='result-title'>Vorhersage:</div>")

    if num_pages > 1:
        print("<div class='pagination'>")
        print("<button class='page-btn' id='btn-prev' onclick='prevPage()' disabled>&#9664; Zurück</button>")
        print(f"<span class='page-info' id='page-info'>Seite 1 von {num_pages} ({total} Sequenzen)</span>")
        next_disabled = " disabled" if num_pages == 1 else ""
        print(f"<button class='page-btn' id='btn-next' onclick='nextPage()'{next_disabled}>Weiter &#9654;</button>")
        print("</div>")

    # ── Block-Rendering: 1:1 aus run_predict.py ──────────────────────
    for i, block in enumerate(blocks):
        display = "block" if i < per_page else "none"
        header  = block[0]

        print(f"<div class='seq-block' style='display:{display}'>")
        print(f"<span class='seq-header'>{html.escape(header)}</span>")

        score_lines    = {}
        current_ps_seq = ""

        def flush_score_lines():
            if not score_lines:
                return

            rows = {lbl: raw for lbl, raw in score_lines.items()}

            for lbl, raw in rows.items():
                target_char = lbl[-1]

                out  = f'<span class="seq-line prob-line prob-row-{target_char}">'
                out += f'<span class="prob-label">{html.escape(lbl)}</span> '

                for pos, ch in enumerate(raw):
                    is_predicted = (
                        pos < len(current_ps_seq)
                        and current_ps_seq[pos] == target_char
                    )

                    if ch.isdigit() and is_predicted:
                        out += f'<span style="color:#c0392b; font-weight:bold;">{ch}</span>'
                    else:
                        out += html.escape(ch)

                out += '</span>'
                print(out)

    # ✅ HIER plot einfügen
            print(render_score_plot(score_lines))

            score_lines.clear()

        has_prob_above = False

        # Erster Durchlauf: PS-Zeile merken
        for line in block[1:]:
            if line.startswith("PS "):
                current_ps_seq = line[3:]

        # Zweiter Durchlauf: Rendern
        for line in block[1:]:
            prefix = line[:3]

            if prefix in ("PH ", "PE ", "PC ", "IH ", "IE ", "IC "):
                has_prob_above = True
                lbl = prefix.strip()
                score_lines[lbl] = line[3:]
            else:
                flush_score_lines()

                if line.startswith("PS "):
                    if has_prob_above:
                        print("<hr class='prob-section-divider'>")
                        has_prob_above = False

                    # Farbige PS-Zeile
                    seq_part   = line[3:]
                    colored_ps = "PS "
                    for char in seq_part:
                        up_char = char.upper()
                        cls = f"char-{up_char}" if up_char in "HEC" else ""
                        if cls:
                            colored_ps += f'<span class="{cls}">{html.escape(char)}</span>'
                        else:
                            colored_ps += html.escape(char)
                    print(f"<span class='seq-line'>{colored_ps}</span>")

                    # Cartoon-Zeile (kein html.escape – bereits HTML)
                    cartoon_html = get_cartoon_aligned(line)
                    print(f"<span class='cartoon-line'>{cartoon_html}</span>")
                else:
                    print(f"<span class='seq-line'>{html.escape(line)}</span>")

        flush_score_lines()
        print("</div>")

    # ── Download ─────────────────────────────────────────────────────
    b64 = base64.b64encode(res_txt.stdout.encode()).decode()
    print(f'<a href="data:text/plain;base64,{b64}" download="gor5_prediction.txt" class="download-btn">&#11015; gor5_prediction.txt herunterladen</a>')

    # ── Validierung ──────────────────────────────────────────────────
    if ref_path:
        def normalize_prd(text):
            lines = []
            for line in text.splitlines():
                if line.startswith(">"):
                    lines.append("> " + line[1:].strip().split()[0])
                elif line.startswith("PS "):
                    lines.append("PS " + line[3:].replace("-", "C"))
                else:
                    lines.append(line)
            return "\n".join(lines) + "\n"

        tmp_prd = tempfile.NamedTemporaryFile(suffix=".prd", delete=False, mode='w')
        tmp_prd.write(normalize_prd(res_txt.stdout)); tmp_prd.close()
        tmp_sum = tempfile.NamedTemporaryFile(suffix=".sum", delete=False); tmp_sum.close()
        tmp_det = tempfile.NamedTemporaryFile(suffix=".evl", delete=False); tmp_det.close()

        val_res = run_validate(tmp_prd.name, ref_path, tmp_sum.name, tmp_det.name)

        if isinstance(val_res, subprocess.CompletedProcess) and val_res.returncode == 0:
            print("<div class='result-title'>Validierungsscores:</div>")

            if os.path.exists(tmp_sum.name) and os.path.getsize(tmp_sum.name) > 0:
                with open(tmp_sum.name) as f:
                    summary_txt = f.read()
                scores = parse_summary_scores(summary_txt)

                def score_class(v):
                    if v >= 65: return "score-good"
                    if v >= 50: return "score-mid"
                    return "score-low"

                metrics = [
                    ("Q3 (gesamt)", "q3"), ("SOV (gesamt)", "SOV"),
                    ("Q_H (Helix)", "qObs_H"), ("Q_E (Strang)", "qObs_E"), ("Q_C (Coil)", "qObs_C"),
                    ("SOV_H", "SOV_H"), ("SOV_E", "SOV_E"), ("SOV_C", "SOV_C"),
                ]
                print("<table class='score-table'>")
                print("<tr><th>Metrik</th><th>Wert</th></tr>")
                for name, key in metrics:
                    val = scores.get(key)
                    if val is not None:
                        print(f"<tr><td>{name}</td><td class='{score_class(val)}'>{val:.1f}%</td></tr>")
                print("</table>")

                b64s = base64.b64encode(summary_txt.encode()).decode()
                print(f'<a href="data:text/plain;base64,{b64s}" download="validation_summary.txt" class="download-btn">&#11015; Summary</a>')

            if os.path.exists(tmp_det.name) and os.path.getsize(tmp_det.name) > 0:
                with open(tmp_det.name) as f:
                    det_txt = f.read()
                b64d = base64.b64encode(det_txt.encode()).decode()
                print(f'<a href="data:text/plain;base64,{b64d}" download="validation_detailed.txt" class="download-btn">&#11015; Details</a>')
        else:
            print("<div class='status-msg info'>Validierung nicht möglich &ndash; Formate prüfen.</div>")

        for t in [tmp_prd.name, tmp_sum.name, tmp_det.name]:
            if os.path.exists(t): os.unlink(t)

    # ── Aufräumen ────────────────────────────────────────────────────
    if tmp_model and os.path.exists(tmp_model):
        os.unlink(tmp_model)
    if tmp_maf_dir and os.path.exists(tmp_maf_dir):
        shutil.rmtree(tmp_maf_dir, ignore_errors=True)
    if tmp_ref and os.path.exists(tmp_ref):
        os.unlink(tmp_ref)

    print(HTML_FOOTER)


if __name__ == "__main__":
    main()
