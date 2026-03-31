#!/usr/bin/python3

import subprocess
import html
import base64
import os
import cgi
import tempfile
import urllib.request
import re

CGI_DIR = os.path.dirname(os.path.abspath(__file__))
JAR_PATH           = os.path.join(CGI_DIR, "predict.jar")
VALIDATE_JAR_PATH  = os.path.join(CGI_DIR, "validateGor.jar")
MAKE_SECLIB_PATH   = os.path.join(CGI_DIR, "get_seclib.py")
DEFAULT_MODELS = {
    "gor1": os.path.join(CGI_DIR, "gor1default.txt"),
    "gor3": os.path.join(CGI_DIR, "gor3default.txt"),
    "gor4": os.path.join(CGI_DIR, "gor4default.txt"),
}
DEFAULT_SEQS = {
    "cb513": "/mnt/extstud/praktikum/bioprakt/Data/GOR/CB513/CB513.fasta",
}
DEFAULT_REFS = {
    "cb513": "/mnt/extstud/praktikum/bioprakt/Data/GOR/CB513/CB513DSSP.db",
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


def run_gor_predict(model_path, seq_path, fmt, probabilities, show_scores=False):
    cmd = [
        "java", "-cp", JAR_PATH, "de.lmu.ifi.bio.gor.cli.Predict",
        "--model", model_path,
        "--seq",   seq_path,
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


def fetch_fasta_from_pdb(pdb_id):
    pdb_id = pdb_id.strip()
    if not pdb_id or len(pdb_id) != 4 or not pdb_id.isalnum():
        return None, f"Ungültige PDB ID: '{pdb_id}'."
    tmp = tempfile.NamedTemporaryFile(suffix=".fasta", delete=False, mode='w')
    tmp.close()
    try:
        url = f"https://www.rcsb.org/fasta/entry/{pdb_id.upper()}/display"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode('utf-8')
            with open(tmp.name, 'w') as f:
                f.write(content)
        if os.path.getsize(tmp.name) < 10:
            return None, f"PDB ID '{pdb_id.upper()}' lieferte keine FASTA-Daten."
        return tmp.name, None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code} für PDB '{pdb_id.upper()}'."
    except Exception as e:
        return None, str(e)


def fetch_seclib_from_pdb(pdb_id):
    pdb_id = pdb_id.strip().upper()
    if not pdb_id or len(pdb_id) != 4 or not pdb_id.isalnum():
        return None, f"Ungültige PDB ID: '{pdb_id}'."

    try:
        url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            pdb_text = resp.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        return None, f"PDB '{pdb_id}' nicht gefunden (HTTP {e.code})."
    except Exception as e:
        return None, f"Fehler beim Laden von PDB '{pdb_id}': {e}"

    aa3to1 = {
        'ALA':'A','ARG':'R','ASN':'N','ASP':'D','CYS':'C','GLN':'Q','GLU':'E',
        'GLY':'G','HIS':'H','ILE':'I','LEU':'L','LYS':'K','MET':'M','PHE':'F',
        'PRO':'P','SER':'S','THR':'T','TRP':'W','TYR':'Y','VAL':'V',
        'MSE':'M','SEC':'C','PYL':'K','HSD':'H','HSE':'H','HSP':'H',
    }

    seqres = {}
    for line in pdb_text.splitlines():
        if line.startswith("SEQRES"):
            chain = line[11].strip()
            residues = line[19:].split()
            if chain not in seqres:
                seqres[chain] = []
            for r in residues:
                seqres[chain].append(aa3to1.get(r.upper(), 'X'))

    if not seqres:
        return None, f"PDB '{pdb_id}' enthält keine SEQRES-Einträge."

    residue_order = {}
    seen = {}
    for line in pdb_text.splitlines():
        if line.startswith("ATOM  ") or line.startswith("ATOM "):
            try:
                chain   = line[21]
                res_seq = int(line[22:26].strip())
                ins_code = line[26].strip()
                key = (chain, res_seq, ins_code)
                if chain not in residue_order:
                    residue_order[chain] = []
                    seen[chain] = set()
                if key not in seen[chain]:
                    seen[chain].add(key)
                    residue_order[chain].append(res_seq)
            except (ValueError, IndexError):
                continue

    helices = []
    for line in pdb_text.splitlines():
        if line.startswith("HELIX "):
            try:
                chain_h = line[19]
                start   = int(line[21:25].strip())
                end     = int(line[33:37].strip())
                helices.append((chain_h, start, end))
            except (ValueError, IndexError):
                continue

    sheets = []
    for line in pdb_text.splitlines():
        if line.startswith("SHEET "):
            try:
                chain_s = line[21]
                start   = int(line[22:26].strip())
                end     = int(line[33:37].strip())
                sheets.append((chain_s, start, end))
            except (ValueError, IndexError):
                continue

    def get_ss_for_residue(chain, res_num):
        for (c, s, e) in helices:
            if c == chain and s <= res_num <= e:
                return 'H'
        for (c, s, e) in sheets:
            if c == chain and s <= res_num <= e:
                return 'E'
        return 'C'

    seclib_lines = []
    for chain in sorted(seqres.keys()):
        seq = "".join(seqres[chain])
        if len(seq) < 5:
            continue
        res_nums = residue_order.get(chain, [])
        if res_nums and len(res_nums) == len(seq):
            ss = "".join(get_ss_for_residue(chain, rn) for rn in res_nums)
        elif res_nums:
            ss_atoms = "".join(get_ss_for_residue(chain, rn) for rn in res_nums)
            if len(ss_atoms) >= len(seq):
                ss = ss_atoms[:len(seq)]
            else:
                ss = ss_atoms + "C" * (len(seq) - len(ss_atoms))
        else:
            ss = "C" * len(seq)
        seclib_lines.append(f"> {pdb_id}_{chain}")
        seclib_lines.append(f"AS {seq}")
        seclib_lines.append(f"SS {ss}")
        seclib_lines.append("")

    if not seclib_lines:
        return None, f"Keine verwertbaren Chains in PDB '{pdb_id}' gefunden."

    return "\n".join(seclib_lines), None


def fetch_seclib_via_script(pdb_id):
    pdb_id = pdb_id.strip().upper()
    if not pdb_id or len(pdb_id) != 4 or not pdb_id.isalnum():
        return None, f"Ungültige PDB ID: '{pdb_id}'."

    if not os.path.exists(MAKE_SECLIB_PATH):
        return None, "get_seclib.py nicht gefunden – bitte in den CGI-Ordner hochladen."

    tmp_pdb = tempfile.NamedTemporaryFile(suffix=".pdb", delete=False, mode='wb')
    tmp_pdb.close()
    url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            if len(data) < 100:
                os.unlink(tmp_pdb.name)
                return None, f"PDB ID '{pdb_id}' lieferte keine Daten (existiert sie?)."
            with open(tmp_pdb.name, 'wb') as f:
                f.write(data)
    except urllib.error.HTTPError as e:
        os.unlink(tmp_pdb.name)
        return None, f"HTTP {e.code}: PDB '{pdb_id}' nicht gefunden."
    except Exception as e:
        os.unlink(tmp_pdb.name)
        return None, f"PDB-Download fehlgeschlagen: {e}"

    tmp_seclib = tempfile.NamedTemporaryFile(suffix=".seclib", delete=False, mode='w')
    tmp_seclib.close()
    cmd = ["python3", MAKE_SECLIB_PATH, "--PDB", tmp_pdb.name, "--output", tmp_seclib.name]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=60)
    except Exception as e:
        os.unlink(tmp_pdb.name)
        return None, f"make_seclib.py Fehler: {e}"
    finally:
        if os.path.exists(tmp_pdb.name):
            os.unlink(tmp_pdb.name)

    if result.returncode != 0:
        return None, f"make_seclib.py Fehler: {result.stderr[:300]}"
    if not os.path.exists(tmp_seclib.name) or os.path.getsize(tmp_seclib.name) == 0:
        return None, f"make_seclib.py hat keine Einträge erzeugt für '{pdb_id}'. Enthält die PDB-Datei ATOM-Einträge?"

    with open(tmp_seclib.name, 'r') as f:
        content = f.read()
    return tmp_seclib.name, content


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


def parse_seclib(text):
    entries = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith(">"):
            entry_id = line[1:].strip().split()[0]
            seq = ""
            ss  = ""
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(">"):
                l = lines[i].strip()
                if l.startswith("AS "):
                    seq = l[3:].strip()
                elif l.startswith("SS ") or l.startswith("PS "):
                    ss = l[3:].strip()
                i += 1
            if seq or ss:
                entries.append((entry_id, seq, ss))
        else:
            i += 1
    return entries


def parse_prediction_output(text):
    entries = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith(">"):
            entry_id = line[1:].strip().split()[0]
            seq = ""
            ps  = ""
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(">"):
                l = lines[i].strip()
                if l.startswith("AS "):
                    seq = l[3:].strip()
                elif l.startswith("PS "):
                    ps = l[3:].strip().replace("-", "C")
                i += 1
            if seq or ps:
                entries.append((entry_id, seq, ps))
        else:
            i += 1
    return entries


def validate_ref_vs_pred(ref_entries, pred_entries):
    warnings = []
    matched  = []

    if not ref_entries:
        return False, ["Referenzdatei enthält keine gültigen Einträge (Format: > ID, AS ..., SS ...)."], []

    if not pred_entries:
        return False, ["Vorhersage enthält keine gültigen Einträge."], []

    ref_by_id = {e[0].lower(): e for e in ref_entries}

    unmatched_pred = []
    for pid, pseq, pss in pred_entries:
        pid_short = pid.lower().split("|")[0].split("_")[0]
        pid_pdb = pid.lower().split("|")[0].split("_")[0]  # nur "1tim"
        ref = ref_by_id.get(pid.lower())
        if ref is None:
            for rid in ref_by_id:
                if rid.split("_")[0] == pid_pdb:  # "1tim_a" → "1tim" == "1tim"
                    ref = ref_by_id[rid]
                    break

        if ref is None:
            unmatched_pred.append(pid)
        else:
            rid, rseq, rss = ref
            pred_len = len(pss.replace("-",""))
            ref_len  = len(rss.replace("-",""))
            if pred_len != ref_len:
                warnings.append(
                    f"Sequenz <strong>{html.escape(pid)}</strong>: "
                    f"Vorhersage hat {pred_len} Zeichen, Referenz hat {ref_len} Zeichen – "
                    f"Validierung für diese Sequenz wird übersprungen."
                )
            else:
                matched.append((pid, rid))

    if unmatched_pred:
        id_list = ", ".join(html.escape(x) for x in unmatched_pred[:5])
        if len(unmatched_pred) > 5:
            id_list += f" … (+{len(unmatched_pred)-5} weitere)"
        warnings.append(
            f"Folgende Sequenzen aus der Vorhersage wurden in der Referenz <strong>nicht gefunden</strong>: {id_list}. "
            f"Bitte sicherstellen, dass die IDs übereinstimmen."
        )

    valid_ss_chars = set("HEChec-")
    for rid, rseq, rss in ref_entries:
        invalid = set(rss) - valid_ss_chars
        if invalid:
            warnings.append(
                f"Referenz <strong>{html.escape(rid)}</strong>: "
                f"Ungültige Zeichen in SS-Zeile: {', '.join(html.escape(c) for c in invalid)}. "
                f"Erlaubt: H, E, C."
            )

    if not matched and not warnings:
        warnings.append("Keine passenden Sequenzen zwischen Vorhersage und Referenz gefunden.")

    ok = len(matched) > 0
    return ok, warnings, matched


def render_prob_line(line):
    prefix = line[:3]
    values = line[3:].split()
    color_map = {"PH ": "#e63946", "PE ": "#f4a261", "PC ": "#457b9d"}
    label_map = {"PH ": "PH", "PE ": "PE", "PC ": "PC"}
    color = color_map.get(prefix, "#888")
    label = label_map.get(prefix, prefix.strip())
    formatted = " ".join(values)
    return (
        f'<span class="seq-line prob-line" style="color:{color}">'
        f'<span class="prob-label">{html.escape(label)}</span> '
        f'{html.escape(formatted)}</span>'
    )


HTML_HEAD = """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GOR Sekundärstruktur-Vorhersage</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <script src="https://chemapps.stolaf.edu/jmol/jsmol/JSmol.min.js"></script>
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
            color: var(--text); line-height: 1.6; min-height: 100vh;
        }
        body::before {
            content: ""; position: fixed; inset: 0;
            background: linear-gradient(180deg, rgba(13,107,92,0.06) 0%, transparent 40%);
            pointer-events: none; z-index: 0;
        }
        .header {
            position: relative; background: transparent;
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
        .tab-buttons { display:flex; gap:8px; margin-bottom:18px; flex-wrap:wrap; }
        .tab-btn {
            flex:1; padding:9px 12px; border:2px solid var(--border); border-radius:10px;
            background:white; cursor:pointer; font-weight:600; font-size:0.88em;
            color:var(--bio-green); font-family:"DM Sans",sans-serif; transition:all 0.2s;
            min-width:100px;
        }
        .tab-btn:hover  { border-color:var(--bio-teal); background:var(--bio-green-pale); }
        .tab-btn.active { border-color:var(--bio-green); background:var(--bio-green); color:white; }
        .tab-content { display:none; } .tab-content.active { display:block; }
        label { display:block; font-weight:600; font-size:0.9em; color:var(--text); margin-bottom:7px; }
        select, input[type="text"] {
            width:100%; padding:10px 13px; border:1.5px solid var(--border); border-radius:10px;
            font-size:0.93em; font-family:"DM Sans",sans-serif; color:var(--text);
            background:var(--bio-green-pale); outline:none; transition:border-color 0.2s;
        }
        select:focus, input[type="text"]:focus { border-color:var(--bio-teal); background:white; }
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
        .warning { background:#fffbec; color:#7a5500; border-color:#e0a800; }
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
        .seq-block .seq-header { font-weight:700; color:var(--bio-green); font-size:0.95em; display:block; margin-bottom:6px; }
        .seq-block .seq-line { display:block; white-space:pre; }
        .seq-block .cartoon-line { display:block; white-space:pre; letter-spacing:0; color:#2a9d8f; font-size:1em; margin-top:0; }
        .prob-line { font-size:1em;}
        .prob-label { font-weight:normal; display:inline-block; width:2ch; }
        .prob-section-divider { display:block; border:none; border-top:1px dashed var(--border); margin:6px 0 4px; }
        .score-table { width:100%; border-collapse:collapse; margin-top:14px; font-family:"JetBrains Mono",monospace; font-size:0.9em; }
        .score-table th { background:var(--bio-green); color:white; padding:10px 16px; text-align:left; font-size:0.82em; letter-spacing:0.05em; }
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
        .jmol-wrap { background:#fff; border:1.5px solid var(--border); border-radius:14px;
                     padding:20px; margin-top:14px; box-shadow:0 2px 12px rgba(13,107,92,0.08); }
        .jmol-wrap h4 { font-size:0.82em; font-weight:700; text-transform:uppercase; letter-spacing:0.07em; color:var(--bio-green); margin-bottom:12px; }
        .jmol-legend { display:flex; gap:14px; flex-wrap:wrap; margin-top:12px; font-size:0.82em; color:var(--text-muted); }
        .jmol-legend span { display:flex; align-items:center; gap:6px; }
        .leg-dot { width:11px; height:11px; border-radius:50%; display:inline-block; }
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
            box-shadow:0 6px 28px rgba(0,0,0,0.45); line-height:1.9; pointer-events:none; width:300px;
        }
        .info-icon .tooltip::before {
            content:""; position:absolute; right:100%; top:50%; transform:translateY(-50%);
            border:7px solid transparent; border-right-color:#1a2e2a;
        }
        .info-icon:hover .tooltip, .info-icon:focus .tooltip { display:block; }
        .char-H { color: #ba55d3; font-weight: bold; }
        .char-E { color: #1e90ff; font-weight: bold; }
        .char-C { color: #2e8b57; font-weight: bold; }
        .prob-filter {
            display:flex; gap:16px; align-items:center; flex-wrap:wrap;
            background:var(--bio-green-pale); border:1px solid var(--border);
            border-radius:10px; padding:10px 16px; margin:10px 0 14px; font-size:0.88em;
        }
        .prob-filter strong { color:var(--bio-green); margin-right:4px; }
        .prob-filter label { margin:0; font-weight:500; font-size:0.93em; cursor:pointer; display:flex; align-items:center; gap:6px; }
        .prob-filter input[type=checkbox] { width:15px; height:15px; accent-color:var(--bio-green); cursor:pointer; }
        .ph-color { color:#e63946; font-weight:700; }
        .pe-color { color:#f4a261; font-weight:700; }
        .pc-color { color:#457b9d; font-weight:700; }
        .ref-check-badge { display:inline-block; padding:3px 10px; border-radius:20px; font-size:0.8em; font-weight:700; margin-left:8px; vertical-align:middle; }
        .ref-check-ok   { background:#d4ede8; color:#0d6b5c; }
        .ref-check-warn { background:#fff3cd; color:#856404; }
        .ref-check-fail { background:#fdf0ef; color:#8b2a22; }
        .validation-warnings { margin:10px 0; }
        .validation-warnings li { margin-bottom:6px; }
    </style>
    <script>
        function switchTab(tabId) {
            document.querySelectorAll('.seq-tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.seq-tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById('tab-' + tabId).classList.add('active');
            document.getElementById('content-' + tabId).classList.add('active');
            document.getElementById('seq_mode').value = tabId;
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
        function updatePostprocHint() {
            var probCb  = document.getElementById('probabilities');
            var ppCb    = document.getElementById('no_postprocessing');
            var hint    = document.getElementById('postproc-hint');
            if (probCb && probCb.checked) {
                if (ppCb)   ppCb.checked  = true;
                if (ppCb)   ppCb.disabled = true;
                if (hint)   hint.style.display = 'block';
            } else {
                if (ppCb)   ppCb.disabled = false;
                if (hint)   hint.style.display = 'none';
            }
        }
        function toggleProb(type) {
            var show = document.getElementById('show-p' + type).checked;
            document.querySelectorAll('.prob-row-' + type).forEach(function(el) {
                el.style.display = show ? 'block' : 'none';
            });
        }
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
        <h1>GOR Sekundärstruktur-Vorhersage</h1>
        <p>WS 2025/2026 <span>&middot;</span> Gruppe 17</p>
        <div class="hero-dots"><span></span><span></span><span></span></div>
    </div>
</header>
<main class="main">
<div class="main-panel">
"""

HTML_FORM = """
<form method="post" enctype="multipart/form-data">
    <input type="hidden" name="seq_mode" id="seq_mode" value="text">
    <input type="hidden" name="ref_mode" id="ref_mode" value="none">

    <!-- 1. Sequenz -->
    <div class="card">
        <div class="card-title">1. Sequenz eingeben</div>
        <div class="tab-buttons">
            <button type="button" class="seq-tab-btn tab-btn active" id="tab-text"
                    onclick="switchTab('text')">Sequenz eingeben</button>
            <button type="button" class="seq-tab-btn tab-btn" id="tab-default"
                    onclick="switchTab('default')">Standard-Fasta</button>
            <button type="button" class="seq-tab-btn tab-btn" id="tab-pdbid"
                    onclick="switchTab('pdbid')">PDB ID</button>
            <button type="button" class="seq-tab-btn tab-btn" id="tab-upload"
                    onclick="switchTab('upload')">FASTA hochladen</button>
        </div>
        <div class="seq-tab-content tab-content active" id="content-text">
            <label style="display:flex;align-items:center;gap:7px;">
                Aminosäuresequenz
                <span class="info-icon" tabindex="0">&#9432;
                    <span class="tooltip">
                        <strong>Format 1 – mit Header:</strong><br>
                        &gt;ProteinName<br>ACDEFGHIKLM...<br><br>
                        <strong>Format 2 – ohne Header:</strong><br>
                        ACDEFGHIKLM...<br><br>
                        <strong>Mehrere Sequenzen:</strong><br>
                        Mit Headern oder durch Zeilenumbrüche trennen.
                    </span>
                </span>
            </label>
            <textarea name="seq_text" rows="5" placeholder=">MeinProtein&#10;ACDEFGHIKLMNPQRSTVWY...&#10;&#10;oder einfach Sequenz ohne Header"></textarea>
        </div>
        <div class="seq-tab-content tab-content" id="content-default">
            <label>Standard-Sequenzdatenbank wählen</label>
            <select name="seq_default_db">
                <option value="cb513">CB513 (513 Proteine, Benchmark-FASTA)</option>
            </select>
            <small>Offizielle CB513-FASTA-Datenbank – alle 513 Benchmark-Sequenzen werden vorhergesagt.</small>
        </div>
        <div class="seq-tab-content tab-content" id="content-pdbid">
            <label>PDB IDs (kommagetrennt)</label>
            <input type="text" name="pdb_id" placeholder="z.B. 1TIM, 2HHB, 1CRN...">
            <small>Mehrere 4-stellige PDB IDs kommagetrennt – Sequenzen werden automatisch von rcsb.org geladen.</small>
        </div>
        <div class="seq-tab-content tab-content" id="content-upload">
            <label>FASTA-Datei hochladen</label>
            <input type="file" name="seq_file" accept=".fasta,.fa,.txt">
            <small>Erlaubte Formate: .fasta, .fa</small>
        </div>
    </div>

    <!-- 2. Modell -->
    <div class="card">
        <div class="card-title">2. Modell wählen</div>
        <input type="hidden" name="model_choice" id="model_choice" value="gor4">
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
            <small style="margin-top:0">GOR I – auf CB513 trainiert (Einzelresidue-Statistik).</small>
        </div>
        <div class="model-tab-content tab-content" id="model-content-gor3">
            <small style="margin-top:0">GOR III – auf CB513 trainiert (Paarkorrelationen).</small>
        </div>
        <div class="model-tab-content tab-content active" id="model-content-gor4">
            <small style="margin-top:0">GOR IV – auf CB513 trainiert (Direktionale Information, empfohlen).</small>
        </div>
        <div class="model-tab-content tab-content" id="model-content-upload">
            <label>Trainiertes GOR-Modell hochladen</label>
            <input type="file" name="model_file" accept=".txt,.model">
            <small>Modell-Datei aus dem Training-Tool (GOR I, III oder IV)</small>
        </div>
    </div>

    <!-- 3. Referenzstruktur (optional) -->
    <div class="card">
        <div class="card-title">
            3. Referenzstruktur (optional) &ndash; für Q3 &amp; SOV Scores
            <span class="info-icon" tabindex="0" style="margin-left:6px;">&#9432;
                <span class="tooltip">
                    <strong>Erlaubte Formate:</strong><br>
                    <strong>.seclib / .txt:</strong> Textformat mit &gt;ID, AS ..., SS ...<br>
                    <strong>.db:</strong> Datenbankformat (gleiche Struktur wie .seclib)<br><br>
                    Die IDs müssen mit den Vorhersage-IDs übereinstimmen.<br>
                    Die SS-Zeile darf nur H, E, C enthalten.<br><br>
                    Das Tool prüft automatisch ob Referenz und Vorhersage zueinander passen.
                </span>
            </span>
        </div>
        <div class="tab-buttons">
            <button type="button" class="ref-tab-btn tab-btn active" id="ref-tab-none"
                    onclick="switchRefTab('none')">Keine</button>
            <button type="button" class="ref-tab-btn tab-btn" id="ref-tab-default"
                    onclick="switchRefTab('default')">Standard-DB</button>
            <button type="button" class="ref-tab-btn tab-btn" id="ref-tab-upload"
                    onclick="switchRefTab('upload')">Datei hochladen</button>
            <button type="button" class="ref-tab-btn tab-btn" id="ref-tab-text"
                    onclick="switchRefTab('text')">Text einfügen</button>
        </div>
        <div class="ref-tab-content tab-content active" id="ref-content-none">
            <small style="margin-top:0">Kein Vergleich – nur Vorhersage anzeigen.</small>
        </div>
        <div class="ref-tab-content tab-content" id="ref-content-default">
            <label>Standard-Referenzdatenbank wählen</label>
            <select name="ref_default_db">
                <option value="cb513">CB513 (513 Proteine, Benchmark)</option>
            </select>
            <small>Offizielle CB513-Datenbank als Referenz für die Validierung.</small>
        </div>
        <div class="ref-tab-content tab-content" id="ref-content-pdbid">
            <label style="display:flex;align-items:center;gap:7px;">
                PDB ID als Referenz
                <span class="info-icon" tabindex="0">&#9432;
                    <span class="tooltip">
                        Die PDB-Datei wird automatisch von rcsb.org geladen und mit
                        <strong>get_seclib.py</strong> in eine Referenzstruktur umgewandelt.<br><br>
                        Voraussetzung: <strong>get_seclib.py</strong> muss im CGI-Ordner liegen.<br><br>
                        Die Sekundärstruktur wird aus den HELIX/SHEET-Einträgen der PDB-Datei extrahiert.
                    </span>
                </span>
            </label>
            <input type="text" name="ref_pdb_id" placeholder="z.B. 1TIM, 2HHB...">
            <small>Mehrere PDB IDs kommagetrennt – Strukturen werden automatisch heruntergeladen und verglichen.</small>
        </div>
        <div class="ref-tab-content tab-content" id="ref-content-upload">
            <label style="display:flex;align-items:center;gap:7px;">
                Referenz-Datei hochladen
                <span class="info-icon" tabindex="0">&#9432;
                    <span class="tooltip">
                        <strong>Unterstützte Formate:</strong><br>
                        <strong>.seclib</strong> – Standard-Format<br>
                        <strong>.db</strong> – Datenbankdatei (gleiches Format)<br>
                        <strong>.txt</strong> – Textdatei mit gleichem Inhalt<br><br>
                        Jeder Eintrag braucht:<br>
                        &gt; ProteinID<br>
                        AS ACDEF...<br>
                        SS HHHCC...
                    </span>
                </span>
            </label>
            <input type="file" name="ref_file" accept=".seclib,.db,.txt">
            <small>Erlaubte Formate: .seclib, .db, .txt</small>
        </div>
        <div class="ref-tab-content tab-content" id="ref-content-text">
            <label>Referenz einfügen</label>
            <textarea name="ref_text" rows="5" placeholder="&gt; ProteinID&#10;AS ACDEFG...&#10;SS HHHCCC..."></textarea>
            <small>Format: &gt;ID, dann AS (Sequenz), dann SS (Struktur: H/E/C)</small>
        </div>
    </div>

    <!-- 4. Optionen -->
    <div class="card">
        <div class="card-title">4. Optionen</div>
        <div class="checkbox-row" style="margin-bottom:12px">
            <input type="checkbox" name="probabilities" id="probabilities" value="1">
            <label for="probabilities">Benutze die Wahrscheinlichkeitsformel</label>
        </div>
        <div class="checkbox-row" style="margin-bottom:12px">
            <input type="checkbox" name="show_scores" id="show_scores" value="1">
            <label for="show_scores">Scores ausgeben (IH/IE/IC bzw. PH/PE/PC)
                <small style="display:inline;font-size:0.82em;color:var(--text-muted);font-weight:400;">
                    – Post-Processing wird deaktiviert
                </small>
            </label>
        </div>
        <div class="checkbox-row" style="margin-bottom:4px">
            <input type="checkbox" name="show_jmol" id="show_jmol" value="1">
            <label for="show_jmol">3D-Struktur mit JSmol anzeigen (nur bei PDB ID)</label>
        </div>
    </div>

    <button type="submit" name="predict_action" class="submit-btn">Vorhersage starten</button>
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


def normalize_seq_input(text):
    lines = text.splitlines()
    blocks = []
    current_header = None
    current_seq = []
    auto_index = 1

    def flush():
        nonlocal current_header, current_seq, auto_index
        if current_seq:
            if current_header is None:
                current_header = f">Seq{auto_index}"
                auto_index += 1
            blocks.append((current_header, "".join(current_seq)))
            current_header = None
            current_seq = []

    for line in lines:
        line = line.strip()
        if not line:
            flush()
        elif line.startswith(">"):
            flush()
            current_header = line
        else:
            seq_clean = "".join(c for c in line if c.isalpha())
            if seq_clean:
                if current_header is None and current_seq:
                    flush()
                current_seq.append(seq_clean)
                if current_header is None:
                    flush()

    flush()
    return "\n\n".join(f"{h}\n{s}" for h, s in blocks) + "\n"


def main():
    fs = cgi.FieldStorage()
    print("Content-Type: text/html; charset=utf-8\n")
    print(HTML_HEAD)
    print(HTML_FORM)

    if "predict_action" not in fs:
        print(HTML_FOOTER)
        return

    seq_mode      = fs.getvalue("seq_mode")      or "text"
    ref_mode      = fs.getvalue("ref_mode")      or "none"
    probabilities = fs.getvalue("probabilities") == "1"
    show_scores   = fs.getvalue("show_scores")   == "1"
    show_jmol     = fs.getvalue("show_jmol")     == "1"

    tmp_seq = tmp_model = tmp_ref = None
    seq_path = model_path = ref_path = None
    pdb_id_used = None
    error_msg = None

    # ── Modell laden ──────────────────────────────────────────────────────────
    if "model_file" in fs and fs["model_file"].filename:
        tmp_m = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
        tmp_m.write(fs["model_file"].file.read())
        tmp_m.close()
        model_path = tmp_m.name
        tmp_model  = model_path
    else:
        model_choice = (fs.getvalue("model_choice") or "").strip()
        if model_choice in DEFAULT_MODELS:
            default_path = DEFAULT_MODELS[model_choice]
            if os.path.exists(default_path):
                model_path = default_path
            else:
                error_msg = f"Standard-Modell '{model_choice}' nicht gefunden ({default_path})."
        else:
            error_msg = "Bitte ein Modell hochladen oder ein Standard-Modell auswählen."

    # ── Sequenz laden ─────────────────────────────────────────────────────────
    if not error_msg:
        if seq_mode == "text":
            seq_text = (fs.getvalue("seq_text") or "").strip()
            if not seq_text:
                error_msg = "Bitte eine Sequenz eingeben."
            else:
                seq_text = normalize_seq_input(seq_text)
                tmp_s = tempfile.NamedTemporaryFile(suffix=".fasta", delete=False, mode='w')
                tmp_s.write(seq_text); tmp_s.close()
                seq_path = tmp_s.name; tmp_seq = seq_path

        elif seq_mode == "default":
            seq_default = (fs.getvalue("seq_default_db") or "").strip()
            if seq_default in DEFAULT_SEQS:
                default_seq_path = DEFAULT_SEQS[seq_default]
                if not os.path.exists(default_seq_path):
                    error_msg = f"Standard-Sequenz '{seq_default}' nicht gefunden ({default_seq_path})."
                else:
                    seq_path = default_seq_path
            else:
                error_msg = "Ungültige Standard-Sequenz ausgewählt."

        elif seq_mode == "pdbid":
            pdb_ids_raw = (fs.getvalue("pdb_id") or "").strip().upper()
            if not pdb_ids_raw:
                error_msg = "Bitte eine PDB ID eingeben."
            else:
                pdb_ids = [x.strip() for x in pdb_ids_raw.split(",") if x.strip()]
                pdb_id_used = pdb_ids[0]
                combined_fasta = ""
                for pid in pdb_ids:
                    print(f"<div class='status-msg info'>Lade PDB <strong>{pid}</strong> von rcsb.org…</div>")
                    tmp_f, err = fetch_fasta_from_pdb(pid)
                    if err:
                        error_msg = err
                        break
                    with open(tmp_f, 'r') as f:
                        combined_fasta += f.read() + "\n"
                    os.unlink(tmp_f)
                if not error_msg:
                    tmp_s = tempfile.NamedTemporaryFile(suffix=".fasta", delete=False, mode='w')
                    tmp_s.write(combined_fasta); tmp_s.close()
                    seq_path = tmp_s.name; tmp_seq = seq_path

        elif seq_mode == "upload":
            if "seq_file" in fs and fs["seq_file"].filename:
                allowed = {'.fasta', '.fa', '.txt'}
                suffix  = os.path.splitext(fs["seq_file"].filename)[1].lower()
                if suffix not in allowed:
                    error_msg = f"Ungültiges Format '{suffix}'. Erlaubt: .fasta, .fa"
                else:
                    tmp_s = tempfile.NamedTemporaryFile(suffix=".fasta", delete=False)
                    tmp_s.write(fs["seq_file"].file.read()); tmp_s.close()
                    seq_path = tmp_s.name; tmp_seq = seq_path
            else:
                error_msg = "Bitte eine FASTA-Datei hochladen."

    # ── Referenzstruktur laden ────────────────────────────────────────────────
    ref_text_raw = None

    if not error_msg and ref_mode != "none":
        if ref_mode == "default":
            ref_default = (fs.getvalue("ref_default_db") or "").strip()
            if ref_default in DEFAULT_REFS:
                ref_path = DEFAULT_REFS[ref_default]
                if not os.path.exists(ref_path):
                    error_msg = f"Standard-Referenz '{ref_default}' nicht gefunden ({ref_path})."
                else:
                    with open(ref_path, 'r', errors='replace') as f:
                        ref_text_raw = f.read()
                    tmp_ref = None
            else:
                error_msg = "Ungültige Standard-Referenz ausgewählt."


        elif ref_mode == "upload":
            if "ref_file" in fs and fs["ref_file"].filename:
                fname  = fs["ref_file"].filename
                suffix = os.path.splitext(fname)[1].lower()
                allowed_ref = {'.seclib', '.db', '.txt'}
                if suffix not in allowed_ref:
                    error_msg = (
                        f"Ungültiges Referenzformat '{html.escape(suffix)}'. "
                        f"Erlaubt: .seclib, .db, .txt"
                    )
                else:
                    raw_bytes = fs["ref_file"].file.read()
                    try:
                        ref_text_raw = raw_bytes.decode('utf-8')
                    except UnicodeDecodeError:
                        ref_text_raw = raw_bytes.decode('latin-1')
                    tmp_r = tempfile.NamedTemporaryFile(suffix=".seclib", delete=False, mode='w', encoding='utf-8')
                    tmp_r.write(ref_text_raw); tmp_r.close()
                    ref_path = tmp_r.name; tmp_ref = ref_path
            else:
                error_msg = "Bitte eine Referenz-Datei hochladen."

        elif ref_mode == "text":
            ref_text_raw = (fs.getvalue("ref_text") or "").strip()
            if not ref_text_raw:
                error_msg = "Bitte Referenz-Inhalt einfügen."
            else:
                tmp_r = tempfile.NamedTemporaryFile(suffix=".seclib", delete=False, mode='w')
                tmp_r.write(ref_text_raw); tmp_r.close()
                ref_path = tmp_r.name; tmp_ref = ref_path

    if error_msg:
        print(f"<div class='status-msg error'><strong>Fehler:</strong> {html.escape(error_msg)}</div>")
        for t in [tmp_seq, tmp_model, tmp_ref]:
            if t and os.path.exists(t): os.unlink(t)
        print(HTML_FOOTER)
        return

    res_txt = run_gor_predict(model_path, seq_path, "txt", probabilities, show_scores)

    if not isinstance(res_txt, subprocess.CompletedProcess):
        print(f"<div class='status-msg error'><strong>Systemfehler:</strong> {html.escape(str(res_txt))}</div>")
        for t in [tmp_seq, tmp_model, tmp_ref]:
            if t and os.path.exists(t): os.unlink(t)
        print(HTML_FOOTER)
        return

    if res_txt.returncode != 0 or not res_txt.stdout.strip():
        stderr = res_txt.stderr
        if "keinen gültigen FASTA-Header" in stderr or "startet nicht mit" in stderr:
            msg = "Ungültige Sequenz: FASTA-Format erwartet (&gt;ID, dann Sequenz)."
        elif "loadModel" in stderr or "NumberFormatException" in stderr or "NoSuchElementException" in stderr:
            msg = "Ungültiges Modell: Die Datei ist kein gültiges GOR-Modell."
        elif "IOException" in stderr:
            msg = "Fehler beim Lesen der Eingabedatei – bitte Dateiformat prüfen."
        elif not res_txt.stdout.strip() and res_txt.returncode == 0:
            msg = "Keine Ausgabe – die Sequenz muss mindestens 17 Aminosäuren lang sein."
        else:
            msg = f"Fehler bei der Vorhersage.<br><small style='font-family:monospace'>{html.escape(stderr[:300])}</small>"
        print(f"<div class='status-msg error'><strong>Fehler:</strong> {msg}</div>")
        for t in [tmp_seq, tmp_model, tmp_ref]:
            if t and os.path.exists(t): os.unlink(t)
        print(HTML_FOOTER)
        return

    print("<div class='status-msg success'><strong>Vorhersage erfolgreich!</strong></div>")

    # ── Referenzstruktur-Kompatibilitätsprüfung ───────────────────────────────
    ref_ok = False
    ref_warnings = []
    ref_matched  = []

    if ref_path and ref_text_raw:
        ref_entries  = parse_seclib(ref_text_raw)
        pred_entries = parse_prediction_output(res_txt.stdout)
        ref_ok, ref_warnings, ref_matched = validate_ref_vs_pred(ref_entries, pred_entries)

        if ref_ok:
            badge = f'<span class="ref-check-badge ref-check-ok">✓ {len(ref_matched)} Sequenz(en) kompatibel</span>'
            print(f"<div class='status-msg success'><strong>Referenzstruktur geprüft</strong> {badge}<br>"
                  f"Die Referenz passt zur Vorhersage und kann für die Validierung verwendet werden.</div>")
        else:
            badge = '<span class="ref-check-badge ref-check-fail">✗ Nicht kompatibel</span>'
            print(f"<div class='status-msg warning'><strong>Referenzstruktur-Problem</strong> {badge}</div>")

        if ref_warnings:
            print("<div class='status-msg warning'><strong>Hinweise zur Referenz:</strong><ul class='validation-warnings'>")
            for w in ref_warnings:
                print(f"<li>{w}</li>")
            print("</ul></div>")

        if not ref_ok:
            print("<div class='status-msg info'>Die Validierung wird übersprungen, da Referenz und Vorhersage nicht kompatibel sind. "
                  "Bitte IDs und Sequenzlängen prüfen.</div>")

    # ── Ergebnisse rendern ────────────────────────────────────────────────────
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

    total    = len(blocks)
    per_page = 5
    num_pages = max(1, (total + per_page - 1) // per_page)

    print("<div class='result-title'>Vorhersage:</div>")

    if num_pages > 1:
        print("<div class='pagination'>")
        print("<button class='page-btn' id='btn-prev' onclick='prevPage()' disabled>&#9664; Zurück</button>")
        print(f"<span class='page-info' id='page-info'>Seite 1 von {num_pages} ({total} Sequenzen)</span>")
        next_disabled = " disabled" if num_pages == 1 else ""
        print(f"<button class='page-btn' id='btn-next' onclick='nextPage()'{next_disabled}>Weiter &#9654;</button>")
        print("</div>")

    for i, block in enumerate(blocks):
        display = "block" if i < per_page else "none"
        header  = block[0]

        print(f"<div class='seq-block' style='display:{display}'>")
        print(f"<span class='seq-header'>{html.escape(header)}</span>")

        score_lines = {}
        current_ps_seq = ""

        def flush_score_lines():
            if not score_lines:
                return
            rows = {lbl: raw for lbl, raw in score_lines.items()}

            for lbl, raw in rows.items():
                target_char = lbl[-1]
                out = f'<span class="seq-line prob-line prob-row-{target_char}">'
                out += f'<span class="prob-label">{html.escape(lbl)}</span> '
                for pos, ch in enumerate(raw):
                    is_predicted = (pos < len(current_ps_seq) and current_ps_seq[pos] == target_char)
                    if ch.isdigit() and is_predicted:
                        out += f'<span style="color:#c0392b; font-weight:bold;">{ch}</span>'
                    else:
                        out += html.escape(ch)
                out += '</span>'
                print(out)

            print(render_score_plot(score_lines))
            score_lines.clear()

        has_prob_above = False
        for line in block[1:]:
            if line.startswith("PS "):
                current_ps_seq = line[3:]

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
                    seq_part = line[3:]
                    colored_ps = "PS "
                    for char in seq_part:
                        up_char = char.upper()
                        cls = f"char-{up_char}" if up_char in "HEC" else ""
                        if cls:
                            colored_ps += f'<span class="{cls}">{html.escape(char)}</span>'
                        else:
                            colored_ps += html.escape(char)
                    print(f"<span class='seq-line'>{colored_ps}</span>")
                    cartoon_html = get_cartoon_aligned(line)
                    print(f"<span class='cartoon-line'>{cartoon_html}</span>")
                else:
                    print(f"<span class='seq-line'>{html.escape(line)}</span>")

        flush_score_lines()
        print("</div>")

    b64 = base64.b64encode(res_txt.stdout.encode()).decode()
    print(f'<a href="data:text/plain;base64,{b64}" download="prediction.txt" class="download-btn">&#11015; prediction.txt herunterladen</a>')

    # ── Validierung (nur wenn Referenz kompatibel) ────────────────────────────
    if ref_path and ref_ok:
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
            err_detail = ""
            if isinstance(val_res, subprocess.CompletedProcess) and val_res.stderr:
                err_detail = f"<br><small style='font-family:monospace'>{html.escape(val_res.stderr[:200])}</small>"
            print(f"<div class='status-msg warning'>Validierung nicht möglich – trotz kompatibler Referenz. Bitte Formate prüfen.{err_detail}</div>")

        for t in [tmp_prd.name, tmp_sum.name, tmp_det.name]:
            if os.path.exists(t): os.unlink(t)

    elif ref_path and not ref_ok:
        pass

    if show_jmol and pdb_id_used:
        print("<div class='result-title'>3D-Struktur (JSmol):</div>")
        jmol_script = (
            f"load ={pdb_id_used}; background white; "
            "display protein; "
            "cartoon on; "
            "select helix;  cartoon 1.5; color [xba55d3]; "
            "select sheet;  cartoon 1.5; color [x1e90ff]; "
            "select not (helix, sheet) and protein; "
            "cartoon 0.3; color [x2e8b57]; "
            "set cartoonFancy True; "
            "spin off; zoom 80;"
        )

        pdb_escaped = html.escape(pdb_id_used)
        print(f"""<div class="jmol-wrap">
              <h4>Sekundärstruktur &ndash; {pdb_escaped}</h4>
              <div id="jmol_div"></div>
              <button onclick="saveJmolPng()" style="
                  margin-top:12px; padding:10px 20px;
                  background:linear-gradient(135deg, var(--bio-dark), var(--bio-green));
                  color:white; border:none; border-radius:10px; font-size:0.9em;
                  font-weight:700; font-family:'DM Sans',sans-serif; cursor:pointer;
                  transition:opacity 0.2s;" onmouseover="this.style.opacity=0.85"
                  onmouseout="this.style.opacity=1">
                &#11015; 3D-Struktur als PNG speichern
              </button>
              <div class="jmol-legend">
                <span><span class="leg-dot" style="background:#ba55d3"></span> Helix</span>
                <span><span class="leg-dot" style="background:#1e90ff"></span> Sheet</span>
                <span><span class="leg-dot" style="background:#2e8b57"></span> Coil/Loop</span>
              </div>
            </div>
            <script>
              var jmolInfo = {{
                width: 500, height: 440,
                use: "HTML5",
                color: "#f8fcfb",
                j2sPath: "https://chemapps.stolaf.edu/jmol/jsmol/j2s",
                script: "{jmol_script}"
              }};
              var myJmol = Jmol.getApplet("myJmol", jmolInfo);
              document.getElementById("jmol_div").innerHTML = Jmol.getAppletHtml(myJmol);

              function saveJmolPng() {{
                Jmol.script(myJmol, "write IMAGE 500 440 PNG '{pdb_escaped}_structure.png'");
              }}
            </script>""")

    for t in [tmp_seq, tmp_model, tmp_ref]:
        if t and os.path.exists(t): os.unlink(t)

    print(HTML_FOOTER)


if __name__ == "__main__":
    main()
