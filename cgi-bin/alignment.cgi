#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CGI: Alignment (Gotoh / NW). Erwartet POST mit pairs_file, seqlib_file, optional matrix_file,
mode, algorithm, gap_open, gap_extend, format.
JARs: im Ordner über cgi-bin (z.B. public_html/alignment.jar).
"""
import os
import sys
import io
import cgi
import cgitb

# Damit Umlaute (ä, ü, ö) auf dem Server korrekt ankommen
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import subprocess
import tempfile
import shutil
import re
import itertools
import base64
import json

cgitb.enable()

# BASE_DIR = Ordner, in dem alignment.jar liegt (eine Ebene über cgi-bin)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
ALIGNMENT_JAR = os.path.join(BASE_DIR, "alignment.jar")
try:
    from result_layout import print_result_start, print_result_end, extract_jar_body, RESULT_CSS
except ImportError:
    def print_result_start(title, back_url, back_label):
        print("<!DOCTYPE html><html><head><meta charset='utf-8'><title>" + str(title) + "</title></head><body>")
        print("<p><a href='" + str(back_url) + "'>&#8592; " + str(back_label) + "</a></p>")
    def print_result_end():
        print("</body></html>")
    def extract_jar_body(html_out):
        s = html_out or ""
        start = s.find("<body>")
        if start >= 0: start = start + 6
        else: start = 0
        end = s.find("</body>")
        if end < 0: end = len(s)
        return s[start:end].strip()
    RESULT_CSS = ""
VALIDATE_JAR = os.path.join(BASE_DIR, "validateAli.jar")
DEFAULT_MATRIX = os.path.join(BASE_DIR, "dayhoff.mat")

def _parse_first_pdb_pair(pairs_data):
    """Erstes Paar aus Pairs-Datei lesen; wenn beide wie PDB-IDs (4 Zeichen), zurueckgeben."""
    if not pairs_data:
        return None, None
    raw = pairs_data.decode("utf-8", errors="replace") if isinstance(pairs_data, bytes) else str(pairs_data)
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            a, b = parts[0].strip()[:4], parts[1].strip()[:4]
            if len(a) == 4 and len(b) == 4 and a.isalnum() and b.isalnum():
                return a.upper(), b.upper()
        break
    return None, None


def jsmol_ss_html(use_ss, pdb_id1=None, pdb_id2=None):
    """3D-Ansicht mit Sekundaerstruktur-Faerbung (Helix rot, Strang gelb, Coil grau), wenn use_ss und zwei PDB-IDs."""
    if not use_ss or not pdb_id1 or not pdb_id2 or len(pdb_id1) != 4 or len(pdb_id2) != 4:
        return ""
    url1 = "https://files.rcsb.org/download/" + pdb_id1 + ".pdb"
    url2 = "https://files.rcsb.org/download/" + pdb_id2 + ".pdb"
    return (
        "<div class='jsmol-toggle-section' style='margin-top:1.5rem;padding-top:1rem;border-top:2px solid var(--accent-light);'>"
        "<div class='jsmol-ss-section' style='padding:1rem 1.25rem;background:linear-gradient(180deg,#edf5f4 0%,#e0f0ee 100%);border:1px solid var(--border);border-radius:12px;margin-bottom:1rem;'>"
        "<h3 style='font-size:1.05rem;color:var(--accent);margin:0 0 0.5rem;'>3D-Ansicht: " + cgi.escape(pdb_id1) + " und " + cgi.escape(pdb_id2) + "</h3>"
        "<p class='jsmol-lead' style='font-size:0.9rem;margin:0 0 0.5rem;'><strong>Was dargestellt wird:</strong> Die beiden Proteine werden aus der PDB geladen und <em>gemeinsam in einer 3D-Szene</em> angezeigt. Sie befinden sich im gleichen Koordinatensystem; ihre urspr&uuml;nglichen PDB-Koordinaten bleiben unver&auml;ndert, daher k&ouml;nnen sich die Strukturen r&aumlich &uuml;berlappen oder getrennt stehen. Die Darstellung ist als <em>Cartoon (Ribbon)</em>: die Peptidr&uuml;ckgrat-Bahnen sind als B&auml;nder gezeichnet, sodass Helices und Strang-Faltbl&auml;tter gut erkennbar sind.</p>"
        "<p class='jsmol-lead' style='font-size:0.9rem;margin:0 0 0.5rem;'><strong>Sekund&auml;rstruktur-Vergleich:</strong> Beide Proteine (<strong>" + cgi.escape(pdb_id1) + "</strong> links, <strong>" + cgi.escape(pdb_id2) + "</strong> rechts) werden nebeneinander angezeigt und einheitlich nach Sekund&auml;rstruktur gef&auml;rbt: <span style='color:#c0392b;font-weight:bold;'>Rot</span> = &alpha;-Helix, <span style='color:#d4ac0d;font-weight:bold;'>Gelb</span> = &beta;-Strang, <span style='color:#7f8c8d;font-weight:bold;'>Grau</span> = Coil. So k&ouml;nnen Sie auf einen Blick vergleichen, wo Helices, Strang und Coils in den beiden Strukturen liegen.</p>"
        "<p class='jsmol-lead' style='font-size:0.9rem;margin:0 0 0.5rem;'><strong>Bedienung:</strong> Maus: drehen (ziehen), zoomen (Rad). Erscheinen anfangs nur Punkte, bitte kurz warten oder drehen.</p>"
        "<p class='jsmol-lead' style='font-size:0.85rem;margin:0 0 0.75rem;color:var(--text-muted);'>Die Ansicht erscheint hier unten. &Ouml;ffnet sich ein neues Fenster (z.&nbsp;B. durch Browser-Einstellungen), k&ouml;nnen Sie die Struktur dort betrachten.</p>"
        "<button type='button' class='jsmol-toggle-btn' onclick=\"this.closest('.jsmol-toggle-section').classList.toggle('expanded'); initJsmolAlignSS(); return false;\" aria-expanded='false'>"
        "<span class='arrow'>&#9654;</span> 3D-Struktur hier laden (JSmol)"
        "</button>"
        "</div>"
        "<div class='jsmol-toggle-content' style='margin-top:0.5rem;'>"
        "<div id='jsmol_align_ss_container' class='jsmol-embed-small' style='width:280px;max-width:100%;height:260px;background:#1a1d23;border-radius:10px;overflow:hidden;border:2px solid var(--border);'></div>"
        "</div></div>"
        "<script>(function(){"
        "var jsmolAlignDone=false;"
        "window.initJsmolAlignSS=function(){"
        "var c=document.getElementById('jsmol_align_ss_container');"
        "if(!c||jsmolAlignDone)return;"
        "var url1=" + json.dumps(url1) + ",url2=" + json.dumps(url2) + ";"
        "function init(){"
        "if(typeof Jmol==='undefined')return;"
        "jsmolAlignDone=true;"
        "var script='load '+url1+'; load append '+url2+'; frame all; calculate structure; spacefill off; wireframe off; cartoons on; select helix; color red; select sheet; color yellow; select loop; color gray; select not (helix or sheet or loop); color gray;';"
        "var Info={width:280,height:260,use:'HTML5',color:'#1a1d23',j2sPath:'https://chemapps.stolaf.edu/jmol/jsmol/j2s',script:script};"
        "var applet=Jmol.getApplet('jsmol_align_ss',Info);"
        "c.innerHTML=Jmol.getAppletHtml(applet);"
        "}"
        "if(typeof Jmol!=='undefined'){init();return;}"
        "var s=document.createElement('script');s.src='https://chemapps.stolaf.edu/jmol/jsmol/JSmol.min.js';s.onload=init;document.head.appendChild(s);"
        "};"
        "})();</script>"
    )


def _matrix_raw_html(raw_txt, path_set):
    """Rendert die Rohmatrix als Tabelle; Zellen auf dem Trace-back-Pfad werden hervorgehoben."""
    if not raw_txt:
        return "<pre class='dp-matrix-raw'></pre>"
    lines = [L for L in raw_txt.strip().split("\n") if L]
    if not lines:
        return "<pre class='dp-matrix-raw'>" + cgi.escape(raw_txt) + "</pre>"
    if path_set is None:
        return "<pre class='dp-matrix-raw'>" + cgi.escape(raw_txt) + "</pre>"
    out = ["<table class='dp-matrix-table'><tbody>"]
    for i, line in enumerate(lines):
        cells = line.split("\t")
        out.append("<tr>")
        for j, cell in enumerate(cells):
            esc = cgi.escape(cell)
            if (i, j) in path_set:
                out.append("<td class='dp-path-cell'>" + esc + "</td>")
            else:
                out.append("<td>" + esc + "</td>")
        out.append("</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def dp_top_preview_html(dp_entries):
    if not dp_entries:
        return ""
    first = dp_entries[0]
    first_name, first_b64, first_raw = first[0], first[1], first[2]
    count = len(dp_entries)
    return (
        "<div class='dp-top-preview'>"
        "<div>"
        "<h3>DP-Matrizen sind verf&uuml;gbar</h3>"
        "<p>Sie wurden f&uuml;r dieses Alignment bereits erzeugt. Du kannst sie direkt von hier aus &ouml;ffnen, ohne erst nach unten zu scrollen.</p>"
        "<div class='dp-top-actions'>"
        "<button type='button' class='dp-jump-btn' onclick=\"var s=document.getElementById('dp-section'); if(s){ s.classList.add('expanded'); s.scrollIntoView({behavior:'smooth', block:'start'}); }\">&#9654; DP-Matrizen jetzt anzeigen</button>"
        "<button type='button' class='dp-jump-btn' onclick=\"var s=document.getElementById('dp-section'); if(s){ s.classList.toggle('expanded'); }\">Ein-/Ausklappen</button>"
        "</div>"
        "<p class='dp-preview-note'>"
        + str(count) + " Matrix"
        + ("en" if count != 1 else "")
        + " gefunden"
        + (" &middot; mit Zahlenansicht" if first_raw is not None else "")
        + "</p>"
        "</div>"
        "<div class='dp-preview-thumb'><img src='data:image/png;base64," + first_b64 + "' alt='DP-Vorschau " + cgi.escape(first_name) + "' /></div>"
        "</div>"
    )


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


def _print_validation_and_tuning(ali_download_out, pairs_data, seqlib_data):
    """Nach jedem Alignment: Validation-Box (wenn ALI vorhanden) und Link/Formular zum Parameter-Tuning."""
    if not ali_download_out:
        return
    ali = ali_download_out if isinstance(ali_download_out, str) else (ali_download_out or b"").decode("utf-8", errors="replace")
    print("<div class='validate-box'><h3>Mit diesem Ergebnis validieren</h3>")
    print("<p>Referenz: <strong>hochladen</strong>, <strong>Beispieldatei</strong> w&auml;hlen oder <strong>Referenz aus HOMSTRAD</strong> (strukturbasierte Referenz-Alignments; PDB-IDs z.&nbsp;B. 1bgxt, 2pgd &ndash; erste 4 Zeichen werden mit HOMSTRAD-Dateien abgeglichen).</p>")
    print("<form action='validate.cgi' method='post' enctype='multipart/form-data'>")
    print("<input type='hidden' name='show_plots' value='1'>")
    print("<textarea name='candidate_ali' style='display:none;'>")
    print(cgi.escape(ali))
    print("</textarea>")
    print("<p><label>Referenz-Datei: <input type='file' name='reference_file' accept='.ali,.txt'></label></p>")
    print("<p>Oder Beispieldatei: <select name='reference_example'><option value=''>&ndash; w&auml;hlen &ndash;</option><option value='example.validation.ali'>example.validation.ali</option><option value='mini.validation.ali'>mini.validation.ali</option></select></p>")
    print("<p><label><input type='checkbox' name='reference_homstrad' value='1'> Referenz aus HOMSTRAD</label></p>")
    print("<button type='submit' class='btn'>Jetzt validieren</button>")
    print("</form></div>")
    # Parameter-Tuning: Eingaben übernehmen, Nutzer muss nur auf Ausführen drücken
    print("<div class='validate-box'><h3>Parameter-Tuning mit diesem Alignment</h3>")
    print("<p>Eingaben werden &uuml;bernommen; auf der Tuning-Seite nur noch auf <strong>Ausf&uuml;hren</strong> dr&uuml;cken (Referenz = dieses Alignment).</p>")
    print("<form action='tuning.cgi' method='post' enctype='multipart/form-data'>")
    print("<textarea name='ref_content' style='display:none;'>")
    print(cgi.escape(ali))
    print("</textarea>")
    if pairs_data:
        pairs_str = pairs_data.decode("utf-8", errors="replace") if isinstance(pairs_data, bytes) else str(pairs_data)
        print("<textarea name='pairs_content' style='display:none;'>")
        print(cgi.escape(pairs_str))
        print("</textarea>")
    if seqlib_data:
        seqlib_str = seqlib_data.decode("utf-8", errors="replace") if isinstance(seqlib_data, bytes) else str(seqlib_data)
        print("<textarea name='seqlib_content' style='display:none;'>")
        print(cgi.escape(seqlib_str))
        print("</textarea>")
    print("<button type='submit' class='btn'>Zum Parameter-Tuning</button>")
    print("</form></div>")


def friendly_alignment_error(raw_output, fallback_err):
    text = raw_output or ""
    m = re.search(r"Unknown residue:\s*'([^']+)'\s*or\s*'([^']+)'", text)
    if m:
        a = cgi.escape(m.group(1))
        b = cgi.escape(m.group(2))
        return (
            "Ung&uuml;ltige Aminos&auml;ure im manuellen Seqlib-Text: <strong>%s</strong> oder <strong>%s</strong>."
            " Bitte verwende g&uuml;ltige Ein-Buchstaben-Codes, die in der gew&auml;hlten Matrix vorkommen"
            " (z.&nbsp;B. <code>ACDEFGHIKLMNPQRSTVWY</code>). "
            "Dein Beispiel <code>1:ABC</code> / <code>2:ABD</code> enth&auml;lt <code>B</code>, das von deiner Matrix hier nicht unterst&uuml;tzt wird."
        ) % (a, b)
    return cgi.escape(fallback_err or "Unbekannter Fehler")


def parse_manual_sequences(text):
    """Unterstützt FASTA (>id\\nSEQ) und id:SEQ. Rückgabe: [(id, seq), ...]."""
    text = (text or "").strip()
    if not text:
        return []
    entries = []
    if ">" in text:
        current_id = None
        seq_parts = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current_id and seq_parts:
                    entries.append((current_id, "".join(seq_parts).replace(" ", "")))
                current_id = line[1:].strip().split()[0] if line[1:].strip() else None
                seq_parts = []
            else:
                seq_parts.append(line.replace(" ", ""))
        if current_id and seq_parts:
            entries.append((current_id, "".join(seq_parts).replace(" ", "")))
    else:
        for raw in text.splitlines():
            line = raw.strip()
            if not line or ":" not in line:
                continue
            sid, seq = line.split(":", 1)
            sid = sid.strip()
            seq = seq.strip().replace(" ", "")
            if sid and seq:
                entries.append((sid, seq))
    cleaned = []
    for sid, seq in entries:
        seq = re.sub(r"\s+", "", seq).upper()
        if sid and seq:
            cleaned.append((sid, seq))
    return cleaned


def seqlib_text_from_entries(entries):
    return "".join(["%s:%s\n" % (sid, seq) for sid, seq in entries])


def parse_seq_ids(text):
    text = (text or "").strip()
    if not text:
        return []
    parts = re.split(r"[\s,;]+", text)
    out = []
    for p in parts:
        v = p.strip()
        if v:
            out.append(v)
    return out


def normalize_seq_source(source):
    src = (source or "").strip().lower()
    if src in ("pdb",):
        return "pdb"
    if src in ("swissprot", "swiss-prot"):
        return "swissprot"
    if src in ("uniprot", "uniprotkb"):
        return "uniprot"
    return src or "pdb"


def extract_ids_from_seqlib_text(text):
    ids = []
    seen = set()
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or ":" not in line:
            continue
        sid = line.split(":", 1)[0].strip()
        if sid and sid not in seen:
            seen.add(sid)
            ids.append(sid)
    return ids


def build_all_pairs(ids):
    pairs = []
    for a, b in itertools.combinations(ids, 2):
        pairs.append("%s %s\n" % (a, b))
    return "".join(pairs)


def parse_ali_blocks(text):
    blocks = []
    lines = (text or "").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith(">") and i + 2 < len(lines):
            l1 = lines[i + 1].rstrip()
            l2 = lines[i + 2].rstrip()
            if ": " in l1 and ": " in l2:
                blocks.append((line, l1, l2))
                i += 3
                while i < len(lines) and "_ss:" in (lines[i] or ""):
                    i += 1
                continue
        i += 1
    return blocks


def alignment_csv_from_ali(text):
    rows = ["id1,id2,score,aligned_seq1,aligned_seq2"]
    for header, l1, l2 in parse_ali_blocks(text):
        parts = header[1:].strip().split()
        if len(parts) >= 3:
            id1, id2, score = parts[0], parts[1], parts[2]
        elif len(parts) >= 2:
            id1, id2, score = parts[0], parts[1], ""
        else:
            continue
        seq1 = l1.split(":", 1)[1].strip() if ":" in l1 else l1.strip()
        seq2 = l2.split(":", 1)[1].strip() if ":" in l2 else l2.strip()
        def esc(v):
            s = str(v).replace('"', '""')
            return '"' + s + '"'
        rows.append(",".join([esc(id1), esc(id2), esc(score), esc(seq1), esc(seq2)]))
    return "\n".join(rows) + "\n"


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


def parse_levitt_matrix_text(content):
    if not content:
        return None, None
    if isinstance(content, bytes):
        text = content.decode("utf-8", errors="replace")
    else:
        text = str(content)
    rowindex = None
    rows = []
    for raw in text.splitlines():
        line = (raw or "").strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("ROWINDEX"):
            parts = line.split()
            if len(parts) > 1:
                rowindex = parts[1].strip()
        elif line.startswith("MATRIX"):
            parts = line.split()[1:]
            if parts:
                rows.append(parts)
    if not rowindex or not rows:
        return None, None
    return rowindex, rows[:len(rowindex)]


def levitt_matrix_html(content):
    rowindex, rows = parse_levitt_matrix_text(content)
    if not rowindex or not rows:
        return ""
    html = "<div class='ss-levitt-box'><div class='ss-levitt-title'>Aktive Levitt-Matrix (H/E/C)</div><table class='ss-levitt-table'><thead><tr><th></th>"
    for col in rowindex:
        html += "<th>" + cgi.escape(col) + "</th>"
    html += "</tr></thead><tbody>"
    for r_idx, row_char in enumerate(rowindex):
        html += "<tr><th>" + cgi.escape(row_char) + "</th>"
        row_vals = rows[r_idx] if r_idx < len(rows) else []
        for c_idx in range(len(rowindex)):
            val = row_vals[c_idx] if c_idx < len(row_vals) else ""
            cell_cls = "ss-levitt-pos" if str(val).startswith(("+", "1", "2", "3", "4", "5", "6", "7", "8", "9")) and str(val) != "0" else "ss-levitt-neg" if str(val).startswith("-") else "ss-levitt-neutral"
            html += "<td class='" + cell_cls + "'>" + cgi.escape(str(val)) + "</td>"
        html += "</tr>"
    html += "</tbody></table></div>"
    return html


def inject_ss_info_html(body, info_html):
    if not info_html:
        return body
    marker_3d = '<div class="ali-3d-block">'
    if marker_3d in body:
        return body.replace(marker_3d, info_html + marker_3d, 1)
    marker_ss = '</div></div><div class="ali-3d-block">'
    if marker_ss in body:
        return body.replace(marker_ss, '</div></div>' + info_html + '<div class="ali-3d-block">', 1)
    if 'class="ali-ss-block"' in body:
        end_idx = body.find('</div>', body.find('class="ali-ss-block"'))
        if end_idx >= 0:
            return body[:end_idx + 6] + info_html + body[end_idx + 6:]
    return body + info_html


def ss_scoring_info_html(ss_weight, ss_source_label, levitt_source_label, levitt_content=None):
    matrix_html = levitt_matrix_html(levitt_content)
    return (
        "<details class='ss-score-box'><summary>Wie wird die Sekund&auml;rstruktur ber&uuml;cksichtigt?</summary>"
        "<div class='ss-score-body'>"
        "<p>Die <strong>H/E/C</strong>-Zeichen werden nicht separat mit einem eigenen Alignment ausgerichtet, sondern "
        "sie laufen im <strong>gleichen dynamischen Programm</strong> wie die Aminos&auml;uresequenzen mit. "
        "Bei jedem Diagonalschritt wird der normale Sequenzscore um einen zus&auml;tzlichen SS-Beitrag erweitert.</p>"
        "<p class='ss-score-formula'><code>Gesamtscore = Sequenzscore + SS-Gewicht &times; Levitt(H/E/C-Score)</code></p>"
        "<p>Das bedeutet: <strong>H-H</strong>, <strong>E-E</strong> oder <strong>C-C</strong> geben je nach Levitt-Matrix "
        "einen positiven Zusatzbeitrag, w&auml;hrend z.&nbsp;B. <strong>H-E</strong> oder <strong>H-C</strong> schlechter bewertet werden. "
        "Gaps werden weiterhin &uuml;ber die normalen Gap-Penalties des Alignments behandelt; es gibt keine separate SS-Gap-Strafe.</p>"
        "<div class='ss-feature-list'>"
        "<div class='ss-feature-item'><strong>Was wird aligned?</strong> Die Aminos&auml;uresequenzen bestimmen weiterhin den Pfad; die SS beeinflusst nur den Score auf passenden Positionen.</div>"
        "<div class='ss-feature-item'><strong>Wie wirken H/E/C?</strong> Gleiche Zust&auml;nde werden bevorzugt, ungleiche Zust&auml;nde abgestraft oder schw&auml;cher bewertet.</div>"
        "<div class='ss-feature-item'><strong>Rolle von SS-Gewicht</strong> Je gr&ouml;&szlig;er der Wert, desto st&auml;rker beeinflusst die Sekund&auml;rstruktur den gew&auml;hlten Alignment-Pfad.</div>"
        "<div class='ss-feature-item'><strong>Rolle der Levitt-Matrix</strong> Sie legt fest, wie gut oder schlecht jedes Paar wie <code>H/H</code>, <code>H/E</code> oder <code>C/C</code> bewertet wird.</div>"
        "</div>"
        + matrix_html +
        "<div class='ss-score-meta'>"
        "<span class='ss-score-chip'>SS-Gewicht: " + cgi.escape(str(ss_weight)) + "</span>"
        "<span class='ss-score-chip'>SS-Quelle: " + cgi.escape(ss_source_label) + "</span>"
        "<span class='ss-score-chip'>Levitt-Matrix: " + cgi.escape(levitt_source_label) + "</span>"
        "</div>"
        "</div></details>"
    )


def alignment_downloads_html(ali_text, dp_entries, html_content=None):
    links = []
    if ali_text:
        links.append(make_download_link("alignment_result.ali", "ALI herunterladen", ali_text))
        csv_text = alignment_csv_from_ali(ali_text)
        links.append(make_download_link("alignment_result.csv", "CSV-Tabelle herunterladen", csv_text, "text/csv;charset=utf-8"))
    if html_content:
        links.append(make_download_link("alignment_result.html", "HTML herunterladen", html_content, "text/html;charset=utf-8"))
    matrix_links = []
    for entry in dp_entries:
        name, b64, raw_txt = entry[0], entry[1], entry[2]
        try:
            png_bytes = base64.b64decode(b64)
            matrix_links.append(make_download_link(name + "_M.png", name + " PNG", png_bytes, "image/png"))
        except Exception:
            pass
        if raw_txt is not None:
            matrix_links.append(make_download_link(name + "_M.txt", name + " TXT", raw_txt))
    html = "<div class='validate-box'><h3>Downloads</h3><p>Alle erzeugten Dateien k&ouml;nnen direkt heruntergeladen werden.</p><div style='display:flex;flex-wrap:wrap;gap:0.6rem;'>%s</div>" % ("".join(links))
    if matrix_links:
        html += "<p style='margin-top:1rem;'><strong>DP-Matrizen:</strong></p><div style='display:flex;flex-wrap:wrap;gap:0.6rem;'>%s</div>" % ("".join(matrix_links))
    html += "</div>"
    return html


def main():
    if os.environ.get("REQUEST_METHOD") != "POST":
        print("Status: 405 Method Not Allowed")
        print("Content-Type: text/plain; charset=utf-8")
        print()
        print("Nur POST erlaubt.")
        return

    form = cgi.FieldStorage()

    mode = form.getfirst("mode", "global")
    algorithm = form.getfirst("algorithm", "gotoh")
    gap_open = form.getfirst("gap_open", "-12")
    gap_extend = form.getfirst("gap_extend", "-1")
    out_format = form.getfirst("format", "ali")
    want_dp_numbers = form.getfirst("dpmatrices", "") in ("1", "yes", "true")
    want_dp_heatmap = form.getfirst("dpmatrices_heatmap", "") in ("1", "yes", "true")
    want_dpmatrices = want_dp_numbers or want_dp_heatmap
    pairs_mode = (form.getfirst("pairs_mode") or "upload").strip()
    seqlib_mode = (form.getfirst("seqlib_mode") or "upload").strip()

    def get_upload_bytes(fieldname):
        # Python 3.6: FieldStorage hat kein .get(), nur form[key] / "key in form"
        if fieldname not in form:
            return None
        f = form[fieldname]
        if isinstance(f, list):
            f = f[0] if f else None
        if f is None:
            return None
        if hasattr(f, "file") and f.file is not None:
            try:
                data = f.file.read()
                return data if data else None
            except Exception:
                return None
        if hasattr(f, "value"):
            v = f.value
            if v is None:
                return None
            return v.encode("utf-8") if isinstance(v, str) else v
        return None

    def read_example_file(subpath, subdir="test"):
        """Liest Beispieldatei aus BASE_DIR/test/ oder BASE_DIR/MATRICES/ (subdir=MATRICES)."""
        path = os.path.join(BASE_DIR, subdir, subpath) if subpath else None
        if not path or not os.path.isfile(path):
            return None
        try:
            with open(path, "rb") as f:
                return f.read()
        except Exception:
            return None

    pairs_example = (form.getfirst("pairs_example") or "").strip()
    seqlib_example = (form.getfirst("seqlib_example") or "").strip()
    seqlib_text = form.getfirst("seqlib_text", "")
    matrix_example = (form.getfirst("matrix_example") or "").strip()
    levitt_example = (form.getfirst("levitt_example") or "").strip()
    seqlib_ss_example = (form.getfirst("seqlib_ss_example") or "").strip()

    pairs_data = get_upload_bytes("pairs_file")
    if not pairs_data and pairs_example:
        pairs_data = read_example_file(pairs_example, "test")
    seqlib_data = get_upload_bytes("seqlib_file")
    if not seqlib_data and seqlib_example:
        seqlib_data = read_example_file(seqlib_example, "test")
    manual_entries = parse_manual_sequences(seqlib_text) if seqlib_mode == "text" else []
    if manual_entries:
        seqlib_data = seqlib_text_from_entries(manual_entries).encode("utf-8")
    matrix_data = get_upload_bytes("matrix_file")
    if not matrix_data and matrix_example:
        matrix_data = read_example_file(matrix_example, "MATRICES")
    if not matrix_data and matrix_example:
        matrix_data = read_example_file(matrix_example, "test")
    levitt_data = get_upload_bytes("levitt_file")
    if not levitt_data and levitt_example:
        levitt_data = read_example_file(levitt_example, "test")
    seqlib_ss_data = get_upload_bytes("seqlib_ss_file")
    if not seqlib_ss_data and seqlib_ss_example:
        seqlib_ss_data = read_example_file(seqlib_ss_example, "test")
    seq_source = normalize_seq_source(form.getfirst("seq_source"))
    seq_source_keys = parse_seq_ids(form.getfirst("seq_source_keys", ""))
    ss_weight = (form.getfirst("ss_weight") or "0").strip()
    if matrix_data is not None and len(matrix_data) == 0:
        matrix_data = None
    if levitt_data is not None and len(levitt_data) == 0:
        levitt_data = None
    if seqlib_ss_data is not None and len(seqlib_ss_data) == 0:
        seqlib_ss_data = None

    # Optional: mehrere Sequenzen per ID aus DB/PDB holen und an Seqlib anhaengen
    resolved_entries = []
    auto_ss_entries = []
    if seq_source_keys:
        try:
            sys.path.insert(0, SCRIPT_DIR)
            from alignment_db_sequence import resolve_sequence_id
            for source_key in seq_source_keys:
                res = resolve_sequence_id(seq_source, source_key, try_external=True)
                if res and res.get("seq"):
                    sid = re.sub(r"[^A-Za-z0-9_-]", "_", source_key.strip())[:40] or "seq_from_id"
                    ss_seq = re.sub(r"[^HEC]", "", (res.get("ss_seq") or "").upper())
                    resolved_entries.append({
                        "sid": sid,
                        "seq": re.sub(r"\s+", "", res["seq"]).upper(),
                        "ss_seq": ss_seq,
                    })
        except Exception:
            pass

    if resolved_entries:
        base_text = ""
        if seqlib_data:
            base_text = seqlib_data.decode("utf-8", errors="replace") if isinstance(seqlib_data, bytes) else str(seqlib_data)
            if base_text and not base_text.endswith("\n"):
                base_text += "\n"
        base_ids = set(extract_ids_from_seqlib_text(base_text))
        for entry in resolved_entries:
            sid = entry["sid"]
            seq = entry["seq"]
            final_sid = sid
            counter = 2
            while final_sid in base_ids:
                final_sid = "%s_%d" % (sid, counter)
                counter += 1
            base_text += final_sid + ":" + seq + "\n"
            base_ids.add(final_sid)
            if entry.get("ss_seq"):
                auto_ss_entries.append((final_sid, entry["ss_seq"]))
        seqlib_data = base_text.encode("utf-8")

    if not seqlib_data:
        print("Content-Type: text/html; charset=utf-8")
        print()
        if seq_source_keys:
            print("<p>Fehler: Die angegebenen IDs konnten nicht in Sequenzen umgewandelt werden. Bei <strong>UniProt</strong> (z.&nbsp;B. P00439): Quelle &bdquo;UniProt&ldquo; w&auml;hlen oder g&uuml;ltige Accession eingeben. Bei <strong>PDB</strong>: 4 Zeichen (z.&nbsp;B. 1tim). Alternativ Seqlib-Datei / FASTA verwenden.</p>")
        else:
            print("<p>Fehler: Bitte eine Seqlib-Datei hochladen, eine Beispieldatei ausw&auml;hlen, FASTA/id:SEQ eingeben oder IDs angeben.</p>")
        return

    seqlib_text_all = seqlib_data.decode("utf-8", errors="replace") if isinstance(seqlib_data, bytes) else str(seqlib_data)
    seqlib_ids = extract_ids_from_seqlib_text(seqlib_text_all)
    auto_ss_from_db_used = False
    levitt_auto_used = False
    if auto_ss_entries and not seqlib_ss_data:
        auto_ss_map = dict(auto_ss_entries)
        if seqlib_ids and all(sid in auto_ss_map and auto_ss_map[sid] for sid in seqlib_ids):
            seqlib_ss_data = "".join(["%s:%s\n" % (sid, auto_ss_map[sid]) for sid in seqlib_ids]).encode("utf-8")
            auto_ss_from_db_used = True
    if seqlib_ss_data and not levitt_data:
        levitt_data = read_example_file("levitt_matrix.txt", "test")
        if levitt_data:
            levitt_auto_used = True
    if levitt_data is not None and len(levitt_data) == 0:
        levitt_data = None
    if seqlib_ss_data is not None and len(seqlib_ss_data) == 0:
        seqlib_ss_data = None
    use_ss = bool(levitt_data and seqlib_ss_data)
    ss_source_label = "Upload/Beispieldatei"
    if auto_ss_from_db_used:
        ss_source_label = "automatisch aus Datenbank"
    levitt_source_label = "Upload/Beispieldatei"
    if levitt_auto_used:
        levitt_source_label = "automatisch (levitt_matrix.txt)"
    auto_pairs_requested = (pairs_mode == "auto")
    if not pairs_data and (auto_pairs_requested or len(seqlib_ids) >= 2):
        auto_pairs = build_all_pairs(seqlib_ids)
        if auto_pairs.strip():
            pairs_data = auto_pairs.encode("utf-8")

    if not pairs_data:
        print("Content-Type: text/html; charset=utf-8")
        print()
        print("<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>")
        print("<p><a href='../alignment.html'>&#8592; Zur&uuml;ck</a></p>")
        print("<p>Fehler: Bitte eine <strong>Pairs-Datei</strong> hochladen, eine Beispieldatei ausw&auml;hlen oder mindestens zwei Sequenzen f&uuml;r Auto-Pairs angeben.</p>")
        print("</body></html>")
        return

    first_pdb1, first_pdb2 = _parse_first_pdb_pair(pairs_data)

    tmpdir = tempfile.mkdtemp(prefix="align_")
    try:
        with open(os.path.join(tmpdir, "pairs.txt"), "wb") as f:
            f.write(pairs_data if isinstance(pairs_data, bytes) else pairs_data.encode("utf-8"))
        with open(os.path.join(tmpdir, "seqlib.txt"), "wb") as f:
            f.write(seqlib_data if isinstance(seqlib_data, bytes) else seqlib_data.encode("utf-8"))
        matrix_path = os.path.join(tmpdir, "matrix.mat")
        if matrix_data and len(matrix_data) > 0:
            with open(matrix_path, "wb") as f:
                f.write(matrix_data if isinstance(matrix_data, bytes) else matrix_data.encode("utf-8"))
        elif os.path.isfile(DEFAULT_MATRIX):
            shutil.copy(DEFAULT_MATRIX, matrix_path)
        else:
            print("Content-Type: text/html; charset=utf-8")
            print()
            print("<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>")
            print("<p><a href='../alignment.html'>&#8592; Zur&uuml;ck</a></p>")
            print("<p>Fehler: Keine Substitutionsmatrix. Bitte <strong>dayhoff.mat</strong> auf den Server in <code>public_html/</code> legen oder beim Alignment eine Matrix-Datei hochladen.</p>")
            print("</body></html>")
            return

        args = [
            "--pairs", "pairs.txt",
            "--seqlib", "seqlib.txt",
            "-m", "matrix.mat",
            "--go", str(gap_open),
            "--ge", str(gap_extend),
            "--mode", mode,
            "--format", out_format,
        ]
        if algorithm == "nw":
            args.append("--nw")
        if use_ss:
            with open(os.path.join(tmpdir, "levitt.mat"), "wb") as f:
                f.write(levitt_data if isinstance(levitt_data, bytes) else levitt_data.encode("utf-8"))
            with open(os.path.join(tmpdir, "seqlib_ss.txt"), "wb") as f:
                f.write(seqlib_ss_data if isinstance(seqlib_ss_data, bytes) else seqlib_ss_data.encode("utf-8"))
            args.extend(["--levitt", "levitt.mat", "--seqlib-ss", "seqlib_ss.txt", "--ss-weight", ss_weight])
        dp_dir = None
        if want_dpmatrices:
            dp_dir = os.path.join(tmpdir, "dp")
            os.makedirs(dp_dir, exist_ok=True)
            args.extend(["--dpmatrices", "dp"])
            # Bei HTML-Auswahl immer format=html beibehalten, damit das schöne Alignment (Matches/Mismatches) geliefert wird.

        out, err = run_jar(ALIGNMENT_JAR, args, tmpdir)
        if err:
            print("Content-Type: text/html; charset=utf-8")
            print()
            print("<!DOCTYPE html><html><head><meta charset='utf-8'><title>Fehler</title></head><body>")
            print("<p><a href='../alignment.html'>&#8592; Zur&uuml;ck</a></p>")
            print("<h2>Fehler</h2>")
            print("<p>%s</p>" % friendly_alignment_error(out, err))
            if out and "Unknown residue" not in out:
                print("<pre>")
                print(cgi.escape(out or ""))
                print("</pre>")
            print("</body></html>")
            return

        ali_download_out = out if out_format == "ali" else ""
        if not ali_download_out:
            ali_args = list(args)
            for idx in range(len(ali_args) - 1):
                if ali_args[idx] == "--format":
                    ali_args[idx + 1] = "ali"
            ali_out_tmp, ali_err_tmp = run_jar(ALIGNMENT_JAR, ali_args, tmpdir)
            if not ali_err_tmp and ali_out_tmp:
                ali_download_out = ali_out_tmp

        # Bei Sekundärstruktur: zusätzlich Alignment ohne SS für Vergleich (nicht nötig bei Gewicht 0)
        body_no_ss = None
        try:
            ss_w_val = float(ss_weight)
        except (TypeError, ValueError):
            ss_w_val = 0.0
        if use_ss and ss_w_val != 0.0:
            args_no_ss = [
                "--pairs", "pairs.txt", "--seqlib", "seqlib.txt", "-m", "matrix.mat",
                "--go", str(gap_open), "--ge", str(gap_extend), "--mode", mode, "--format", "html",
            ]
            if algorithm == "nw":
                args_no_ss.append("--nw")
            out_no_ss, err_no_ss = run_jar(ALIGNMENT_JAR, args_no_ss, tmpdir)
            if not err_no_ss and out_no_ss:
                body_no_ss = extract_jar_body(out_no_ss)
                if not body_no_ss or "ali-card" not in body_no_ss:
                    body_no_ss = "<div class='ali-block'><h3>Alignment ohne SS</h3><pre class='raw'>" + cgi.escape(out_no_ss or "") + "</pre></div>" if out_no_ss else None

        # Optional: DP-Heatmaps + Rohmatrix (_M.txt) + Trace-back-Pfad (_path.txt) einlesen
        dp_entries = []  # [(name, b64_png, raw_txt or None, path_set or None), ...]
        if want_dpmatrices and dp_dir and os.path.isdir(dp_dir):
            import base64
            for f in sorted(os.listdir(dp_dir)):
                if f.endswith("_M.png"):
                    name = f.replace("_M.png", "")
                    path_png = os.path.join(dp_dir, f)
                    path_txt = os.path.join(dp_dir, name + "_M.txt")
                    path_path = os.path.join(dp_dir, name + "_path.txt")
                    b64 = None
                    raw_txt = None
                    path_set = None
                    try:
                        with open(path_png, "rb") as fp:
                            b64 = base64.b64encode(fp.read()).decode("ascii")
                    except Exception:
                        pass
                    if b64:
                        try:
                            with open(path_txt, "r", encoding="utf-8", errors="replace") as fp:
                                raw_txt = fp.read()
                        except Exception:
                            pass
                        try:
                            with open(path_path, "r", encoding="utf-8", errors="replace") as fp:
                                path_set = set()
                                for line in fp:
                                    line = line.strip()
                                    if not line:
                                        continue
                                    parts = line.split()
                                    if len(parts) >= 2:
                                        path_set.add((int(parts[0]), int(parts[1])))
                        except Exception:
                            path_set = None
                        dp_entries.append((name, b64, raw_txt, path_set))

        if out_format == "html" and not dp_entries:
            print_result_start("Alignment Ergebnis", "../alignment.html", "Zurück zur Alignment-Seite")
            body = extract_jar_body(out)
            # Falls JAR kein HTML geliefert hat (leerer Body oder nur Text): Ali-Output lesbar anzeigen
            if not body.strip() or "ali-card" not in body:
                if not (out or "").strip():
                    body = "<p class='error'>Das Programm hat keine Ausgabe geliefert. Bitte prüfen Sie, ob <strong>Pairs</strong>- und <strong>Seqlib</strong>-Datei gültig sind und die gewählten Beispieldateien auf dem Server vorhanden sind. Für die farbige HTML-Darstellung muss <code>alignment.jar</code> mit <strong>Main-Class alignment.Main</strong> gebaut sein (<code>./build/build.sh</code>).</p>"
                else:
                    body = "<div class='ali-block'><h3>Alignment</h3><pre class='raw'>" + cgi.escape(out) + "</pre></div>"
            ss_info = inject_ss_info_html("", ss_scoring_info_html(ss_weight, ss_source_label, levitt_source_label, levitt_data)) if use_ss else ""
            page_body = body + jsmol_ss_html(use_ss, first_pdb1, first_pdb2)
            if use_ss and ss_info:
                page_body = ss_info + page_body
            print(alignment_downloads_html(ali_download_out, dp_entries, result_page_html_document("Alignment Ergebnis", page_body)))
            # Sekundärstruktur-Bereich: bei Gewicht 0 nur "ohne SS" anzeigen; sonst zwei Varianten (ohne / mit)
            if use_ss and ss_info:
                print("<div class='result-align-col'>")
                print(ss_info)
                try:
                    ss_w = float(ss_weight)
                except (TypeError, ValueError):
                    ss_w = 0.0
                if ss_w == 0.0:
                    print("<details class='ali-compare-details' open><summary>Alignment <strong>ohne</strong> Sekund&auml;rstruktur</summary><div class='ali-compare-body'>")
                    print(body)
                    print("</div></details>")
                else:
                    if body_no_ss:
                        print("<details class='ali-compare-details'><summary>Alignment <strong>ohne</strong> Sekund&auml;rstruktur</summary><div class='ali-compare-body'>")
                        print(body_no_ss)
                        print("</div></details>")
                    print("<details class='ali-compare-details' open><summary>Alignment <strong>mit</strong> Sekund&auml;rstruktur (Gewicht " + cgi.escape(ss_weight) + ")</summary><div class='ali-compare-body'>")
                    print(body)
                    print("</div></details>")
                print("</div>")
            else:
                print("<div class='result-align-col'>")
                print(body)
                print("</div>")
            print(jsmol_ss_html(use_ss, first_pdb1, first_pdb2))
            _print_validation_and_tuning(ali_download_out, pairs_data, seqlib_data)
            print_result_end()
        elif out_format == "html" and dp_entries:
            body = extract_jar_body(out)
            preview_html = dp_top_preview_html(dp_entries)
            # Kollabierbarer DP-Bereich: Anklicken zum Ein-/Ausblenden
            heatmaps_html = (
                "<div class='dp-section' id='dp-section'>"
                "<button type='button' class='dp-toggle-btn' onclick=\"document.getElementById('dp-section').classList.toggle('expanded')\" aria-expanded='false'>"
                "<span class='arrow'>&#9654;</span> DP-Matrix / Heatmap anzeigen"
                "</button>"
                "<div class='dp-content'>"
                "<div class='heatmaps'>"
                "<h2 class='heatmaps-title'>DP-Matrizen (Fixed Point)</h2>"
                "<div class='heatmaps-fixedpoint-expl'>"
                "<h3 class='dp-expl-title'>Was ist Fixed Point?</h3>"
                "<p>Die Berechnung verwendet <em>Fixed-Point-Arithmetik</em>: Scores werden mit einem festen Faktor skaliert und als ganze Zahlen gespeichert (z.&nbsp;B. <code>long</code>), um schnell und ohne Rundungsfehler zu rechnen. "
                "Die Formel f&uuml;r die Anzeige normalisiert die Rohwerte auf den Bereich [0,&nbsp;1], damit die Heatmap gut lesbar ist:</p>"
                "<p class='dp-formula'><code>norm(x) = (x − min) / (max − min)</code></p>"
                "<p>Dabei sind <code>min</code> und <code>max</code> der kleinste bzw. gr&ouml;&szlig;te g&uuml;ltige Eintrag in der Matrix <em>M</em>. So wird jeder Wert auf eine Farbe zwischen &bdquo;niedrig&ldquo; und &bdquo;hoch&ldquo; abgebildet.</p>"
                "</div>"
                "<div class='heatmaps-intro'>"
                "<h3 class='dp-expl-title'>Was zeigt die Heatmap? Was ist die DP-Matrix?</h3>"
                "<p>F&uuml;r jedes Sequenzpaar wird die <em>Score-Matrix M</em> der dynamischen Programmierung (Gotoh/NW) dargestellt. "
                "<strong>Heatmap</strong> = farbige Darstellung der Werte; <strong>DP-Matrix (Zahlen)</strong> = Rohwerte (Fixed Point). "
                "<strong>y-Achse (i)</strong> = Position in Sequenz&nbsp;1, <strong>x-Achse (j)</strong> = Position in Sequenz&nbsp;2. "
                "Jede Zelle entspricht <code>M(i,j)</code>. Der <strong>rote Pfad</strong> ist der Trace-back (optimales Alignment). "
                "F&uuml;r <strong>zwei lokale Alignments</strong> (zwei getrennte Striche): Modus <em>Local</em> w&auml;hlen und z.&nbsp;B. <strong>1bgxt</strong> / <strong>2pgd</strong> oder 2 aus: 1x01a, 1bif, 1k6ma, 1pgjb, 1c8ca, 1azpa, 1ayoa, 1edya, 1qqfa, 1c3d, 1g41a, 1e94e, 1e32a, 1d2na, 1bOua, 1f3oa, 1g291.</p>"
                "</div>"
            )
            for entry in dp_entries:
                name, b64, raw_txt, path_set = entry[0], entry[1], entry[2], entry[3] if len(entry) > 3 else None
                heatmaps_html += "<div class='dp-card'>"
                heatmaps_html += "<h3 class='dp-card-title'>" + cgi.escape(name) + "</h3>"
                heatmaps_html += "<p class='dp-card-desc'>Score-Matrix M: Achsen = Positionen in Seq1 bzw. Seq2.</p>"
                if want_dp_numbers and raw_txt is not None:
                    heatmaps_html += "<details class='dp-view-details' open><summary>DP-Matrix (Zahlen)</summary><div class='dp-matrix-raw-wrap'>"
                    heatmaps_html += _matrix_raw_html(raw_txt, path_set)
                    heatmaps_html += "</div></details>"
                if want_dp_heatmap:
                    heatmaps_html += "<details class='dp-view-details' open><summary>Fixed-Point-Heatmap (mit Trace-back)</summary><div class='dp-card-img-wrap'>"
                    heatmaps_html += "<img src='data:image/png;base64," + b64 + "' alt='DP-Matrix " + cgi.escape(name) + "' />"
                    heatmaps_html += "</div></details>"
                heatmaps_html += "</div>"
            heatmaps_html += "</div></div></div>"
            print_result_start("Alignment Ergebnis", "../alignment.html", "Zurück zur Alignment-Seite")
            if not body.strip() or "ali-card" not in body:
                if not (out or "").strip():
                    body = "<p class='error'>Das Programm hat keine Ausgabe geliefert. Bitte prüfen Sie Pairs- und Seqlib-Datei. Für die farbige HTML-Darstellung muss <code>alignment.jar</code> mit Main-Class alignment.Main gebaut sein.</p>"
                else:
                    body = "<div class='ali-block'><h3>Alignment</h3><pre class='raw'>" + cgi.escape(out) + "</pre></div>"
            ss_info = inject_ss_info_html("", ss_scoring_info_html(ss_weight, ss_source_label, levitt_source_label, levitt_data)) if use_ss else ""
            if use_ss and ss_info:
                body = ss_info + body
            page_body = body + jsmol_ss_html(use_ss, first_pdb1, first_pdb2) + heatmaps_html
            print(alignment_downloads_html(ali_download_out, dp_entries, result_page_html_document("Alignment Ergebnis", page_body)))
            print(preview_html)
            print("<div class='result-align-col'>")
            if use_ss and ss_info:
                print(ss_info)
                try:
                    ss_w = float(ss_weight)
                except (TypeError, ValueError):
                    ss_w = 0.0
                if ss_w == 0.0:
                    print("<details class='ali-compare-details' open><summary>Alignment <strong>ohne</strong> Sekund&auml;rstruktur</summary><div class='ali-compare-body'>")
                    print(body)
                    print("</div></details>")
                else:
                    if body_no_ss is not None:
                        print("<details class='ali-compare-details'><summary>Alignment <strong>ohne</strong> Sekund&auml;rstruktur</summary><div class='ali-compare-body'>")
                        print(body_no_ss)
                        print("</div></details>")
                    print("<details class='ali-compare-details' open><summary>Alignment <strong>mit</strong> Sekund&auml;rstruktur (Gewicht " + cgi.escape(ss_weight) + ")</summary><div class='ali-compare-body'>")
                    print(extract_jar_body(out))
                    print("</div></details>")
            else:
                print(body)
            print("</div>")
            print(jsmol_ss_html(use_ss, first_pdb1, first_pdb2))
            print(heatmaps_html)
            _print_validation_and_tuning(ali_download_out, pairs_data, seqlib_data)
            print_result_end()
        else:
            print_result_start("Alignment Ergebnis", "../alignment.html", "Zurück zur Alignment-Seite")
            page_body = "<h2>Ergebnis</h2><pre>" + cgi.escape(out) + "</pre>"
            print(alignment_downloads_html(ali_download_out or out, dp_entries, result_page_html_document("Alignment Ergebnis", page_body)))
            if dp_entries:
                print(dp_top_preview_html(dp_entries))
            print("<h2>Ergebnis</h2><pre>")
            print(cgi.escape(out))
            print("</pre>")
            _print_validation_and_tuning(ali_download_out or (out if (">" in out and ": " in out) else None), pairs_data, seqlib_data)
            if dp_entries:
                print("<div class='dp-section' id='dp-section'>")
                print("<button type='button' class='dp-toggle-btn' onclick=\"document.getElementById('dp-section').classList.toggle('expanded')\" aria-expanded='false'>")
                print("<span class='arrow'>&#9654;</span> DP-Matrix / Heatmap anzeigen")
                print("</button>")
                print("<div class='dp-content'>")
                print("<div class='heatmaps'>")
                print("<h2 class='heatmaps-title'>DP-Matrizen (Fixed Point)</h2>")
                print("<div class='heatmaps-fixedpoint-expl'>")
                print("<h3 class='dp-expl-title'>Was ist Fixed Point?</h3>")
                print("<p>Die Berechnung verwendet <em>Fixed-Point-Arithmetik</em>: Scores werden skaliert und als ganze Zahlen gespeichert. ")
                print("Zur Anzeige: <code>norm(x) = (x − min) / (max − min)</code>. <strong>Heatmap</strong> = Farbdarstellung, <strong>DP-Matrix (Zahlen)</strong> = Rohwerte.</p>")
                print("</div>")
                print("<div class='heatmaps-intro'>")
                print("<h3 class='dp-expl-title'>Was zeigt die Heatmap? Was ist die DP-Matrix?</h3>")
                print("<p><strong>y-Achse (i)</strong> = Position in Seq1, <strong>x-Achse (j)</strong> = Position in Seq2. Jede Zelle = <code>M(i,j)</code>. ")
                print("Roter Pfad = Trace-back. Zwei lokale Alignments (zwei Striche): Modus Local, z.&nbsp;B. 1bgxt/2pgd oder 1x01a/1bif.</p>")
                print("</div>")
                for entry in dp_entries:
                    name, b64, raw_txt = entry[0], entry[1], entry[2]
                    path_set = entry[3] if len(entry) > 3 else None
                    print("<div class='dp-card'>")
                    print("<h3 class='dp-card-title'>", cgi.escape(name), "</h3>")
                    print("<p class='dp-card-desc'>Score-Matrix M: Achsen = Positionen in Seq1 bzw. Seq2.</p>")
                    if want_dp_numbers and raw_txt is not None:
                        print("<details class='dp-view-details' open><summary>DP-Matrix (Zahlen)</summary><div class='dp-matrix-raw-wrap'>")
                        print(_matrix_raw_html(raw_txt, path_set))
                        print("</div></details>")
                    if want_dp_heatmap:
                        print("<details class='dp-view-details' open><summary>Fixed-Point-Heatmap (mit Trace-back)</summary><div class='dp-card-img-wrap'>")
                        print("<img src='data:image/png;base64,", b64, "' alt='DP-Matrix ", cgi.escape(name), "' />")
                        print("</div></details>")
                    print("</div>")
                print("</div></div></div>")
            print_result_end()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Content-Type: text/html; charset=utf-8")
        print()
        print("<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>")
        print("<p><a href='../alignment.html'>&#8592; Zur&uuml;ck</a></p>")
        print("<p><strong>Ein interner Fehler ist aufgetreten.</strong></p>")
        import traceback
        print("<pre style='background:#f0f0f0;padding:1em;overflow:auto;'>")
        print(cgi.escape(traceback.format_exc()))
        print("</pre></body></html>")
