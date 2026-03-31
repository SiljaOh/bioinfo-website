#!/usr/bin/python3

import subprocess
import html
import base64
import os
import cgi
import tempfile
import urllib.request
from mycgi import Form

CGI_DIR = os.path.dirname(os.path.abspath(__file__))
JAR_PATH = os.path.join(CGI_DIR, "train.jar")
CB513_PATH = "/mnt/extstud/praktikum/bioprakt/Data/GOR/CB513/CB513DSSP.db"
GET_SECLIB = os.path.join(CGI_DIR, "get_seclib.py")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def run_gor_train(db_path, method, model_out):
    cmd = [
        "java", "-cp", JAR_PATH, "de.lmu.ifi.bio.gor.cli.Train",
        "--db", db_path,
        "--method", str(method),
        "--model", model_out
    ]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=300
        )
        return result
    except Exception as e:
        return e


def is_model_empty(model_path):
    with open(model_path, "r") as f:
        content = f.read()
    numbers = [x for x in content.split() if x.lstrip('-').isdigit()]
    return bool(numbers) and all(x == '0' for x in numbers)


def sanitize_model_name(name):
    """Bereinigt den Modellnamen: kein Pfad-Traversal, keine gefährlichen Zeichen."""
    name = os.path.basename(name.strip())
    # Nur erlaubte Zeichen
    name = "".join(c for c in name if c.isalnum() or c in ('_', '-', '.'))
    if not name:
        name = "my_gor_model.model"
    # Endung sicherstellen
    if '.' not in name:
        name += ".model"
    return name


def fetch_pdb_as_seclib(pdb_id):
    pdb_id = pdb_id.strip().upper()
    if not pdb_id or len(pdb_id) != 4 or not pdb_id.isalnum():
        return None, f"Ungültige PDB ID: '{html.escape(pdb_id)}'. Eine PDB ID besteht aus genau 4 alphanumerischen Zeichen (z.B. 1TIM, 2HHB)."

    tmp_pdb = tempfile.NamedTemporaryFile(suffix=".pdb", delete=False, prefix=pdb_id + "_")
    tmp_seclib = tempfile.NamedTemporaryFile(suffix=".seclib", delete=False, mode='w')
    tmp_pdb.close()
    tmp_seclib.close()

    try:
        url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as response:
                with open(tmp_pdb.name, 'wb') as f:
                    f.write(response.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None, f"PDB ID '{pdb_id}' existiert nicht in der PDB."
            return None, f"HTTP Fehler {e.code} beim Laden von PDB '{pdb_id}'."
        except urllib.error.URLError as e:
            return None, f"Netzwerkfehler: {str(e.reason)}"

        if os.path.getsize(tmp_pdb.name) < 100:
            return None, f"PDB ID '{pdb_id}' lieferte keine gültige Datei."

        try:
            proc = subprocess.Popen(
                ["python3", GET_SECLIB, "--PDB", tmp_pdb.name, "--output", tmp_seclib.name],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            _, err = proc.communicate(timeout=60)
            if proc.returncode != 0:
                return None, f"Fehler bei der Konvertierung von '{pdb_id}': {err.decode('utf-8', errors='replace')[:200]}"
        except Exception as e:
            return None, f"get_seclib.py Fehler: {e}"

        if os.path.getsize(tmp_seclib.name) == 0:
            return None, f"PDB '{pdb_id}' enthält keine verwertbaren Protein-Ketten (RNA/DNA oder leer)."

        return tmp_seclib.name, None

    except Exception as e:
        return None, f"Unerwarteter Fehler: {str(e)}"
    finally:
        if os.path.exists(tmp_pdb.name):
            os.unlink(tmp_pdb.name)


def main():
    fs = cgi.FieldStorage()
    form = Form()

    print("Content-Type: text/html; charset=utf-8\n")

    print("""
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GOR Model Trainer</title>
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
            content: ""; position: fixed; inset: 0;
            background:
                linear-gradient(180deg, rgba(13,107,92,0.06) 0%, transparent 40%),
                radial-gradient(ellipse 80% 50% at 50% -20%, rgba(42,157,143,0.15), transparent),
                repeating-linear-gradient(0deg, transparent, transparent 32px, rgba(13,107,92,0.03) 32px, rgba(13,107,92,0.03) 33px),
                repeating-linear-gradient(90deg, transparent, transparent 32px, rgba(13,107,92,0.03) 32px, rgba(13,107,92,0.03) 33px);
            pointer-events: none; z-index: 0;
        }
        .header {
            position: relative;
            background: linear-gradient(160deg, var(--bio-deep) 0%, var(--bio-dark) 40%, var(--bio-green) 100%);
            color: #fff; padding: 40px 24px 48px; text-align: center; overflow: hidden;
        }
        .header::after {
            content: ""; position: absolute; bottom: 0; left: 0; right: 0; height: 60px;
            background: linear-gradient(to top, var(--bio-deep), transparent); pointer-events: none;
        }
        .header-inner { position: relative; z-index: 1; }
        .header h1 { margin: 0 0 6px; font-size: 1.6rem; font-weight: 700; letter-spacing: 0.02em; }
        .header p  { margin: 0; opacity: 0.85; font-size: 0.95rem; }
        .hero-dots { display: flex; gap: 8px; justify-content: center; margin-top: 14px; }
        .hero-dots span { width: 8px; height: 8px; border-radius: 50%; background: rgba(255,255,255,0.45); }
        .main { position: relative; z-index: 1; max-width: 900px; margin: -24px auto 0; padding: 0 20px 56px; }
        .main-panel {
            background: linear-gradient(180deg, rgba(255,255,255,0.97) 0%, rgba(248,252,251,0.98) 100%);
            border-radius: 20px; padding: 36px 32px 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.25), 0 0 0 1px rgba(255,255,255,0.1) inset;
        }
        .card {
            background: var(--card-bg); border: 1px solid var(--border); border-radius: 14px;
            padding: 24px 24px 20px; margin-bottom: 20px;
        }
        .card-title {
            font-size: 0.78em; font-weight: 700; text-transform: uppercase;
            letter-spacing: 0.08em; color: var(--bio-green); margin-bottom: 16px;
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
        select, input[type="text"] {
            width: 100%; padding: 10px 13px; border: 1.5px solid var(--border); border-radius: 10px;
            font-size: 0.93em; font-family: "DM Sans", sans-serif; color: var(--text);
            background: var(--bio-green-pale); outline: none; transition: border-color 0.2s;
        }
        select:focus, input[type="text"]:focus { border-color: var(--bio-teal); background: white; }
        input[type="file"] {
            width: 100%; padding: 10px 13px; border: 1.5px dashed var(--border); border-radius: 10px;
            font-size: 0.88em; font-family: "DM Sans", sans-serif;
            background: var(--bio-green-pale); cursor: pointer;
        }
        small { display: block; margin-top: 6px; font-size: 0.82em; color: var(--text-muted); }
        .submit-btn {
            width: 100%; padding: 14px;
            background: linear-gradient(135deg, var(--bio-dark), var(--bio-green));
            color: white; border: none; border-radius: 12px; font-size: 1em; font-weight: 700;
            font-family: "DM Sans", sans-serif; cursor: pointer; letter-spacing: 0.03em;
            transition: opacity 0.2s; margin-top: 5px;
        }
        .submit-btn:hover { opacity: 0.88; }
        .status-msg {
            padding: 13px 17px; border-radius: 12px; margin: 16px 0;
            font-size: 0.93em; border-left: 4px solid;
        }
        .error   { background: #fdf0ef; color: #8b2a22; border-color: #c0392b; }
        .success { background: var(--bio-green-pale); color: var(--bio-dark); border-color: var(--bio-green); }
        .info    { background: #eef5fb; color: #1a4d7a; border-color: #2980b9; }
        .warning { background: #fffbec; color: #7a5500; border-color: #e0a800; }
        .preview-box {
            background: #1a2e2a; color: #a8d5bc; padding: 20px; border-radius: 12px;
            font-family: "JetBrains Mono", monospace; font-size: 0.85em; white-space: pre;
            max-height: 280px; overflow-y: auto; overflow-x: auto; margin-top: 16px;
        }
        .preview-title {
            font-weight: 700; font-size: 0.9em; color: var(--bio-green);
            margin: 20px 0 4px; text-transform: uppercase; letter-spacing: 0.06em;
        }
        .download-btn {
            display: inline-block;
            background: linear-gradient(135deg, var(--bio-dark), var(--bio-green));
            color: white; padding: 11px 22px; text-decoration: none; border-radius: 10px;
            font-weight: 700; font-size: 0.92em; margin-top: 14px; transition: opacity 0.2s;
        }
        .download-btn:hover { opacity: 0.88; }
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
        function switchTab(tabId) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById('tab-' + tabId).classList.add('active');
            document.getElementById('content-' + tabId).classList.add('active');
            document.getElementById('input_mode').value = tabId;
        }
    </script>
</head>
<body>

<header class="header">
    <div class="header-inner">
        <h1>GOR Model Training</h1>
        <p>WS 2025/2026 <span>&middot;</span> Gruppe 17</p>
        <div class="hero-dots"><span></span><span></span><span></span></div>
    </div>
</header>

<main class="main">
<div class="main-panel">
    <form method="post" enctype="multipart/form-data">
        <input type="hidden" name="input_mode" id="input_mode" value="internal">

        <div class="card">
            <div class="card-title">1. Trainingsdaten wählen</div>
            <div class="tab-buttons">
                <button type="button" class="tab-btn active" id="tab-internal" onclick="switchTab('internal')">Interne DB</button>
                <button type="button" class="tab-btn" id="tab-pdbid" onclick="switchTab('pdbid')">PDB ID</button>
                <button type="button" class="tab-btn" id="tab-upload" onclick="switchTab('upload')">Datei hochladen</button>
            </div>

            <div class="tab-content active" id="content-internal">
                <label>Interne Datenbank auswählen</label>
                <select name="internal_db">
                    <option value="cb513">CB513 (513 Proteine, Benchmark)</option>
                </select>
            </div>

            <div class="tab-content" id="content-pdbid">
                <label>PDB IDs (kommagetrennt)</label>
                <input type="text" name="pdb_id" placeholder="z.B. 1TIM, 2HHB, 1CRN...">
                <small>Mehrere 4-stellige PDB IDs kommagetrennt. Nur Protein-Strukturen werden unterstützt.</small>
            </div>

            <div class="tab-content" id="content-upload">
                <label>Datei hochladen (.seclib, .db, .pdb, .dssp)</label>
                <input type="file" name="upload_file" accept=".seclib,.db,.pdb,.dssp">
                <small>Erlaubte Formate: .seclib, .db, .pdb, .dssp &ndash; max. 10 MB</small>
            </div>
        </div>

        <div class="card">
            <div class="card-title">2. GOR Algorithmus wählen</div>
            <label>Methode</label>
            <select name="method">
                <option value="gor1">GOR I</option>
                <option value="gor3">GOR III</option>
                <option value="gor4">GOR IV</option>
            </select>
        </div>

        <div class="card">
            <div class="card-title">3. Modell-Ausgabedatei</div>
            <label>Dateiname (z.B. mein_modell.model)</label>
            <input type="text" name="model_name" value="my_gor_model.model">
            <small>Erlaubte Zeichen: Buchstaben, Zahlen, _ - . &ndash; Endung wird automatisch ergänzt.</small>
        </div>

        <button type="submit" name="train_action" class="submit-btn">Training starten</button>
    </form>
    """)

    if "train_action" in fs:
        input_mode = fs.getvalue("input_mode") or "internal"
        method     = fs.getvalue("method") or "gor1"

        # ── Modellname bereinigen ─────────────────────────────────────────────
        model_name = sanitize_model_name(fs.getvalue("model_name") or "my_gor_model.model")

        tmp_files  = []
        final_db   = None
        error_msg  = None

        # ── JAR prüfen ────────────────────────────────────────────────────────
        if not os.path.exists(JAR_PATH):
            error_msg = "train.jar nicht gefunden – bitte den Administrator informieren."

        if not error_msg:
            if input_mode == "internal":
                if not os.path.exists(CB513_PATH):
                    error_msg = "Interne Datenbank (CB513) nicht gefunden."
                else:
                    final_db = CB513_PATH

            elif input_mode == "pdbid":
                pdb_raw = (fs.getvalue("pdb_id") or "").strip()
                if not pdb_raw:
                    error_msg = "Bitte mindestens eine PDB ID eingeben."
                else:
                    pdb_ids = [x.strip() for x in pdb_raw.split(",") if x.strip()]
                    combined_seclib = ""
                    for pid in pdb_ids:
                        print(f"<div class='status-msg info'>Lade PDB <strong>{html.escape(pid.upper())}</strong> von rcsb.org…</div>")
                        seclib_path, err = fetch_pdb_as_seclib(pid)
                        if err:
                            error_msg = err
                            break
                        with open(seclib_path, 'r') as f:
                            combined_seclib += f.read() + "\n"
                        os.unlink(seclib_path)

                    if not error_msg:
                        if not combined_seclib.strip():
                            error_msg = "Keine verwertbaren Protein-Daten aus den PDB IDs erhalten."
                        else:
                            tmp_combined = tempfile.NamedTemporaryFile(suffix=".seclib", delete=False, mode='w')
                            tmp_combined.write(combined_seclib)
                            tmp_combined.close()
                            final_db = tmp_combined.name
                            tmp_files.append(final_db)

            elif input_mode == "upload":
                if "upload_file" in fs and fs["upload_file"].filename:
                    uploaded = fs["upload_file"]
                    allowed  = {'.seclib', '.db', '.pdb', '.dssp'}
                    suffix   = os.path.splitext(uploaded.filename)[1].lower()
                    if suffix not in allowed:
                        error_msg = f"Ungültiges Dateiformat '{html.escape(suffix)}'. Erlaubt: .seclib, .db, .pdb, .dssp"
                    else:
                        data = uploaded.file.read(MAX_UPLOAD_BYTES + 1)
                        if len(data) > MAX_UPLOAD_BYTES:
                            error_msg = "Datei zu groß – maximum 10 MB erlaubt."
                        elif len(data) == 0:
                            error_msg = "Hochgeladene Datei ist leer."
                        else:
                            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
                            tmp.write(data)
                            tmp.close()
                            final_db = tmp.name
                            tmp_files.append(final_db)
                else:
                    error_msg = "Bitte eine Datei auswählen."

        if error_msg:
            print(f"<div class='status-msg error'><strong>Fehler:</strong> {html.escape(error_msg)}</div>")
        elif final_db:
            res = run_gor_train(final_db, method, model_name)

            if isinstance(res, subprocess.CompletedProcess):
                if res.returncode == 0:
                    if not os.path.exists(model_name):
                        print("<div class='status-msg error'><strong>Fehler:</strong> Modelldatei wurde nicht erzeugt – Java-Ausgabe prüfen.</div>")
                    elif is_model_empty(model_name):
                        print("<div class='status-msg error'><strong>Fehler:</strong> Das Modell enthält nur Nullen – die Eingabe enthält wahrscheinlich keine Protein-Sequenzen (RNA/DNA?).</div>")
                    else:
                        print("<div class='status-msg success'><strong>Training erfolgreich!</strong> Das Modell wurde erstellt.</div>")

                        with open(model_name, "r") as f:
                            preview = "".join([f.readline() for _ in range(20)])
                        print("<div class='preview-title'>Modell-Vorschau (Header):</div>")
                        print(f"<div class='preview-box'>{html.escape(preview)}</div>")

                        with open(model_name, "rb") as f:
                            b64 = base64.b64encode(f.read()).decode()
                        print(f'<a href="data:text/plain;base64,{b64}" download="{html.escape(model_name)}" class="download-btn">&#11015; {html.escape(model_name)} herunterladen</a>')
                else:
                    stderr_clean = res.stderr.strip()
                    if "OutOfMemoryError" in stderr_clean:
                        msg = "Java Speicherfehler – Datei zu groß für das System."
                    elif "FileNotFoundException" in stderr_clean or "IOException" in stderr_clean:
                        msg = "Datei nicht lesbar – bitte Format prüfen."
                    elif "NumberFormatException" in stderr_clean:
                        msg = "Ungültiges Dateiformat – bitte eine gültige .seclib oder .db Datei verwenden."
                    else:
                        msg = f"<pre style='margin-top:8px;font-size:0.85em'>{html.escape(stderr_clean[:400])}</pre>"
                    print(f"<div class='status-msg error'><strong>Training fehlgeschlagen:</strong> {msg}</div>")
            else:
                print(f"<div class='status-msg error'><strong>Systemfehler:</strong> {html.escape(str(res))}</div>")

        for t in tmp_files:
            if os.path.exists(t):
                os.unlink(t)

    print("""
</div>
</main>

<footer>
    ProgPrakt WS 2025/2026 &middot; Gruppe 17 &nbsp;|&nbsp;
    <a href="../index.html">&larr; Zurück zur Hauptseite</a>
</footer>
</body>
</html>
    """)


if __name__ == "__main__":
    main()
