#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os, cgi, subprocess, tempfile, shutil, re, zipfile, base64
from pathlib import Path

# --- KONFIGURATION ---
CGI_DIR      = os.path.dirname(os.path.abspath(__file__))
JAR_TRAIN    = os.path.join(CGI_DIR, "train.jar")
JAR_PREDICT  = os.path.join(CGI_DIR, "predict.jar")
JAR_VALIDATE = os.path.join(CGI_DIR, "validateGor.jar")
CLS_TRAIN    = "de.lmu.ifi.bio.gor.cli.Train"
CLS_PREDICT  = "de.lmu.ifi.bio.gor.cli.Predict"
CLS_VALIDATE = "de.lmu.ifi.bio.gor.cli.validateGor"
CB513_PATH   = "/mnt/extstud/praktikum/bioprakt/Data/GOR/CB513/CB513DSSP.db"
DEFAULT_MODELS = {
    "gor1": os.path.join(CGI_DIR, "gor1default.txt"),
    "gor3": os.path.join(CGI_DIR, "gor3default.txt"),
    "gor4": os.path.join(CGI_DIR, "gor4default.txt"),
}


def get_seq(entry):
    for l in entry.split("\n"):
        if l.startswith("AS "): return l[3:].strip()
    return ""


def get_id(entry):
    for l in entry.split("\n"):
        if l.startswith(">"): return l[1:].strip().split()[0]
    return "unk"


def parse_mean(line):
    m = re.search(r'Mean:\s*([\d.]+)', line, re.IGNORECASE)
    return float(m.group(1)) if m else 0.0


def parse_summary_file(summary_file):
    scores = {}
    if not os.path.exists(summary_file): return scores
    keys_map = {
        r'^q3\s*:': "Q3", r'^sov\s*:': "SOV"
    }
    with open(summary_file, "r") as f:
        for line in f:
            for pattern, key in keys_map.items():
                if re.match(pattern, line.strip(), re.IGNORECASE):
                    val = parse_mean(line)
                    if val is not None: scores[key] = val
    return scores


print("Content-Type: text/html; charset=utf-8\n")
fs = cgi.FieldStorage()

print("""
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Validation &amp; Performance Hub | Gruppe 17</title>
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
            background: var(--bio-deep);
            color: var(--text);
            line-height: 1.6;
            min-height: 100vh;
        }

        body::before {
            content: "";
            position: fixed;
            inset: 0;
            background:
                linear-gradient(180deg, rgba(13,107,92,0.06) 0%, transparent 40%),
                radial-gradient(ellipse 80% 50% at 50% -20%, rgba(42,157,143,0.15), transparent),
                repeating-linear-gradient(0deg, transparent, transparent 32px, rgba(13,107,92,0.03) 32px, rgba(13,107,92,0.03) 33px),
                repeating-linear-gradient(90deg, transparent, transparent 32px, rgba(13,107,92,0.03) 32px, rgba(13,107,92,0.03) 33px);
            pointer-events: none;
            z-index: 0;
        }

        .header {
            position: relative;
            background: linear-gradient(160deg, var(--bio-deep) 0%, var(--bio-dark) 40%, var(--bio-green) 100%);
            color: #fff;
            padding: 40px 24px 48px;
            text-align: center;
            overflow: hidden;
        }

        .header::after {
            content: "";
            position: absolute;
            bottom: 0; left: 0; right: 0;
            height: 60px;
            background: linear-gradient(to top, var(--bio-deep), transparent);
            pointer-events: none;
        }

        .header-inner { position: relative; z-index: 1; }

        .header h1 { margin: 0 0 6px; font-size: 1.6rem; font-weight: 700; letter-spacing: 0.02em; }
        .header p  { margin: 0; opacity: 0.85; font-size: 0.95rem; }

        .badge {
            display: inline-block;
            background: rgba(255,255,255,0.15);
            border: 1px solid rgba(255,255,255,0.3);
            border-radius: 20px;
            padding: 3px 14px;
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.06em;
            margin-top: 10px;
        }

        .hero-dots { display: flex; gap: 8px; justify-content: center; margin-top: 14px; }
        .hero-dots span { width: 8px; height: 8px; border-radius: 50%; background: rgba(255,255,255,0.45); }

        .main {
            position: relative;
            z-index: 1;
            max-width: 900px;
            margin: -24px auto 0;
            padding: 0 20px 56px;
        }

        .main-panel {
            background: linear-gradient(180deg, rgba(255,255,255,0.97) 0%, rgba(248,252,251,0.98) 100%);
            border-radius: 20px;
            padding: 36px 32px 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.25), 0 0 0 1px rgba(255,255,255,0.1) inset;
        }

        .card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 24px 24px 20px;
            margin-bottom: 20px;
        }

        .card-title {
            font-size: 0.78em;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--bio-green);
            margin-bottom: 16px;
        }

        .card h2 { font-size: 1.05rem; font-weight: 700; color: var(--bio-dark); margin-bottom: 10px; }
        .card p  { font-size: 0.93em; color: var(--text); margin-bottom: 10px; }

        .info-box {
            background: var(--bio-green-pale);
            border: 1px solid var(--bio-green-light);
            border-radius: 10px;
            padding: 11px 15px;
            font-size: 0.88em;
            color: var(--bio-green);
            margin-bottom: 16px;
        }

        .tab-buttons { display: flex; gap: 8px; margin-bottom: 18px; }
        .tab-btn {
            flex: 1; padding: 9px 12px; border: 2px solid var(--border); border-radius: 10px;
            background: white; cursor: pointer; font-weight: 600; font-size: 0.88em;
            color: var(--bio-green); font-family: "DM Sans", sans-serif; transition: all 0.2s;
        }
        .tab-btn:hover  { border-color: var(--bio-teal); background: var(--bio-green-pale); }
        .tab-btn.active { border-color: var(--bio-green); background: var(--bio-green); color: white; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }

        label {
            display: block; font-weight: 600; font-size: 0.9em;
            color: var(--text); margin-bottom: 7px;
        }

        input[type="file"] {
            width: 100%; padding: 10px 13px;
            border: 1.5px dashed var(--border); border-radius: 10px;
            font-size: 0.88em; font-family: "DM Sans", sans-serif;
            background: var(--bio-green-pale); cursor: pointer;
        }

        small { display: block; margin-top: 6px; font-size: 0.82em; color: var(--text-muted); }

        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }

        .btn {
            display: inline-block;
            background: linear-gradient(135deg, var(--bio-dark), var(--bio-green));
            color: white; border: none; padding: 11px 22px; border-radius: 10px;
            cursor: pointer; font-weight: 700; font-size: 0.92em;
            font-family: "DM Sans", sans-serif; text-decoration: none; transition: opacity 0.2s;
        }
        .btn:hover { opacity: 0.88; }

        .plot-placeholder {
            background: var(--bio-green-pale);
            border: 1.5px dashed var(--border);
            border-radius: 12px; height: 250px;
            display: flex; align-items: center; justify-content: center;
            color: var(--text-muted); font-style: italic; font-size: 0.9em; margin: 15px 0;
        }

        .status-msg {
            padding: 13px 17px; border-radius: 12px; margin: 16px 0;
            font-size: 0.93em; border-left: 4px solid;
        }
        .error   { background: #fdf0ef; color: #8b2a22; border-color: #c0392b; }
        .success { background: var(--bio-green-pale); color: var(--bio-dark); border-color: var(--bio-green); }

        .plot-slider .slider-slide img { cursor: pointer; }
        .plot-expand-overlay {
            position: fixed; inset: 0; background: rgba(0,0,0,0.88);
            z-index: 9999; display: none; align-items: center; justify-content: center;
            cursor: pointer;
        }
        .plot-expand-overlay.show { display: flex; }
        .plot-expand-overlay img { max-width: 95vw; max-height: 95vh; object-fit: contain; pointer-events: none; }

        footer {
            position: relative; z-index: 1;
            background: linear-gradient(180deg, var(--bio-dark) 0%, var(--bio-deep) 100%);
            color: rgba(255,255,255,0.88); padding: 22px 24px; font-size: 0.88rem;
            text-align: center; border-top: 1px solid rgba(13,107,92,0.4); margin-top: 40px;
        }
        footer a { color: #9ae6d9; text-decoration: none; }
        footer a:hover { text-decoration: underline; }
    </style>
    <script>
        function switchModelTab(tabId) {
            document.querySelectorAll('.model-tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.model-tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById('model-tab-' + tabId).classList.add('active');
            document.getElementById('model-content-' + tabId).classList.add('active');
            document.getElementById('model_choice').value = tabId;
        }
    </script>
</head>
<body>

<header class="header">
    <div class="header-inner">
        <h1>Validation &amp; Performance Hub</h1>
        <p>Methodik, Benchmarks &amp; 5-Fold Cross-Validation</p>
        <div class="badge">Gruppe 17</div>
        <div class="hero-dots"><span></span><span></span><span></span></div>
    </div>
</header>

<main class="main">
<div class="main-panel">
""")

# ── 5-Fold Cross-Validation: interaktiv ─────────────────────────────
print("""
    <script>
        function updateGor5Checkboxes() {
            var hasZip = document.getElementById('aln_zip').value !== '';
            var gor5boxes = document.querySelectorAll('.gor5-cb');
            gor5boxes.forEach(function(cb) {
                if (!hasZip) {
                    cb.checked = false;
                    cb.disabled = true;
                    cb.closest('.cv-check-row').classList.add('cv-check-disabled');
                } else {
                    cb.disabled = false;
                    cb.closest('.cv-check-row').classList.remove('cv-check-disabled');
                }
            });
            updateSelectAll();
        }
        function updateSelectAll() {
            var all  = document.querySelectorAll('.cv-method-cb:not(:disabled)');
            var chkd = document.querySelectorAll('.cv-method-cb:not(:disabled):checked');
            var sa   = document.getElementById('select-all-cv');
            if (!sa) return;
            sa.checked       = all.length > 0 && chkd.length === all.length;
            sa.indeterminate = chkd.length > 0 && chkd.length < all.length;
        }
        function toggleSelectAll(cb) {
            var all = document.querySelectorAll('.cv-method-cb:not(:disabled)');
            all.forEach(function(c) { c.checked = cb.checked; });
            updateSelectAll();
        }
    </script>
    <style>
        .cv-check-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin: 12px 0 18px;
        }
        .cv-check-row {
            display: flex; align-items: center; gap: 10px;
            padding: 10px 14px;
            border: 1.5px solid var(--border); border-radius: 10px;
            background: white; cursor: pointer; transition: border-color 0.15s;
            font-size: 0.9em; font-weight: 600; color: var(--bio-dark);
        }
        .cv-check-row:hover:not(.cv-check-disabled) { border-color: var(--bio-teal); background: var(--bio-green-pale); }
        .cv-check-row input[type="checkbox"] {
            width: 17px; height: 17px; accent-color: var(--bio-green);
            cursor: pointer; flex-shrink: 0; margin: 0;
        }
        .cv-check-disabled { opacity: 0.38; cursor: not-allowed; }
        .cv-check-disabled input { cursor: not-allowed; }
        .cv-check-tag {
            margin-left: auto; font-size: 0.72em; font-weight: 700;
            padding: 2px 8px; border-radius: 10px; letter-spacing: 0.05em;
        }
        .tag-gor5 { background: #fff3e0; color: #b45309; border: 1px solid #fcd34d; }
        .select-all-row {
            display: flex; align-items: center; gap: 10px;
            padding: 10px 14px; margin-bottom: 4px;
            border: 1.5px solid var(--bio-green); border-radius: 10px;
            background: var(--bio-green-pale); font-size: 0.9em; font-weight: 700;
            color: var(--bio-green); cursor: pointer;
        }
        .select-all-row input[type="checkbox"] {
            width: 17px; height: 17px; accent-color: var(--bio-green);
            cursor: pointer; flex-shrink: 0; margin: 0;
        }
    </style>
    <section class="card">
        <div class="card-title">5-Fold Cross-Validation</div>
        <h2>Eigene 5CV ausf&uuml;hren</h2>
        <p>W&auml;hle Methoden, lade deine Datenbank hoch und starte die 5CV.
           GOR5-Methoden sind nur verf&uuml;gbar wenn du ein ALN-ZIP hochl&auml;dst.</p>
        <form method="post" enctype="multipart/form-data">

            <label>1. Datenbank hochladen (.db / .txt)</label>
            <input type="file" name="db_file" accept=".db,.txt" required>
            <small>Seclib-Format: Eintr&auml;ge mit &gt; ID, AS ..., SS ... getrennt durch Leerzeilen</small>

            <div style="margin-top:18px">
                <label>2. GOR5-Alignments (optional) &ndash; ZIP mit .aln-Dateien</label>
                <input type="file" name="aln_zip" id="aln_zip" accept=".zip"
                       onchange="updateGor5Checkboxes()">
                <small>Aktiviert GOR5-Optionen unten sobald ein g&uuml;ltiges ZIP ausgew&auml;hlt wird</small>
            </div>

            <div style="margin-top:18px">
                <label>3. Eigenes Modell (optional) &ndash; ersetzt Default-Training</label>
                <input type="file" name="custom_model" accept=".txt,.model">
                <small>Wird nur verwendet wenn kein Default-Modell verf&uuml;gbar ist oder du ein eigenes testen willst</small>
            </div>

            <div style="margin-top:22px">
            <label>4. Methoden ausw&auml;hlen</label>
            <label class="select-all-row">
                <input type="checkbox" id="select-all-cv" checked onchange="toggleSelectAll(this)">
                Alle ausw&auml;hlen / abw&auml;hlen
            </label>
            <div class="cv-check-grid">
                <label class="cv-check-row">
                    <input type="checkbox" class="cv-method-cb" name="cv_methods" value="gor1" checked
                           onchange="updateSelectAll()">
                    GOR I
                </label>
                <label class="cv-check-row">
                    <input type="checkbox" class="cv-method-cb" name="cv_methods" value="gor3" checked
                           onchange="updateSelectAll()">
                    GOR III
                </label>
                <label class="cv-check-row">
                    <input type="checkbox" class="cv-method-cb" name="cv_methods" value="gor4" checked
                           onchange="updateSelectAll()">
                    GOR IV
                </label>
                <label class="cv-check-row cv-check-disabled">
                    <input type="checkbox" class="cv-method-cb gor5-cb" name="cv_methods" value="gor5_gor1"
                           disabled onchange="updateSelectAll()">
                    GOR5 mit GOR I
                    <span class="cv-check-tag tag-gor5">GOR5</span>
                </label>
                <label class="cv-check-row cv-check-disabled">
                    <input type="checkbox" class="cv-method-cb gor5-cb" name="cv_methods" value="gor5_gor3"
                           disabled onchange="updateSelectAll()">
                    GOR5 mit GOR III
                    <span class="cv-check-tag tag-gor5">GOR5</span>
                </label>
                <label class="cv-check-row cv-check-disabled">
                    <input type="checkbox" class="cv-method-cb gor5-cb" name="cv_methods" value="gor5_gor4"
                           disabled onchange="updateSelectAll()">
                    GOR5 mit GOR IV
                    <span class="cv-check-tag tag-gor5">GOR5</span>
                </label>
            </div>
            </div>

            <button type="submit" name="run_cv" value="1"
                    class="btn" style="width:100%; padding:14px; margin-top:20px;
                    border-radius:12px; font-size:1em; letter-spacing:0.03em;">
                5CV starten
            </button>
        </form>
""")

# ── CV Execution ─────────────────────────────────────────────────────
if fs.getvalue("run_cv"):
    import html as _html
    try:
        # --- gewählte Methoden lesen ---
        selected = []
        if "cv_methods" in fs:
            val = fs["cv_methods"]
            if isinstance(val, list):
                selected = [v.value if hasattr(v, 'value') else str(v) for v in val]
            else:
                selected = [val.value if hasattr(val, 'value') else str(val)]
        if not selected:
            raise ValueError("Bitte mindestens eine Methode auswaehlen.")

        base_methods = [m for m in selected if not m.startswith("gor5_")]
        gor5_methods  = [m for m in selected if m.startswith("gor5_")]

        # --- DB als Datei speichern ---
        # --- DB als Datei speichern & bereinigen ---
        db_raw = fs.getvalue("db_file")
        if hasattr(db_raw, 'decode'):
            db_raw = db_raw.decode('utf-8')

        if db_raw:
            # 1. Zeilenenden normalisieren (Wichtig für Java!)
            db_raw = db_raw.replace('\r', '')

            # 2. Präzise Bereinigung: Entfernt nur Tags, die mit [ beginnen
            lines = db_raw.split('\n')
            clean_lines = []
            for line in lines:
                l = line.strip()
                # Falls ein Tag davorsteht (z.B. > 154l), schneiden wir es ab
                if '[' in l and ']' in l and l.find(']') < l.find('>'):
                    l = l.split(']', 1)[-1].strip()

                # Nur relevante Zeilen oder Leerzeilen behalten
                if l.startswith('>') or l.startswith('AS') or l.startswith('SS') or not l:
                    clean_lines.append(l)

            db_raw = '\n'.join(clean_lines).strip()

        # Validierung
        if not db_raw:
            raise ValueError("Die Datei ist nach der Bereinigung leer.")


        tmp_dir = tempfile.mkdtemp()
        work_dir = os.path.join(tmp_dir, "work")
        os.makedirs(work_dir, exist_ok=True)

        # DB speichern
        Path(os.path.join(work_dir, "CB513DSSP.db")).write_text(db_raw)
        # JARs hineinkopieren
        for jar in [JAR_TRAIN, JAR_PREDICT, JAR_VALIDATE]:
            dst = os.path.join(work_dir, os.path.basename(jar))
            if not os.path.exists(dst):
                shutil.copy(jar, dst)

        # --- ALN-ZIP extrahieren fuer GOR5 ---
        aln_dir = None
        if "aln_zip" in fs and fs["aln_zip"].filename:
            aln_zip_raw = fs["aln_zip"].file.read()
            zip_tmp = os.path.join(tmp_dir, "aln.zip")
            with open(zip_tmp, "wb") as zf:
                zf.write(aln_zip_raw)
            try:
                with zipfile.ZipFile(zip_tmp) as z:
                    if [f for f in z.namelist() if f.endswith(".aln")]:
                        maf_dst = os.path.join(work_dir, "CB513MultipleAlignments")
                        os.makedirs(maf_dst, exist_ok=True)
                        z.extractall(maf_dst)
                        aln_dir = maf_dst
                    else:
                        gor5_methods = []
            except zipfile.BadZipFile:
                gor5_methods = []
                print("<div class='status-msg error'>Ungueltige ALN-ZIP - GOR5 uebersprungen.</div>")

        if gor5_methods and not aln_dir:
            print("<div class='status-msg error'>GOR5 gewaehlt aber kein ALN-ZIP - GOR5 uebersprungen.</div>")
            gor5_methods = []

        # --- 5cv.py kopieren und ausfuehren ---
        cv_script = os.path.join(CGI_DIR, "5cv.py")
        shutil.copy(cv_script, os.path.join(work_dir, "5cv.py"))

        # Baue die Argumentliste: ["python3", "5cv.py", "gor1", "gor4", "gor5_gor4", ...]
        cmd = ["python3", "5cv.py"] + selected

        r = subprocess.run(
            cmd,
            cwd=work_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        cv_stdout = (r.stdout or b"").decode("utf-8", errors="replace")
        cv_stderr = (r.stderr or b"").decode("utf-8", errors="replace")

        if r.returncode != 0:
            raise RuntimeError(
                "5cv.py Fehler (exit " + str(r.returncode) + "):\n"
                + (cv_stderr or cv_stdout)[:600]
            )

        # --- Ergebnisse aus stdout parsen (Schlusstabelle von 5cv.py) ---
        # Format: Method  Q3_overall  Q3_H  Q3_E  Q3_C  SOV  SOV_H  SOV_E  SOV_C
        all_results = {}
        lines = cv_stdout.strip().split("\n")
        in_table = False
        for line in lines:
            if line.startswith("Method") or line.startswith("---"):
                in_table = True
                continue
            if not in_table:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            m = parts[0]
            try:
                q3  = float(parts[1]) if len(parts) > 1 else None
                qh  = float(parts[2]) if len(parts) > 2 else None
                qe  = float(parts[3]) if len(parts) > 3 else None
                qc  = float(parts[4]) if len(parts) > 4 else None
                sov = float(parts[5]) if len(parts) > 5 else None
            except ValueError:
                continue
            # nur gewaehlte Methoden
            is_gor5  = m.startswith("gor5_")
            base_key = m.replace("gor5_", "")
            if is_gor5 and base_key not in [g.replace("gor5_","") for g in gor5_methods]:
                continue
            if not is_gor5 and m not in base_methods:
                continue
            all_results[m] = {"Q3": q3, "H": qh, "E": qe, "C": qc, "SOV": sov}

        # --- fold-weise Q3 aus summary-files ---
        fold_scores = {}
        for m in base_methods + gor5_methods:
            fold_scores[m] = []
            for fold in range(1, 6):
                fname = os.path.join(work_dir, m + "_fold" + str(fold) + "_summary.txt")
                if os.path.exists(fname):
                    s = parse_summary_file(fname)
                    fold_scores[m].append(s.get("Q3"))
                else:
                    fold_scores[m].append(None)

        # --- ZIP der Fold-Ergebnisse ---
        zip_path = os.path.join(tmp_dir, "5CV_Results.zip")
        with zipfile.ZipFile(zip_path, "w") as zipf:
            for m in base_methods + gor5_methods:
                for fold in range(1, 6):
                    for fpath, arcname in [
                        (os.path.join(work_dir, m+"_fold"+str(fold)+".txt"),       "fold"+str(fold)+"/"+m+"/pred.txt"),
                        (os.path.join(work_dir, m+"_fold"+str(fold)+"_summary.txt"),"fold"+str(fold)+"/"+m+"/summary.txt"),
                        (os.path.join(work_dir, m+"_fold"+str(fold)+"_detailed.txt"),"fold"+str(fold)+"/"+m+"/detailed.txt"),
                    ]:
                        if os.path.exists(fpath):
                            zipf.write(fpath, arcname=arcname)

        # --- Ergebnistabelle HTML ---
        method_labels = {
            "gor1": "GOR I", "gor3": "GOR III", "gor4": "GOR IV",
            "gor5_gor1": "GOR5 (GOR I)", "gor5_gor3": "GOR5 (GOR III)", "gor5_gor4": "GOR5 (GOR IV)",
        }
        order = ["gor1","gor3","gor4","gor5_gor1","gor5_gor3","gor5_gor4"]
        method_order = [m for m in order if m in all_results]

        def fmt(v): return (("%.2f" % v) + "%") if v is not None else "&mdash;"
        def scls(v):
            if v is None: return ""
            return "score-good" if v >= 70 else ("score-mid" if v >= 55 else "score-low")

        th = ("<th>Methode</th>"
              + "".join("<th>Fold&nbsp;" + str(i+1) + "</th>" for i in range(5))
              + "<th><strong>&#216;&nbsp;Q3</strong></th><th>&#216;&nbsp;SOV</th>")
        rows = ""
        for m in method_order:
            sc   = all_results[m]
            aq3  = sc.get("Q3")
            asov = sc.get("SOV")
            fq3s = fold_scores.get(m, [None]*5)
            cells = "".join("<td>" + fmt(v) + "</td>" for v in fq3s)
            row_style = " style='background:#fffbf2'" if m.startswith("gor5_") else ""
            rows += ("<tr" + row_style + "><td><strong>" + method_labels.get(m,m) + "</strong></td>"
                     + cells
                     + "<td class='" + scls(aq3) + "'><strong>" + fmt(aq3) + "</strong></td>"
                     + "<td>" + fmt(asov) + "</td></tr>")

        b64_zip = base64.b64encode(open(zip_path, "rb").read()).decode()
        n_done  = len(method_order)
        plural  = "n" if n_done != 1 else ""

        print("<div class=\"status-msg success\" style=\"margin-top:16px\">")
        print("<strong>5CV abgeschlossen!</strong> &nbsp; " + str(n_done) + " Methode" + plural + " evaluiert.")
        print("</div>")
        print("<div style=\"overflow-x:auto; margin:14px 0\">")
        print("<table class=\"score-table\">")
        print("<thead><tr>" + th + "</tr></thead>")
        print("<tbody>" + rows + "</tbody>")
        print("</table></div>")
        print("<a href=\"data:application/zip;base64," + b64_zip + "\" download=\"5CV_Results.zip\"")
        print("   class=\"btn\" style=\"margin-top:4px\">&#11015; Alle Folds herunterladen (ZIP)</a>")

        shutil.rmtree(tmp_dir, ignore_errors=True)

    except Exception as e:
        print("<div class='status-msg error'><strong>Fehler:</strong> " + _html.escape(str(e)) + "</div>")

print("""
        <div style="margin-top:20px;padding-top:20px;border-top:1px solid var(--bio-green-light)">
            <p style="font-size:0.9em;color:var(--text-muted)">
                <strong style="color:var(--bio-dark)">Wie wir das gemacht haben:</strong>
                Die CB513-Proteine werden aufsteigend nach Sequenzl&auml;nge sortiert und durch
                zyklische Zuweisung auf 5 Folds verteilt, sodass jeder Fold eine repr&auml;sentative
                L&auml;ngenverteilung hat. In jeder Iteration dienen vier Folds als Training,
                einer als Test. F&uuml;r GOR5 werden pro Fold nur die <code>.aln</code>-Dateien
                der jeweiligen Test-Proteine verwendet (kein Data-Leakage).
                Alle Scores (Q3, SOV) werden &uuml;ber alle 5 Folds gemittelt.
            </p>
        </div>
    </section>
""")

# ── Training & Datenbasis ────────────────────────────────────────────
print("""
    <section class="card">
        <div class="card-title">Training &amp; Datenbasis</div>
        <h2>Der CB513 Datensatz</h2>
        <p>CB513 ist der Goldstandard f&uuml;r die Evaluation von Sekund&auml;rstrukturvorhersagen.
           Er enth&auml;lt 513 nicht-redundante Proteine mit einer Sequenzidentit&auml;t von &lt;&nbsp;25&nbsp;%.</p>

        <div class="plot-slider" id="cb513-slider">
            <div class="slider-track">
                <div class="slider-slide active">
                    <img src="plots/CB513/CB513States.png" alt="Verteilung der Struktur-States">
                    <div class="slide-caption">Klassenverteilung H / E / C im CB513-Datensatz</div>
                </div>
                <div class="slider-slide">
                    <img src="plots/CB513/CB513Laenge.png" alt="Verteilung der Sequenzlaengen">
                    <div class="slide-caption">Verteilung der Sequenzl&auml;ngen im CB513-Datensatz</div>
                </div>
            </div>
            <button class="slider-btn prev" onclick="slideCB513(-1)">&#8592;</button>
            <button class="slider-btn next" onclick="slideCB513(1)">&#8594;</button>
            <div class="slider-dots">
                <span class="dot active" onclick="goToSlide(0)"></span>
                <span class="dot" onclick="goToSlide(1)"></span>
            </div>
        </div>
    </section>

    <style>
        .plot-slider { position: relative; margin: 15px 0; background: var(--bio-green-pale);
            border: 1.5px solid var(--border); border-radius: 12px; overflow: hidden; }
        .slider-track { display: flex; transition: transform 0.4s ease; }
        .slider-slide { min-width: 100%; display: flex; flex-direction: column;
            align-items: center; padding: 16px; }
        .slider-slide img { max-width: 100%; max-height: 280px; object-fit: contain;
            border-radius: 8px; }
        .slide-caption { margin-top: 8px; font-size: 0.85em; color: var(--text-muted);
            font-style: italic; }
        .slider-btn { position: absolute; top: 50%; transform: translateY(-50%);
            background: var(--bio-green); color: white; border: none; border-radius: 50%;
            width: 36px; height: 36px; font-size: 1.1em; cursor: pointer;
            display: flex; align-items: center; justify-content: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2); transition: opacity 0.2s; z-index: 2; }
        .slider-btn:hover { opacity: 0.8; }
        .slider-btn.prev { left: 10px; }
        .slider-btn.next { right: 10px; }
        .slider-dots { display: flex; justify-content: center; gap: 8px; padding: 8px 0 12px; }
        .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--border);
            cursor: pointer; transition: background 0.2s; }
        .dot.active { background: var(--bio-green); }
    </style>
    <script>
        var cb513Index = 0;
        function slideCB513(dir) {
            var slides = document.querySelectorAll('#cb513-slider .slider-slide');
            cb513Index = (cb513Index + dir + slides.length) % slides.length;
            goToSlide(cb513Index);
        }
        function goToSlide(i) {
            cb513Index = i;
            var track = document.querySelector('#cb513-slider .slider-track');
            track.style.transform = 'translateX(-' + (i * 100) + '%)';
            document.querySelectorAll('#cb513-slider .dot').forEach(function(d, idx) {
                d.classList.toggle('active', idx === i);
            });
        }
    </script>
""")

# ── Hyperparameter-Tuning ────────────────────────────────────────────
print("""
    <section class="card">
        <div class="card-title">Optimierung</div>
        <h2>Hyperparameter-Tuning (80/20 Split)</h2>
        <p>Die Optimierung der Hyperparameter erfolgte auf einem separaten 80/20-Split von CB513, um Overfitting auf den Testdaten der 5-fachen Kreuzvalidierung (5CV) zu vermeiden. Hierbei wurden neben den Pseudocounts zur statistischen Regularisierung auch die Parameter Min_E und Min_H bestimmt. Diese dienen als Mindestlängen-Schwellenwerte, um physikalisch unplausible Einzelvorhersagen von Strand- (E) oder Helix-Elementen (H) im Post-processing zu glätten.</p>

        <div class="plot-slider" id="param-slider">
            <div class="slider-track">
                <div class="slider-slide">
                    <img src="plots/parameterplots/plot3_best_overview.png" alt="Fensterbreite vs. Q3">
                    <div class="slide-caption">Post-processing vs. Q3 &ndash; Optimierung der minimalen H/E-Parameter</div>
                </div>
                <div class="slider-slide">
                    <img src="plots/parameterplots/plot2_pseudocount.png" alt="Pseudocounts Analyse">
                    <div class="slide-caption">Pseudocount-Analyse &ndash; Einfluss auf die Vorhersagequalit&auml;t</div>
                </div>
            </div>
            <button class="slider-btn prev" onclick="slideParam(-1)">&#8592;</button>
            <button class="slider-btn next" onclick="slideParam(1)">&#8594;</button>
            <div class="slider-dots">
                <span class="dot active" onclick="goToParamSlide(0)"></span>
                <span class="dot" onclick="goToParamSlide(1)"></span>
            
            </div>
        </div>
    </section>

    <script>
        var paramIndex = 0;
        function slideParam(dir) {
            var slides = document.querySelectorAll('#param-slider .slider-slide');
            paramIndex = (paramIndex + dir + slides.length) % slides.length;
            goToParamSlide(paramIndex);
        }
        function goToParamSlide(i) {
            paramIndex = i;
            var track = document.querySelector('#param-slider .slider-track');
            track.style.transform = 'translateX(-' + (i * 100) + '%)';
            document.querySelectorAll('#param-slider .dot').forEach(function(d, idx) {
                d.classList.toggle('active', idx === i);
            });
        }
    </script>
""")
# ── CASP & MSA Test-Set ──────────────────────────────────────────────
print("""
    <section class="card">
        <div class="card-title">Independent Testing</div>
        <h2>Eigenes CASP Test-Set</h2>

        <p><strong>Was ist CASP?</strong> Critical Assessment of Structure Prediction &ndash;
           ein internationaler Blind-Test-Wettbewerb, bei dem Gruppen weltweit Vorhersagen
           für neu gelöste Proteinstrukturen einreichen, bevor diese veröffentlicht werden.
           Damit ist CASP der härteste unabhängige Benchmark für Strukturvorhersagemethoden.</p>

        <div style="background:#fff8f0; border:1.5px solid #fcd34d; border-radius:12px;
                    padding:16px 20px; margin:16px 0;">
            <p style="font-weight:700; color:#b45309; margin-bottom:10px; font-size:0.9em;
                      text-transform:uppercase; letter-spacing:0.06em;">
                &#9889; Warum ist CASP so anspruchsvoll?
            </p>
            <p style="margin-bottom:8px">
                <strong>Echter Blindtest:</strong> Die Zielstrukturen sind zum Zeitpunkt der
                Vorhersage noch nicht öffentlich &ndash; Methoden können sich nicht auf bekannte
                Lösungen stützen.
            </p>
            <p style="margin-bottom:8px">
                <strong>Evolutionär neuartige Sequenzen:</strong> CASP-Targets werden bewusst so
                gewählt, dass sie wenig Ähnlichkeit zu bereits bekannten Strukturen haben.
            </p>
            <p style="margin-bottom:0">
                <strong>Kein Overfitting möglich:</strong> Da wir CASP-Daten nie für Training
                oder Hyperparameter-Tuning verwendet haben, misst dieses Test-Set die echte
                Generalisierungsfähigkeit unserer Modelle.
            </p>
        </div>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin:12px 0 16px;">
            <div style="background:var(--bio-green-pale); border:1px solid var(--border);
                        border-radius:10px; padding:14px 16px;">
                <div style="font-size:0.78em; font-weight:700; text-transform:uppercase;
                            letter-spacing:0.07em; color:var(--bio-green); margin-bottom:6px;">
                    1. Datenquelle
                </div>
                <p style="font-size:0.9em; margin:0">
                    <strong>81 DSSP-Dateien</strong> aus CASP 10-14 &ndash; offiziell veröffentlichte
                    Experimentalstrukturen.
                </p>
            </div>
            <div style="background:var(--bio-green-pale); border:1px solid var(--border);
                        border-radius:10px; padding:14px 16px;">
                <div style="font-size:0.78em; font-weight:700; text-transform:uppercase;
                            letter-spacing:0.07em; color:var(--bio-green); margin-bottom:6px;">
                    2. Redundanzfilter
                </div>
                <p style="font-size:0.9em; margin:0">
                    Sequenzidentität &lt; 30 % gegenüber CB513 (Needleman-Wunsch). Kein Datenleck.
                </p>
            </div>
        </div>

        <div class="plot-slider" id="casp-slider">
            <div class="slider-track">
                <div class="slider-slide">
                    <img src="plots/CASP/CASPStates.png" alt="Klassenverteilung CASP">
                    <div class="slide-caption">Klassenverteilung H / E / C im CASP Test-Set</div>
                </div>
                <div class="slider-slide">
                    <img src="plots/CASP/CASPLaenge.png" alt="Sequenzlaengen CASP">
                    <div class="slide-caption">Sequenzl&auml;ngenverteilung &ndash; bimodal durch heterogene Targets</div>
                </div>
                <div class="slider-slide">
                    <img src="plots/gorOnCASP/Q3CASP.png" alt="Q3 Performance CASP">
                    <div class="slide-caption">Performance-Analyse: Q3-Scores auf dem CASP Test-Set</div>
                </div>
                <div class="slider-slide">
                    <img src="plots/gorOnCASP/SOVCASP.png" alt="SOV Performance CASP">
                    <div class="slide-caption">Segment-OVerlap (SOV) Score &ndash; Vergleich der Vorhersageg&uuml;te</div>
                </div>
            </div>

            <button class="slider-btn prev" onclick="slideCASP(-1)">&#8592;</button>
            <button class="slider-btn next" onclick="slideCASP(1)">&#8594;</button>

            <div class="slider-dots">
                <span class="dot active" onclick="goToCASPSlide(0)"></span>
                <span class="dot" onclick="goToCASPSlide(1)"></span>
                <span class="dot" onclick="goToCASPSlide(2)"></span>
                <span class="dot" onclick="goToCASPSlide(3)"></span>
            </div>
        </div>

        <script>
            var caspIndex = 0;
            function slideCASP(dir) {
                var slides = document.querySelectorAll('#casp-slider .slider-slide');
                caspIndex = (caspIndex + dir + slides.length) % slides.length;
                goToCASPSlide(caspIndex);
            }
            function goToCASPSlide(i) {
                caspIndex = i;
                var track = document.querySelector('#casp-slider .slider-track');
                track.style.transform = 'translateX(-' + (i * 100) + '%)';
                document.querySelectorAll('#casp-slider .dot').forEach(function(d, idx) {
                    d.classList.toggle('active', idx === i);
                });
            }
        </script>
    </section>
""")

# ── PSIPRED-Vergleich ────────────────────────────────────────────────
print("""
    <section class="card">
        <div class="card-title">Benchmarks</div>
        <h2>Vergleich mit PSIPRED</h2>

        <p><strong>Was ist PSIPRED?</strong> PSIPRED ist ein Industriestandard zur Sekund&auml;rstrukturvorhersage. Er nutzt ein zweistufiges neuronales Netzwerk, das auf evolution&auml;ren Informationen (PSSMs aus PSI-BLAST) basiert. Da PSIPRED seit Jahrzehnten als einer der stabilsten Algorithmen gilt, dient er als idealer Benchmark, um die Vorhersagekraft unserer GOR-Implementierungen einzuordnen.</p>

        <div style="background:var(--bio-green-pale); border-left:4px solid var(--bio-green); padding:12px 16px; margin:16px 0; font-size:0.92em;">
            <strong>Test-Methodik:</strong> Der Vergleich erfolgte auf zwei Datens&auml;tzen:
            <ul style="margin:8px 0 0 20px; padding:0;">
                <li><strong>5-fache Kreuzvalidierung (5CV):</strong> Auf dem CB513-Datensatz zur Messung der internen Konsistenz.</li>
                <li><strong>CASP Test-Set:</strong> Unser eigenst&auml;ndiges, redundanzfreies Set zur Messung der echten Generalisierungsf&auml;higkeit.</li>
            </ul>
        </div>

        <div class="plot-slider" id="psi-slider">
            <div class="slider-track">
                <div class="slider-slide">
                    <img src="plots/Benchmarking/CASPPSIPRED5CVQ3.png" alt="Q3 Vergleich PSIPRED">
                    <div class="slide-caption">
                        <strong>Q3-Performance:</strong> GOR IV vs. GOR V vs. PSIPRED 
                        <span style="display:block; font-size:0.85em; color:#666; margin-top:2px;">Drei-Zustands-Genauigkeit (CB513 5CV & CASP)</span>
                    </div>
                </div>
                <div class="slider-slide">
                    <img src="plots/Benchmarking/CASPPSIPRED5CVSOV.png" alt="SOV Vergleich PSIPRED">
                    <div class="slide-caption">
                        <strong>SOV-Score:</strong> Segment-Overlap Vergleich
                        <span style="display:block; font-size:0.85em; color:#666; margin-top:2px;">Bewertung der strukturellen Realit&auml;t im Vergleich zum Benchmark</span>
                    </div>
                </div>
            </div>

            <button class="slider-btn prev" onclick="slidePSI(-1)">&#8592;</button>
            <button class="slider-btn next" onclick="slidePSI(1)">&#8594;</button>

            <div class="slider-dots">
                <span class="dot active" onclick="goToPSISlide(0)"></span>
                <span class="dot" onclick="goToPSISlide(1)"></span>
            </div>
        </div>

        <script>
            var psiIndex = 0;
            function slidePSI(dir) {
                var slides = document.querySelectorAll('#psi-slider .slider-slide');
                psiIndex = (psiIndex + dir + slides.length) % slides.length;
                goToPSISlide(psiIndex);
            }
            function goToPSISlide(i) {
                psiIndex = i;
                var track = document.querySelector('#psi-slider .slider-track');
                track.style.transform = 'translateX(-' + (i * 100) + '%)';
                document.querySelectorAll('#psi-slider .dot').forEach(function(d, idx) {
                    d.classList.toggle('active', idx === i);
                });
            }
        </script>
    </section>

</div>
</main>

<div style="text-align:center; padding: 28px 0 8px;">
    <a href="../index.html"
       style="display:inline-flex; align-items:center; gap:8px;
              background: linear-gradient(135deg, var(--bio-dark), var(--bio-green));
              color:white; text-decoration:none; padding:13px 32px;
              border-radius:50px; font-family:'DM Sans',sans-serif;
              font-size:0.95em; font-weight:600; letter-spacing:0.03em;
              box-shadow:0 4px 16px rgba(13,107,92,0.25);
              transition: transform 0.15s, box-shadow 0.15s;"
       onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='0 6px 22px rgba(13,107,92,0.35)'"
       onmouseout="this.style.transform='';this.style.boxShadow='0 4px 16px rgba(13,107,92,0.25)'">
        &#8592; Zur&uuml;ck zur Hauptseite
    </a>
</div>

<footer>
    Programmierpraktikum WS 25/26 &middot; Gruppe 17
</footer>

<div id="plot-expand-overlay" class="plot-expand-overlay" title="Klicken zum Schlie&szlig;en">
    <img src="" alt="">
</div>
<script>
document.addEventListener('DOMContentLoaded', function() {
    var overlay = document.getElementById('plot-expand-overlay');
    var overlayImg = overlay.querySelector('img');
    document.querySelectorAll('.plot-slider .slider-slide img').forEach(function(img) {
        img.addEventListener('click', function(e) {
            e.stopPropagation();
            overlayImg.src = this.src;
            overlayImg.alt = this.alt;
            overlay.classList.add('show');
        });
    });
    overlay.addEventListener('click', function() {
        this.classList.remove('show');
    });
});
</script>

</body>
</html>
""")
