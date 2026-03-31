#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CGI: Validation (validateAli). Erwartet POST mit alignment_pairs_file.
Gibt Text aus und optional HTML mit Tabelle und einfachen Balken (Plots).
"""
import os
import sys
import io
import cgi

# Damit Umlaute (ä, ü, ö) auf dem Server korrekt ankommen
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import cgitb
import subprocess
import tempfile
import shutil
import re
import traceback
import base64

try:
    from result_layout import print_result_start, print_result_end, extract_jar_body, RESULT_CSS
except ImportError:
    def print_result_start(title, back_url, back_label):
        print("Content-Type: text/html; charset=utf-8")
        print()
        print("<!DOCTYPE html><html><head><meta charset='utf-8'><title>%s</title></head><body>" % cgi.escape(title))
        print("<p><a href='%s'>%s</a></p>" % (cgi.escape(back_url), cgi.escape(back_label)))
    def print_result_end():
        print("</body></html>")
    def extract_jar_body(html_str):
        if not html_str:
            return ""
        start = html_str.find("<body>")
        end = html_str.rfind("</body>")
        if start >= 0 and end > start:
            return html_str[start + 6:end].strip()
        return html_str
    RESULT_CSS = ""

cgitb.enable()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
VALIDATE_JAR = os.path.join(BASE_DIR, "validateAli.jar")
ALIGNMENT_JAR = os.path.join(BASE_DIR, "alignment.jar")


def run_jar(jar_path, args, cwd, timeout=120):
    if not os.path.isfile(jar_path):
        return None, "JAR nicht gefunden: " + jar_path
    cmd = ["java", "-Xmx512M", "-jar", jar_path] + args
    try:
        r = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        out = (r.stdout or b"").decode("utf-8", errors="replace")
        err = (r.stderr or b"").decode("utf-8", errors="replace")
        if r.returncode != 0:
            return out + err, "Exit " + str(r.returncode)
        return out, None
    except subprocess.TimeoutExpired:
        return "", "Timeout"
    except Exception as e:
        return "", str(e)


def parse_validation_output(text):
    """Extrahiert pro Block: header, sens, spec, cov, mse, inv_mse. Letzte 5 Zahlen = sens, spec, cov, inv_mse, mse."""
    blocks = []
    lines = text.strip().split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(">"):
            parts = line[1:].strip().split()
            if len(parts) >= 5:
                try:
                    sens = float(parts[-5])
                    spec = float(parts[-4])
                    cov = float(parts[-3])
                    inv_mse = float(parts[-2])
                    mse = float(parts[-1])
                    header = (" ".join(parts[:-5]) if len(parts) > 5 else (parts[0] if parts else "")).strip() or "Block"
                    block_lines = [line]
                    for _ in range(4):
                        i += 1
                        if i < len(lines):
                            block_lines.append(lines[i])
                    blocks.append({
                        "header": header,
                        "sensitivity": sens,
                        "specificity": spec,
                        "coverage": cov,
                        "mse": mse,
                        "inv_mse": inv_mse,
                        "lines": block_lines,
                    })
                except (ValueError, IndexError):
                    pass
        i += 1
    return blocks


def make_download_link(filename, label, content, mime="text/plain;charset=utf-8"):
    if content is None:
        return ""
    if isinstance(content, str):
        content = content.encode("utf-8")
    href = "data:%s;base64,%s" % (mime, base64.b64encode(content).decode("ascii"))
    return "<a class='btn' download='%s' href='%s'>%s</a>" % (cgi.escape(filename), href, cgi.escape(label))


def result_page_html_document(title, body_html):
    return (
        "<!DOCTYPE html><html lang='de'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>" + cgi.escape(title) + "</title>"
        "<link rel='preconnect' href='https://fonts.googleapis.com'><link href='https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap' rel='stylesheet'>"
        "<style>" + RESULT_CSS + "</style></head><body>"
        "<header><div class='container'><a href='../index.html' class='logo'>Alignment &amp; Validation</a>"
        "<nav><a href='../alignment.html'>Alignment</a><a href='../validation.html'>Validation</a><a href='../tuning.html'>Parameter-Tuning</a><a href='../index.html'>Start</a></nav>"
        "</div></header><main class='container'><div class='result-content'>" + body_html + "</div></main></body></html>"
    )


def validation_csv(blocks):
    rows = ["header,sensitivity,specificity,f1,coverage,mse,inv_mse"]
    for b in blocks:
        def esc(v):
            s = str(v).replace('"', '""')
            return '"' + s + '"'
        f1 = _f1(b["sensitivity"], b["specificity"])
        rows.append(",".join([
            esc(b.get("header") or "Block"),
            esc("%.2f" % b["sensitivity"]),
            esc("%.2f" % b["specificity"]),
            esc("%.2f" % f1),
            esc("%.2f" % b["coverage"]),
            esc("%.2f" % b["mse"]),
            esc("%.2f" % b["inv_mse"]),
        ]))
    return "\n".join(rows) + "\n"


def validation_downloads_html(blocks, merged_ali, raw_text, html_content=None):
    return (
        "<div class='validate-box'><h3>Downloads</h3><p>Alle erzeugten Ergebnisdateien k&ouml;nnen direkt heruntergeladen werden.</p>"
        "<div style='display:flex;flex-wrap:wrap;gap:0.6rem;'>"
        + make_download_link("validation_input.ali", "ALI herunterladen", merged_ali)
        + make_download_link("validation_result.csv", "CSV-Tabelle herunterladen", validation_csv(blocks), "text/csv;charset=utf-8")
        + make_download_link("validation_raw.txt", "Rohausgabe herunterladen", raw_text)
        + (make_download_link("validation_result.html", "HTML herunterladen", html_content, "text/html;charset=utf-8") if html_content else "")
        + "</div></div>"
    )


def _f1(sens, spec):
    if sens + spec <= 0:
        return 0.0
    return 2.0 * sens * spec / (sens + spec)


def html_with_plots(blocks, raw_text, merged_ali="", html_content=None):
    """Erzeugt HTML mit Tabelle und Balken-Diagrammen."""
    rows = []
    sens_vals = []
    spec_vals = []
    cov_vals = []
    f1_vals = []
    for b in blocks:
        sens_vals.append(b["sensitivity"])
        spec_vals.append(b["specificity"])
        cov_vals.append(b["coverage"])
        f1_vals.append(_f1(b["sensitivity"], b["specificity"]))
        def bar(x):
            pct = max(0, min(100, x * 100))
            return '<div class="bar-wrap"><span class="bar" style="width:{:.0f}%"></span></div>'.format(pct)
        f1 = _f1(b["sensitivity"], b["specificity"])
        rows.append(
            "<tr><td>{header}</td>"
            "<td>{bs} {sens:.2f}</td><td>{bp} {spec:.2f}</td><td>{bf} {f1:.2f}</td><td>{bc} {cov:.2f}</td>"
            "<td>{mse:.2f}</td><td>{inv:.2f}</td></tr>".format(
                header=cgi.escape(b.get("header") or "Block"),
                sens=b["sensitivity"], bs=bar(b["sensitivity"]),
                spec=b["specificity"], bp=bar(b["specificity"]),
                f1=f1, bf=bar(f1),
                cov=b["coverage"], bc=bar(b["coverage"]),
                mse=b["mse"], inv=b["inv_mse"],
            )
        )
    avg_sens = sum(sens_vals) / len(sens_vals) if sens_vals else 0
    avg_spec = sum(spec_vals) / len(spec_vals) if spec_vals else 0
    avg_f1 = sum(f1_vals) / len(f1_vals) if f1_vals else 0
    avg_cov = sum(cov_vals) / len(cov_vals) if cov_vals else 0
    mse_vals = [b["mse"] for b in blocks]
    inv_vals = [b["inv_mse"] for b in blocks]

    # Kurze Labels (erster Teil des Headers, max. 12 Zeichen) – kein undefined/leer
    labels_list = []
    for b in blocks:
        h = (b.get("header") or "Block").strip()
        parts = h.split()
        h = (parts[0] if parts else "Block") or "Block"
        labels_list.append(h[:12] if len(h) > 12 else h)

    # Alle 10 Plots aus den hochgeladenen Daten (echte Daten vom Upload)
    charts_html = ""
    if len(blocks) >= 1:
        import json
        sens_json = json.dumps(sens_vals)
        spec_json = json.dumps(spec_vals)
        cov_json = json.dumps(cov_vals)
        f1_json = json.dumps(f1_vals)
        mse_json = json.dumps(mse_vals)
        inv_json = json.dumps(inv_vals)
        labels_json = json.dumps([l if l else "Block" for l in labels_list])
        n_blocks = len(blocks)
        avg_mse = sum(mse_vals) / n_blocks if mse_vals else 0
        charts_html = """
  <h2>Plots aus Ihrem Upload (echte Daten)</h2>
  <p style="color:#5a6578;font-size:0.95rem;">Die folgenden Diagramme nutzen die Metriken aus Ihrer hochgeladenen Datei (&quot;%d Bl&ouml;cke&quot;).</p>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:1rem;margin:1rem 0;">
    <div><p><strong>1. Sensitivity vs. Specificity</strong></p><canvas id="chart1" width="280" height="180"></canvas></div>
    <div><p><strong>2. MSE vs. inverse MSE</strong></p><canvas id="chart2" width="280" height="180"></canvas></div>
    <div><p><strong>3. Sensitivity pro Block</strong></p><canvas id="chart3" width="280" height="180"></canvas></div>
    <div><p><strong>4. Specificity pro Block</strong></p><canvas id="chart4" width="280" height="180"></canvas></div>
    <div><p><strong>5. Coverage pro Block</strong></p><canvas id="chart5" width="280" height="180"></canvas></div>
    <div><p><strong>6. Mittelwerte (dieser Lauf)</strong></p><canvas id="chart6" width="280" height="180"></canvas></div>
    <div><p><strong>7. Verteilung Sensitivity</strong></p><canvas id="chart7" width="280" height="180"></canvas></div>
    <div><p><strong>8. Block-Index vs. Sensitivity</strong></p><canvas id="chart8" width="280" height="180"></canvas></div>
    <div><p><strong>9. Mittlerer MSE (dieser Lauf)</strong></p><canvas id="chart9" width="280" height="180"></canvas></div>
    <div><p><strong>10. &Uuml;bersicht Metriken</strong></p><canvas id="chart10" width="280" height="180"></canvas></div>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <script>
    var sens = %s, spec = %s, cov = %s, f1 = %s, mse = %s, invMse = %s, labelsRaw = %s;
    var labels = (labelsRaw || []).map(function(l){ return (l === undefined || l === null || l === '') ? 'Block' : l; });
    var avgS=%s, avgP=%s, avgC=%s, avgF1=%s, avgM=%s;
    function binCounts(arr,bins){ var c=bins.map(function(_,i){ return 0; }); arr.forEach(function(v){ for(var i=0;i<bins.length-1;i++) if(v>=bins[i]&&v<bins[i+1]){ c[i]++; return; } if(v>=bins[bins.length-1]) c[bins.length-1]++; }); return c; }
    var histCounts = binCounts(sens, [0,0.2,0.4,0.6,0.8,1.01]);
    new Chart(document.getElementById("chart1"),{type:"scatter",data:{datasets:[{label:"Sens vs Spec",data:sens.map(function(s,i){return{x:s,y:spec[i]};}),backgroundColor:"rgba(13,107,92,0.6)",pointRadius:5}]},options:{scales:{x:{min:0,max:1.05},y:{min:0,max:1.05}}}});
    new Chart(document.getElementById("chart2"),{type:"scatter",data:{datasets:[{label:"MSE vs inv. MSE",data:mse.map(function(m,i){return{x:m,y:invMse[i]};}),backgroundColor:"rgba(42,157,143,0.6)",pointRadius:5}]},options:{scales:{x:{beginAtZero:true},y:{beginAtZero:true}}}});
    new Chart(document.getElementById("chart3"),{type:"bar",data:{labels:labels,datasets:[{label:"Sensitivity",data:sens,backgroundColor:"rgba(13,107,92,0.7)"}]},options:{scales:{y:{min:0,max:1.05}}}});
    new Chart(document.getElementById("chart4"),{type:"bar",data:{labels:labels,datasets:[{label:"Specificity",data:spec,backgroundColor:"rgba(42,157,143,0.7)"}]},options:{scales:{y:{min:0,max:1.05}}}});
    new Chart(document.getElementById("chart5"),{type:"bar",data:{labels:labels,datasets:[{label:"Coverage",data:cov,backgroundColor:"rgba(13,107,92,0.5)"}]},options:{scales:{y:{min:0,max:1.05}}}});
    new Chart(document.getElementById("chart6"),{type:"bar",data:{labels:["Dieser Lauf"],datasets:[{label:"Sensitivity",data:[avgS],backgroundColor:"#0d6b5c"},{label:"Specificity",data:[avgP],backgroundColor:"#2a9d8f"},{label:"F1",data:[avgF1],backgroundColor:"#5cb8a8"},{label:"Coverage",data:[avgC],backgroundColor:"#7dcec8"}]},options:{scales:{y:{min:0,max:1.05}}}});
    new Chart(document.getElementById("chart7"),{type:"bar",data:{labels:["0-0.2","0.2-0.4","0.4-0.6","0.6-0.8","0.8-1.0"],datasets:[{label:"Anzahl",data:histCounts,backgroundColor:"rgba(13,107,92,0.7)"}]},options:{scales:{y:{beginAtZero:true,ticks:{stepSize:1}}}}});
    new Chart(document.getElementById("chart8"),{type:"scatter",data:{datasets:[{label:"Sensitivity",data:sens.map(function(s,i){return{x:i,y:s};}),backgroundColor:"rgba(13,107,92,0.6)",pointRadius:5}]},options:{scales:{x:{title:{display:true,text:"Block-Index"}},y:{min:0,max:1.05}}}});
    new Chart(document.getElementById("chart9"),{type:"bar",data:{labels:["Dieser Lauf"],datasets:[{label:"MSE",data:[avgM],backgroundColor:"#0d6b5c"}]},options:{scales:{y:{beginAtZero:true}}}});
    new Chart(document.getElementById("chart10"),{type:"bar",data:{labels:["Sensitivity","Specificity","F1","Coverage"],datasets:[{label:"Mittelwerte",data:[avgS,avgP,avgF1,avgC],backgroundColor:["#0d6b5c","#2a9d8f","#5cb8a8","#7dcec8"]}]},options:{scales:{y:{min:0,max:1.05}}}});
  </script>""" % (
            n_blocks, sens_json, spec_json, cov_json, f1_json, mse_json, inv_json, labels_json,
            avg_sens, avg_spec, avg_cov, avg_f1, avg_mse
        )

    css = """
    .val-table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.9em; }
    .val-table th, .val-table td { border: 1px solid #ddd; padding: 6px 10px; text-align: left; }
    .val-table th { background: #0d6b5c; color: #fff; }
    .val-table tr:nth-child(even) { background: #f6f5f2; }
    .bar-wrap { width: 60px; height: 0.75em; background: #e2e0db; border-radius: 3px; overflow: hidden; display: inline-block; vertical-align: middle; margin-right: 6px; }
    .bar { display: block; height: 100%; background: #0d6b5c; border-radius: 2px; min-width: 2px; }
    .summary { display: flex; gap: 2rem; margin: 1rem 0; flex-wrap: wrap; }
    .summary-item { background: #f6f5f2; padding: 0.75rem 1.25rem; border-radius: 8px; }
    .summary-item strong { display: block; font-size: 1.5rem; color: #0d6b5c; }
    pre.raw { background: #1a1d23; color: #e6e8eb; padding: 1rem; overflow-x: auto; font-size: 0.85em; }
    """
    return """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <title>Validation Ergebnis</title>
  <style>{css}</style>
</head>
<body>
  <h1>Validation Ergebnis</h1>
  {downloads}
  <h2>&Uuml;bersicht (Mittelwerte)</h2>
  <div class="summary">
    <div class="summary-item">Sensitivity (&Oslash;) <strong>{avg_sens:.2f}</strong></div>
    <div class="summary-item">Specificity (&Oslash;) <strong>{avg_spec:.2f}</strong></div>
    <div class="summary-item">F1 (&Oslash;) <strong>{avg_f1:.2f}</strong></div>
    <div class="summary-item">Coverage (&Oslash;) <strong>{avg_cov:.2f}</strong></div>
  </div>
  {charts}
  <h2>Pro Block</h2>
  <table class="val-table">
    <thead><tr><th>Header</th><th>Sensitivity</th><th>Specificity</th><th>F1</th><th>Coverage</th><th>MSE</th><th>Inv. MSE</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <h2>Rohausgabe</h2>
  <pre class="raw">{raw}</pre>
</body>
</html>""".format(
        css=css,
        avg_sens=avg_sens,
        avg_spec=avg_spec,
        avg_f1=avg_f1,
        avg_cov=avg_cov,
        charts=charts_html,
        rows="".join(rows),
        raw=cgi.escape(raw_text),
        downloads=validation_downloads_html(blocks, merged_ali, raw_text, html_content),
    )


def parse_candidate_ali(text):
    """Parst Alignment-Ausgabe (ali): Bloecke von 3 Zeilen (Header, line1, line2). id_ss-Zeilen ueberspringen."""
    blocks = []
    lines = (text or "").strip().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith(">"):
            header = line
            line1 = lines[i + 1].rstrip() if i + 1 < len(lines) else ""
            line2 = lines[i + 2].rstrip() if i + 2 < len(lines) else ""
            i += 3
            while i < len(lines) and ("_ss:" in (lines[i] or "") or (lines[i] or "").strip().startswith("#")):
                i += 1
            if line1 and line2:
                blocks.append((header, line1, line2))
            continue
        i += 1
    return blocks


def parse_reference_5lines(data_bytes):
    """Parst Referenz-Datei (5 Zeilen pro Block), liefert Liste von (header, line1, line2, line3, line4)."""
    text = (data_bytes or b"").decode("utf-8", errors="replace").strip()
    blocks = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith(">"):
            header = line
            l1 = lines[i + 1].rstrip() if i + 1 < len(lines) else ""
            l2 = lines[i + 2].rstrip() if i + 2 < len(lines) else ""
            l3 = lines[i + 3].rstrip() if i + 3 < len(lines) else ""
            l4 = lines[i + 4].rstrip() if i + 4 < len(lines) else ""
            i += 5
            if l3 and l4:
                blocks.append((header, l1, l2, l3, l4))
            continue
        i += 1
    return blocks


def _run_alignment_jar(tmpdir, pairs_txt, seqlib_txt, matrix_path, with_ss=False, seqlib_ss_txt=None, levitt_path=None, ss_weight="0.3", go=-12, ge=-1):
    """Führt alignment.jar aus. with_ss: zusätzlich --levitt, --seqlib-ss, --ss-weight. Liefert (stdout, None) oder (None, Fehlermeldung)."""
    if not os.path.isfile(ALIGNMENT_JAR):
        return None, "alignment.jar nicht gefunden"
    args = [
        "--pairs", "pairs.txt", "--seqlib", "seqlib.txt", "-m", matrix_path,
        "--go", str(go), "--ge", str(ge), "--mode", "global", "--format", "ali",
    ]
    if with_ss and levitt_path and seqlib_ss_txt:
        args.extend(["--levitt", os.path.basename(levitt_path), "--seqlib-ss", "seqlib_ss.txt", "--ss-weight", str(ss_weight)])
    out, err = run_jar(ALIGNMENT_JAR, args, tmpdir, timeout=90)
    if err:
        return None, err
    return out, None


def _handle_compare_ss(pdb_id1, pdb_id2, form):
    """Vergleich Validation mit vs. ohne Sekundärstruktur (HOMSTRAD): zwei Alignments, eine Referenz, zwei Plots."""
    sys.path.insert(0, SCRIPT_DIR)
    try:
        from homstrad_ref import build_ref_from_db
        from alignment_db_sequence import resolve_sequence_id
    except ImportError as e:
        print_result_start("Validation – Fehler", "../validation.html", "Zurück zur Validation-Seite")
        print("<p class='error'>Modul fehlt: " + cgi.escape(str(e)) + "</p>")
        print_result_end()
        return

    r1 = resolve_sequence_id("pdb", pdb_id1)
    r2 = resolve_sequence_id("pdb", pdb_id2)
    if not r1 or not r1.get("seq"):
        print_result_start("Validation – Fehler", "../validation.html", "Zurück zur Validation-Seite")
        print("<p class='error'>Sequenz für ID " + cgi.escape(pdb_id1) + " nicht gefunden (DB oder PDB).</p>")
        print_result_end()
        return
    if not r2 or not r2.get("seq"):
        print_result_start("Validation – Fehler", "../validation.html", "Zurück zur Validation-Seite")
        print("<p class='error'>Sequenz für ID " + cgi.escape(pdb_id2) + " nicht gefunden (DB oder PDB).</p>")
        print_result_end()
        return

    seq1 = (r1["seq"] or "").replace("-", "").replace(".", "").strip()
    seq2 = (r2["seq"] or "").replace("-", "").replace(".", "").strip()
    ss1 = (r1.get("ss_seq") or "").strip()
    ss2 = (r2.get("ss_seq") or "").strip()
    have_ss = bool(ss1 and ss2 and len(ss1) == len(seq1) and len(ss2) == len(seq2))

    ref_blocks = build_ref_from_db([(pdb_id1, pdb_id2)])
    if not ref_blocks:
        print_result_start("Validation – Fehler", "../validation.html", "Zurück zur Validation-Seite")
        print("<p class='error'>Keine HOMSTRAD-Referenz für " + cgi.escape(pdb_id1) + " / " + cgi.escape(pdb_id2) + " gefunden. "
              "Datenbank befüllen (scripts/import_homstrad_to_db.py) oder andere PDB-IDs wählen.</p>")
        print_result_end()
        return

    tmpdir = tempfile.mkdtemp(prefix="val_ss_")
    try:
        with open(os.path.join(tmpdir, "pairs.txt"), "w", encoding="utf-8") as f:
            f.write("%s %s\n" % (pdb_id1, pdb_id2))
        with open(os.path.join(tmpdir, "seqlib.txt"), "w", encoding="utf-8") as f:
            f.write("%s: %s\n%s: %s\n" % (pdb_id1, seq1, pdb_id2, seq2))

        matrix_path = os.path.join(tmpdir, "matrix.mat")
        mat_dir = os.path.join(BASE_DIR, "MATRICES")
        test_dir = os.path.join(BASE_DIR, "test")
        matrix_used = None
        for name in ["blosum62.mat", "dayhoff.mat"]:
            for d in [mat_dir, test_dir]:
                p = os.path.join(d, name)
                if os.path.isfile(p):
                    with open(p, "rb") as src:
                        with open(matrix_path, "wb") as dst:
                            dst.write(src.read())
                    matrix_used = name
                    break
            if matrix_used:
                break
        if not os.path.isfile(matrix_path):
            shutil.rmtree(tmpdir, ignore_errors=True)
            print_result_start("Validation – Fehler", "../validation.html", "Zurück zur Validation-Seite")
            print("<p class='error'>Keine Substitutionsmatrix (blosum62.mat / dayhoff.mat) gefunden.</p>")
            print_result_end()
            return

        levitt_path = None
        if have_ss:
            lp = os.path.join(BASE_DIR, "test", "levitt_matrix.txt")
            if os.path.isfile(lp):
                levitt_path = os.path.join(tmpdir, "levitt.mat")
                with open(lp, "rb") as src:
                    with open(levitt_path, "wb") as dst:
                        dst.write(src.read())
            with open(os.path.join(tmpdir, "seqlib_ss.txt"), "w", encoding="utf-8") as f:
                f.write("%s: %s\n%s: %s\n" % (pdb_id1, ss1, pdb_id2, ss2))

        go, ge = -12, -1
        out_no_ss, err_no = _run_alignment_jar(tmpdir, None, None, "matrix.mat", with_ss=False, go=go, ge=ge)
        if err_no:
            print_result_start("Validation – Fehler", "../validation.html", "Zurück zur Validation-Seite")
            print("<p class='error'>Alignment ohne SS: " + cgi.escape(err_no) + "</p>")
            print_result_end()
            return

        cand_no_ss = parse_candidate_ali(out_no_ss or "")
        if not cand_no_ss:
            print_result_start("Validation – Fehler", "../validation.html", "Zurück zur Validation-Seite")
            print("<p class='error'>Alignment ohne SS lieferte keine Blöcke.</p>")
            print_result_end()
            return

        merged_no_ss = merge_candidate_with_reference(cand_no_ss, ref_blocks)
        inp_no = os.path.join(tmpdir, "input_no_ss.txt")
        with open(inp_no, "w", encoding="utf-8") as f:
            f.write(merged_no_ss)
        raw_no, err_val_no = run_jar(VALIDATE_JAR, ["-f", "input_no_ss.txt"], tmpdir)
        if err_val_no:
            print_result_start("Validation – Fehler", "../validation.html", "Zurück zur Validation-Seite")
            print("<p class='error'>ValidateAli ohne SS: " + cgi.escape(err_val_no) + "</p>")
            print_result_end()
            return
        blocks_no_ss = parse_validation_output(raw_no or "")

        blocks_with_ss = None
        ss_weight_used = "1"
        if have_ss and levitt_path:
            # Gleiche Gap-Kosten wie ohne SS (go=-12, ge=-1), SS-Gewicht 1 und Levitt-Matrix für fairen Vergleich
            out_ss, err_ss = _run_alignment_jar(tmpdir, None, None, "matrix.mat", with_ss=True,
                                                 seqlib_ss_txt="dummy", levitt_path=levitt_path, ss_weight=ss_weight_used, go=go, ge=ge)
            if not err_ss and out_ss:
                cand_ss = parse_candidate_ali(out_ss)
                if cand_ss:
                    merged_ss = merge_candidate_with_reference(cand_ss, ref_blocks)
                    inp_ss = os.path.join(tmpdir, "input_ss.txt")
                    with open(inp_ss, "w", encoding="utf-8") as f:
                        f.write(merged_ss)
                    raw_ss, err_val_ss = run_jar(VALIDATE_JAR, ["-f", "input_ss.txt"], tmpdir)
                    if not err_val_ss:
                        blocks_with_ss = parse_validation_output(raw_ss or "")

        n_no = len(blocks_no_ss) if blocks_no_ss else 0
        sens_no = sum(b["sensitivity"] for b in blocks_no_ss) / n_no if n_no else 0
        spec_no = sum(b["specificity"] for b in blocks_no_ss) / n_no if n_no else 0
        cov_no = sum(b["coverage"] for b in blocks_no_ss) / n_no if n_no else 0
        mse_no = sum(b["mse"] for b in blocks_no_ss) / n_no if n_no else 0
        inv_no = sum(b["inv_mse"] for b in blocks_no_ss) / n_no if n_no else 0
        f1_no = sum((2.0 * b["sensitivity"] * b["specificity"] / (b["sensitivity"] + b["specificity"]) if (b["sensitivity"] + b["specificity"]) > 0 else 0.0) for b in blocks_no_ss) / n_no if n_no else 0

        sens_ss = spec_ss = cov_ss = mse_ss = inv_ss = f1_ss = None
        if blocks_with_ss:
            n_ss = len(blocks_with_ss)
            sens_ss = sum(b["sensitivity"] for b in blocks_with_ss) / n_ss
            spec_ss = sum(b["specificity"] for b in blocks_with_ss) / n_ss
            cov_ss = sum(b["coverage"] for b in blocks_with_ss) / n_ss
            mse_ss = sum(b["mse"] for b in blocks_with_ss) / n_ss
            inv_ss = sum(b["inv_mse"] for b in blocks_with_ss) / n_ss
            f1_ss = sum((2.0 * b["sensitivity"] * b["specificity"] / (b["sensitivity"] + b["specificity"]) if (b["sensitivity"] + b["specificity"]) > 0 else 0.0) for b in blocks_with_ss) / n_ss

        import json
        labels_compare = ["Ohne SS", "Mit SS"] if blocks_with_ss else ["Ohne SS"]
        def _v(x):
            return round(x, 4) if x is not None else None
        sens_c = [sens_no] + ([sens_ss] if sens_ss is not None else [])
        spec_c = [spec_no] + ([spec_ss] if spec_ss is not None else [])
        cov_c = [cov_no] + ([cov_ss] if cov_ss is not None else [])
        mse_c = [mse_no] + ([mse_ss] if mse_ss is not None else [])
        inv_c = [inv_no] + ([inv_ss] if inv_ss is not None else [])
        f1_c = [f1_no] + ([f1_ss] if f1_ss is not None else [])

        # Kompakte Tabelle: alle 6 Metriken, Spalten Ohne SS | Mit SS
        has_ss = blocks_with_ss is not None
        th_ss = "<th style='text-align:center;padding:0.5rem 0.75rem;border:1px solid rgba(255,255,255,0.3);'>Mit SS</th>" if has_ss else ""
        settings_info = (
            " <span style='font-size:0.85rem;'>Einstellungen: Matrix <strong>" + cgi.escape(matrix_used or "?") + "</strong>, "
            "Gap open <strong>" + str(go) + "</strong>, Gap extend <strong>" + str(ge) + "</strong>. "
            + ("Mit SS: Levitt-Matrix (test/levitt_matrix.txt), SS-Gewicht <strong>" + ss_weight_used + "</strong>." if has_ss else "")
            + "</span>"
        )
        body = (
            "<h1>Vergleich mit/ohne Sekund&auml;rstruktur</h1>"
            "<p style='color:var(--text-muted);font-size:0.9rem;margin-bottom:1rem;'>Paar: <strong>" + cgi.escape(pdb_id1) + " / " + cgi.escape(pdb_id2) + "</strong>. "
            + ("Beide Alignments gegen dieselbe HOMSTRAD-Referenz." if has_ss else "Nur Alignment ohne SS (Sekund&auml;rstruktur nicht verf&uuml;gbar).")
            + settings_info + "</p>"
            "<div class='ss-compare-wrap' style='display:grid;grid-template-columns:1fr auto;gap:1.5rem;align-items:start;margin:1rem 0;'>"
            "<div class='ss-compare-table-wrap' style='overflow-x:auto;'>"
            "<table class='ss-compare-table' style='border-collapse:collapse;width:100%;max-width:380px;font-size:0.9rem;'>"
            "<thead><tr style='background:#0d6b5c;color:#fff;'>"
            "<th style='text-align:left;padding:0.5rem 0.75rem;border:1px solid rgba(255,255,255,0.3);'>Metrik</th>"
            "<th style='text-align:center;padding:0.5rem 0.75rem;border:1px solid rgba(255,255,255,0.3);'>Ohne SS</th>"
            + th_ss +
            "</tr></thead><tbody>"
        )
        def _row(name, no_val, ss_val, fmt=".2f"):
            try:
                no_s = format(no_val, fmt) if no_val is not None else "&ndash;"
            except (TypeError, ValueError):
                no_s = str(no_val) if no_val is not None else "&ndash;"
            try:
                ss_s = format(ss_val, fmt) if ss_val is not None else "&ndash;"
            except (TypeError, ValueError):
                ss_s = str(ss_val) if ss_val is not None else "&ndash;"
            td_ss = "<td style='text-align:center;padding:0.4rem 0.75rem;border:1px solid #c5e0db;background:#e8f6f3;'><strong>" + ss_s + "</strong></td>" if has_ss else ""
            return "<tr><td style='padding:0.4rem 0.75rem;border:1px solid #c5e0db;'>" + name + "</td><td style='text-align:center;padding:0.4rem 0.75rem;border:1px solid #c5e0db;background:#f6f5f2;'><strong>" + no_s + "</strong></td>" + td_ss + "</tr>"
        body += _row("Sensitivity", sens_no, sens_ss)
        body += _row("Specificity", spec_no, spec_ss)
        body += _row("Coverage", cov_no, cov_ss)
        body += _row("MSE", mse_no, mse_ss, ".3f")
        body += _row("IMSE", inv_no, inv_ss, ".3f")
        body += _row("F1-Score", f1_no, f1_ss)
        body += "</tbody></table></div>"
        # 6 kleine Balkencharts
        body += (
            "<div class='ss-compare-charts' style='display:grid;grid-template-columns:repeat(2,1fr);gap:0.75rem;'>"
            "<div><canvas id='chart_ss_sens' width='160' height='100'></canvas><p style='margin:0;font-size:0.8rem;color:var(--text-muted);'>Sensitivity</p></div>"
            "<div><canvas id='chart_ss_spec' width='160' height='100'></canvas><p style='margin:0;font-size:0.8rem;color:var(--text-muted);'>Specificity</p></div>"
            "<div><canvas id='chart_ss_cov' width='160' height='100'></canvas><p style='margin:0;font-size:0.8rem;color:var(--text-muted);'>Coverage</p></div>"
            "<div><canvas id='chart_ss_mse' width='160' height='100'></canvas><p style='margin:0;font-size:0.8rem;color:var(--text-muted);'>MSE</p></div>"
            "<div><canvas id='chart_ss_imse' width='160' height='100'></canvas><p style='margin:0;font-size:0.8rem;color:var(--text-muted);'>IMSE</p></div>"
            "<div><canvas id='chart_ss_f1' width='160' height='100'></canvas><p style='margin:0;font-size:0.8rem;color:var(--text-muted);'>F1-Score</p></div>"
            "</div></div>"
            "<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'></script>"
            "<script>"
            "var labelsCompare=" + json.dumps(labels_compare) + ";"
            "var sensCompare=" + json.dumps(sens_c) + ",specCompare=" + json.dumps(spec_c) + ",covCompare=" + json.dumps(cov_c) + ",mseCompare=" + json.dumps(mse_c) + ",invCompare=" + json.dumps(inv_c) + ",f1Compare=" + json.dumps(f1_c) + ";"
            "var opts={scales:{y:{min:0,max:1.05}}},optsMse={scales:{y:{beginAtZero:true}}};"
            "new Chart(document.getElementById('chart_ss_sens'),{type:'bar',data:{labels:labelsCompare,datasets:[{label:'Sensitivity',data:sensCompare,backgroundColor:['#0d6b5c','#2a9d8f']}]},options:opts});"
            "new Chart(document.getElementById('chart_ss_spec'),{type:'bar',data:{labels:labelsCompare,datasets:[{label:'Specificity',data:specCompare,backgroundColor:['#0d6b5c','#2a9d8f']}]},options:opts});"
            "new Chart(document.getElementById('chart_ss_cov'),{type:'bar',data:{labels:labelsCompare,datasets:[{label:'Coverage',data:covCompare,backgroundColor:['#0d6b5c','#2a9d8f']}]},options:opts});"
            "new Chart(document.getElementById('chart_ss_mse'),{type:'bar',data:{labels:labelsCompare,datasets:[{label:'MSE',data:mseCompare,backgroundColor:['#0d6b5c','#2a9d8f']}]},options:optsMse});"
            "new Chart(document.getElementById('chart_ss_imse'),{type:'bar',data:{labels:labelsCompare,datasets:[{label:'IMSE',data:invCompare,backgroundColor:['#0d6b5c','#2a9d8f']}]},options:optsMse});"
            "new Chart(document.getElementById('chart_ss_f1'),{type:'bar',data:{labels:labelsCompare,datasets:[{label:'F1',data:f1Compare,backgroundColor:['#0d6b5c','#2a9d8f']}]},options:opts});"
            "</script>"
        )
        body += ""
        # JSmol: 3D-Ansicht der Sekundärstrukturen beider PDB-Strukturen
        pdb4_1 = (pdb_id1 or "").strip()[:4].upper()
        pdb4_2 = (pdb_id2 or "").strip()[:4].upper()
        if pdb4_1 and pdb4_2 and len(pdb4_1) == 4 and len(pdb4_2) == 4:
            url1 = "https://files.rcsb.org/download/" + pdb4_1 + ".pdb"
            url2 = "https://files.rcsb.org/download/" + pdb4_2 + ".pdb"
            jsmol_html = (
                "<div class='jsmol-toggle-section' style='margin-top:2rem;padding-top:1rem;border-top:2px solid var(--accent-light);'>"
                "<div class='jsmol-ss-section' style='padding:1rem 1.25rem;background:linear-gradient(180deg,#edf5f4 0%,#e0f0ee 100%);border:1px solid var(--border);border-radius:12px;margin-bottom:1rem;'>"
                "<h3 style='font-size:1.05rem;color:var(--accent);margin:0 0 0.5rem;'>3D-Ansicht: " + cgi.escape(pdb4_1) + " und " + cgi.escape(pdb4_2) + "</h3>"
                "<p class='jsmol-lead' style='font-size:0.9rem;margin:0 0 0.5rem;'><strong>Was dargestellt wird:</strong> Die beiden Proteine werden aus der PDB geladen und <em>gemeinsam in einer 3D-Szene</em> angezeigt. Sie befinden sich im gleichen Koordinatensystem; ihre urspr&uuml;nglichen PDB-Koordinaten bleiben unver&auml;ndert, daher k&ouml;nnen sich die Strukturen r&aumlich &uuml;berlappen oder getrennt stehen. Die Darstellung ist als <em>Cartoon (Ribbon)</em>: die Peptidr&uuml;ckgrat-Bahnen sind als B&auml;nder gezeichnet, sodass Helices und Strang-Faltbl&auml;tter gut erkennbar sind.</p>"
                "<p class='jsmol-lead' style='font-size:0.9rem;margin:0 0 0.5rem;'><strong>Sekund&auml;rstruktur-Vergleich:</strong> Beide Proteine (<strong>" + cgi.escape(pdb4_1) + "</strong> links, <strong>" + cgi.escape(pdb4_2) + "</strong> rechts) werden nebeneinander angezeigt und einheitlich nach Sekund&auml;rstruktur gef&auml;rbt: <span style='color:#c0392b;font-weight:bold;'>Rot</span> = &alpha;-Helix, <span style='color:#d4ac0d;font-weight:bold;'>Gelb</span> = &beta;-Strang, <span style='color:#7f8c8d;font-weight:bold;'>Grau</span> = Coil. So k&ouml;nnen Sie auf einen Blick vergleichen, wo Helices, Strang und Coils in den beiden Strukturen liegen.</p>"
                "<p class='jsmol-lead' style='font-size:0.9rem;margin:0 0 0.5rem;'><strong>Bedienung:</strong> Maus: drehen (ziehen), zoomen (Rad). Erscheinen anfangs nur Punkte, bitte kurz warten oder drehen.</p>"
                "<p class='jsmol-lead' style='font-size:0.85rem;margin:0 0 0.75rem;color:var(--text-muted);'>Die Ansicht erscheint hier unten. &Ouml;ffnet sich ein neues Fenster (z.&nbsp;B. durch Browser-Einstellungen), k&ouml;nnen Sie die Struktur dort betrachten.</p>"
                "<button type='button' class='jsmol-toggle-btn' onclick=\"this.closest('.jsmol-toggle-section').classList.toggle('expanded'); initJsmolCompareSS(); return false;\" aria-expanded='false'>"
                "<span class='arrow'>&#9654;</span> 3D-Struktur hier laden (JSmol)"
                "</button>"
                "</div>"
                "<div class='jsmol-toggle-content' style='margin-top:0.5rem;'>"
                "<div id='jsmol_compare_ss_container' class='jsmol-embed-small' style='width:280px;max-width:100%;height:260px;background:#1a1d23;border-radius:10px;overflow:hidden;border:2px solid var(--border);'></div>"
                "</div></div>"
                "<script>(function(){"
                "var jsmolCompareDone=false;"
                "window.initJsmolCompareSS=function(){"
                "var c=document.getElementById('jsmol_compare_ss_container');"
                "if(!c||jsmolCompareDone)return;"
                "var url1=" + json.dumps(url1) + ",url2=" + json.dumps(url2) + ";"
                "function init(){"
                "if(typeof Jmol==='undefined')return;"
                "jsmolCompareDone=true;"
                "try{"
                "var script='load '+url1+'; load append '+url2+'; frame all; calculate structure; spacefill off; wireframe off; cartoons on; select helix; color red; select sheet; color yellow; select loop; color gray; select not (helix or sheet or loop); color gray;';"
                "var Info={width:280,height:260,use:'HTML5',color:'#1a1d23',j2sPath:'https://chemapps.stolaf.edu/jmol/jsmol/j2s',script:script,disableInitialConsole:true};"
                "var applet=Jmol.getApplet('jsmol_compare_ss',Info);"
                "var h=Jmol.getAppletHtml(applet);"
                "if(c)c.innerHTML=h;"
                "}catch(e){ if(c)c.innerHTML='<p style=\"color:#c0392b;\">JSmol konnte nicht geladen werden. Bitte Seite neu laden.</p>'; }"
                "}"
                "if(typeof Jmol!=='undefined'){init();return;}"
                "var s=document.createElement('script');s.src='https://chemapps.stolaf.edu/jmol/jsmol/JSmol.min.js';s.onload=init;s.onerror=function(){var c=document.getElementById('jsmol_compare_ss_container');if(c)c.innerHTML='<p style=\"color:#c0392b;\">JSmol-Skript konnte nicht geladen werden.</p>';};document.head.appendChild(s);"
                "};"
                "})();</script>"
            )
            body += jsmol_html
        print_result_start("Vergleich mit/ohne Sekundärstruktur", "../validation.html", "Zurück zur Validation-Seite")
        print(body)
        print_result_end()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def merge_candidate_with_reference(candidate_blocks, reference_blocks):
    """Kandidat (3 Zeilen/Block) + Referenz: reference_blocks = Liste von (h,l1,l2,l3,l4) ODER Dict (id1,id2) -> (line3, line4)."""
    out = []
    if isinstance(reference_blocks, dict):
        for (ch, c1, c2) in candidate_blocks:
            parts = ch[1:].strip().split()
            if len(parts) < 2:
                continue
            key = (parts[0], parts[1])
            if key not in reference_blocks and (parts[1], parts[0]) in reference_blocks:
                key = (parts[1], parts[0])
            if key in reference_blocks:
                r3, r4 = reference_blocks[key]
                out.append(ch)
                out.append(c1)
                out.append(c2)
                out.append(r3)
                out.append(r4)
    else:
        n = min(len(candidate_blocks), len(reference_blocks))
        for i in range(n):
            ch, c1, c2 = candidate_blocks[i]
            rh, r1, r2, r3, r4 = reference_blocks[i]
            out.append(ch)
            out.append(c1)
            out.append(c2)
            out.append(r3)
            out.append(r4)
    return "\n".join(out) + "\n" if out else ""


def main():
    if os.environ.get("REQUEST_METHOD") != "POST":
        print("Status: 405 Method Not Allowed")
        print("Content-Type: text/plain; charset=utf-8")
        print()
        print("Nur POST erlaubt.")
        return

    form = cgi.FieldStorage()
    compare_ss = form.getfirst("compare_ss", "") in ("1", "yes", "true")
    pdb_id1 = (form.getfirst("pdb_id1") or "").strip()
    pdb_id2 = (form.getfirst("pdb_id2") or "").strip()
    if compare_ss and pdb_id1 and pdb_id2:
        _handle_compare_ss(pdb_id1, pdb_id2, form)
        return

    candidate_ali = (form.getfirst("candidate_ali") or "").strip()
    reference_example = (form.getfirst("reference_example") or "").strip()
    reference_homstrad = form.getfirst("reference_homstrad", "") in ("1", "yes", "true")
    try:
        ref_file = form["reference_file"] if "reference_file" in form else None
    except (TypeError, KeyError):
        ref_file = None
    if isinstance(ref_file, list):
        ref_file = ref_file[0] if ref_file else None
    ref_data = None
    if ref_file is not None:
        try:
            if hasattr(ref_file, "file") and ref_file.file:
                ref_data = ref_file.file.read()
            elif hasattr(ref_file, "value"):
                ref_data = ref_file.value
                if isinstance(ref_data, str):
                    ref_data = ref_data.encode("utf-8")
        except Exception:
            ref_data = None
    if not ref_data and reference_example:
        ref_path = os.path.join(BASE_DIR, "test", reference_example)
        if os.path.isfile(ref_path):
            try:
                with open(ref_path, "rb") as f:
                    ref_data = f.read()
            except Exception:
                pass

    back_url = "../alignment.html" if candidate_ali else "../validation.html"
    back_label = "Zurück zur Alignment-Seite" if candidate_ali else "Zurück zur Validation-Seite"

    # Modus "Jetzt validieren" (von Alignment-Seite): Kandidat + Referenz (Upload, Beispieldatei oder HOMSTRAD)
    if candidate_ali and (ref_data or reference_homstrad):
        cand_blocks = parse_candidate_ali(candidate_ali)
        if not cand_blocks:
            print_result_start("Validation – Fehler", back_url, back_label)
            print("<p class='error'>Das Alignment-Ergebnis enth&auml;lt keine g&uuml;ltigen Bl&ouml;cke (Format: &gt;Header, dann 2 Zeilen id: seq).</p>")
            print_result_end()
            return

        ref_blocks = None
        if reference_homstrad:
            sys.path.insert(0, SCRIPT_DIR)
            pairs_list = []
            for (header, l1, l2) in cand_blocks:
                parts = header[1:].strip().split()
                if len(parts) >= 2:
                    pairs_list.append((parts[0], parts[1]))
            try:
                from homstrad_ref import build_ref_from_db, build_ref_from_homstrad
            except ImportError:
                print_result_start("Validation – Fehler", back_url, back_label)
                print("<p class='error'>homstrad_ref.py nicht gefunden.</p>")
                print_result_end()
                return
            # Zuerst Referenz aus der Datenbank (kein HOMSTRAD-Ordner auf dem Server nötig)
            ref_blocks = build_ref_from_db(pairs_list)
            if not ref_blocks:
                # Fallback: Referenz aus HOMSTRAD-Verzeichnis (z. B. Bioclient)
                HOMSTRAD_DIR = os.environ.get("HOMSTRAD_DIR", "")
                if os.path.isdir(HOMSTRAD_DIR):
                    ref_blocks = build_ref_from_homstrad(HOMSTRAD_DIR, pairs_list)
                if not ref_blocks:
                    print_result_start("Validation – Fehler", back_url, back_label)
                    print("<p class='error'>Keine HOMSTRAD-Referenz gefunden. "
                          "Entweder die Datenbank enth&auml;lt noch keine HOMSTRAD-Daten "
                          "(dann einmalig <code>python3 scripts/import_homstrad_to_db.py</code> aus dem Projektordner ausf&uuml;hren) "
                          "oder die IDs in Ihrem Alignment (z.&nbsp;B. 1bgxt, 2pgd) m&uuml;ssen mit den Referenz-IDs &uuml;bereinstimmen (PDB-Basis: erste 4 Zeichen).</p>")
                    print_result_end()
                    return
        else:
            ref_blocks_5 = parse_reference_5lines(ref_data)
            if not ref_blocks_5:
                print_result_start("Validation – Fehler", back_url, back_label)
                print("<p class='error'>Die Referenz-Datei enth&auml;lt keine g&uuml;ltigen Bl&ouml;cke (5 Zeilen pro Block).</p>")
                print_result_end()
                return
            if len(cand_blocks) != len(ref_blocks_5):
                print_result_start("Validation – Fehler", back_url, back_label)
                print("<p class='error'>Anzahl Bl&ouml;cke passt nicht (Alignment: %d, Referenz: %d).</p>" % (len(cand_blocks), len(ref_blocks_5)))
                print_result_end()
                return
            ref_blocks = {}
            for (h, l1, l2, l3, l4) in ref_blocks_5:
                idx = l1.find(":")
                id1 = l1[:idx].strip() if idx >= 0 else l1.split(None, 1)[0]
                idx2 = l2.find(":")
                id2 = l2[:idx2].strip() if idx2 >= 0 else l2.split(None, 1)[0]
                if id1 and id2:
                    ref_blocks[(id1, id2)] = (l3, l4)

        merged = merge_candidate_with_reference(cand_blocks, ref_blocks)
        if not merged.strip():
            print_result_start("Validation – Fehler", back_url, back_label)
            print("<p class='error'>Referenz-IDs passen nicht zu den Alignment-IDs.</p>")
            print_result_end()
            return
        data = merged.encode("utf-8")
    else:
        # Klassisch: eine Datei (vollstaendiges Validation-Format) oder Beispieldatei
        alignment_example = (form.getfirst("alignment_example") or "").strip()
        data = None
        if alignment_example:
            ref_path = os.path.join(BASE_DIR, "test", alignment_example)
            if os.path.isfile(ref_path):
                try:
                    with open(ref_path, "rb") as fp:
                        data = fp.read()
                except Exception:
                    pass
        if not data:
            if "alignment_pairs_file" in form:
                f = form["alignment_pairs_file"]
                if isinstance(f, list):
                    f = f[0] if f else None
                if f and hasattr(f, "file") and f.file:
                    data = f.file.read()
                elif f and hasattr(f, "value"):
                    data = f.value
                    if isinstance(data, str):
                        data = data.encode("utf-8")
        if not data:
            print_result_start("Validation – Fehler", back_url, back_label)
            print("<p class='error'>Bitte eine Alignment-Pairs-Datei hochladen oder eine Beispieldatei (z.&nbsp;B. example.validation.ali) w&auml;hlen.</p>")
            print_result_end()
            return

    tmpdir = tempfile.mkdtemp(prefix="val_")
    try:
        inp = os.path.join(tmpdir, "input.txt")
        with open(inp, "wb") as fp:
            fp.write(data)

        out, err = run_jar(VALIDATE_JAR, ["-f", "input.txt"], tmpdir)
        if err:
            print_result_start("Validation – Fehler", back_url, back_label)
            print("<h2>Fehler</h2><pre class='raw'>")
            print(cgi.escape(out or ""))
            print("</pre><p class='error'>", cgi.escape(err), "</p>")
            print_result_end()
            return

        show_plots = form.getfirst("show_plots", "1") in ("1", "yes", "true")
        merged_text = data.decode("utf-8", errors="replace")
        if show_plots:
            blocks = parse_validation_output(out)
            if blocks:
                base_plot_body = extract_jar_body(html_with_plots(blocks, out, merged_text, None))
                full_plot_html = result_page_html_document("Validation Ergebnis", base_plot_body)
                plot_body = extract_jar_body(html_with_plots(blocks, out, merged_text, full_plot_html))
                print_result_start("Validation Ergebnis", back_url, back_label)
                print(plot_body)
                print_result_end()
                return

        print_result_start("Validation Ergebnis", back_url, back_label)
        blocks = parse_validation_output(out)
        raw_body = "<h2>Ergebnis</h2><pre class='raw'>" + cgi.escape(out) + "</pre>"
        print(validation_downloads_html(blocks, merged_text, out, result_page_html_document("Validation Ergebnis", raw_body)))
        print(raw_body)
        print_result_end()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        try:
            print_result_start("Validation – Fehler", "../validation.html", "Zurück zur Validation-Seite")
            print("<p class='error'>Ein unerwarteter Fehler ist aufgetreten.</p>")
            print("<pre class='raw'>")
            print(cgi.escape(traceback.format_exc()))
            print("</pre>")
            print_result_end()
        except Exception:
            print("<!DOCTYPE html><html><head><meta charset='utf-8'></head><body><h1>Fehler</h1><pre>")
            print(traceback.format_exc())
            print("</pre></body></html>")
