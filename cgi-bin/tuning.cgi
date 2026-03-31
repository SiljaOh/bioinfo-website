#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CGI: Parameter-Tuning. Führt tune_params.py aus (Pairs, Seqlib, Referenz, go/ge-Listen)
und zeigt Tabelle + beste Parameter an.
"""
import os
import re
import sys
import io
import cgi
import cgitb
import subprocess
import tempfile
import shutil
import traceback

try:
    from result_layout import print_result_start, print_result_end
except ImportError:
    def print_result_start(title, back_url, back_label):
        print("Content-Type: text/html; charset=utf-8")
        print()
        print("<!DOCTYPE html><html><head><meta charset='utf-8'><title>%s</title></head><body>" % cgi.escape(title))
        print("<p><a href='%s'>%s</a></p>" % (cgi.escape(back_url), cgi.escape(back_label)))
    def print_result_end():
        print("</body></html>")

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
cgitb.enable()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
# Tuning-Skript: zuerst in public_html/src (Server), sonst Projekt-root/src (lokal)
TUNE_SCRIPT = os.path.join(BASE_DIR, "src", "tune_params.py")
if not os.path.isfile(TUNE_SCRIPT):
    TUNE_SCRIPT = os.path.join(BASE_DIR, "..", "src", "tune_params.py")
ALIGNMENT_JAR = os.path.join(BASE_DIR, "alignment.jar")
VALIDATE_JAR = os.path.join(BASE_DIR, "validateAli.jar")
DEFAULT_MATRIX = os.path.join(BASE_DIR, "dayhoff.mat")
MATRICES_DIR = os.path.join(BASE_DIR, "MATRICES")
# Für Matrix Auto: alle verfügbaren Matrizen (ohne Beschreibungsdateien)
def _list_auto_matrices():
    names = []
    if os.path.isdir(MATRICES_DIR):
        for f in sorted(os.listdir(MATRICES_DIR)):
            if f.endswith(".mat") and not f.startswith(".") and "Description" not in f and "InclusiveFormat" not in f:
                names.append(f)
    if not names and os.path.isfile(DEFAULT_MATRIX):
        names = ["dayhoff.mat"]
    return names


def parse_seq_ids(text):
    """IDs aus Text (Leerzeichen, Komma, Zeilenumbruch getrennt)."""
    if not (text or "").strip():
        return []
    parts = re.split(r"[\s,;]+", text.strip())
    return [p.strip() for p in parts if p.strip()]


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
    """IDs aus Seqlib-Text (id:SEQ Zeilen)."""
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
    """Alle Paare aus ID-Liste (eine Zeile 'id1 id2' pro Paar)."""
    import itertools
    pairs = []
    for a, b in itertools.combinations(ids, 2):
        pairs.append("%s %s\n" % (a, b))
    return "".join(pairs)


def main():
    if os.environ.get("REQUEST_METHOD") != "POST":
        print("Status: 405 Method Not Allowed")
        print("Content-Type: text/html; charset=utf-8")
        print()
        print("Nur POST erlaubt.")
        return

    form = cgi.FieldStorage()

    def read_upload(name):
        try:
            f = form[name] if name in form else None
        except (TypeError, KeyError):
            f = None
        if isinstance(f, list):
            f = f[0] if f else None
        if f is None:
            return None
        if hasattr(f, "file") and f.file:
            return f.file.read()
        if hasattr(f, "value"):
            v = f.value
            return v.encode("utf-8") if isinstance(v, str) else v
        return None

    def read_example(subpath, subdir="test"):
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
    ref_example = (form.getfirst("ref_example") or "").strip()
    matrix_example = (form.getfirst("matrix_example") or "").strip()
    ref_content = (form.getfirst("ref_content") or "").strip()
    pairs_content = (form.getfirst("pairs_content") or "").strip()
    seqlib_content = (form.getfirst("seqlib_content") or "").strip()
    pairs_mode = (form.getfirst("pairs_mode") or "upload").strip().lower()
    seqlib_mode = (form.getfirst("seqlib_mode") or "upload").strip().lower()
    seqlib_text = (form.getfirst("seqlib_text") or "").strip()
    seq_source = normalize_seq_source(form.getfirst("seq_source"))
    seq_source_keys = parse_seq_ids(form.getfirst("seq_source_keys", ""))
    reference_homstrad = form.getfirst("reference_homstrad", "") in ("1", "yes", "true")

    pairs_data = read_upload("pairs_file")
    if not pairs_data and pairs_content:
        pairs_data = pairs_content.encode("utf-8")
    if not pairs_data and pairs_example:
        pairs_data = read_example(pairs_example, "test")
    seqlib_data = read_upload("seqlib_file")
    if not seqlib_data and seqlib_content:
        seqlib_data = seqlib_content.encode("utf-8")
    if not seqlib_data and seqlib_mode == "text" and seqlib_text:
        seqlib_data = seqlib_text.encode("utf-8")
    if not seqlib_data and seqlib_example:
        seqlib_data = read_example(seqlib_example, "test")

    # PDB/UniProt/SwissProt-IDs auflösen und an Seqlib anhängen (wie Alignment)
    if seq_source_keys:
        try:
            sys.path.insert(0, SCRIPT_DIR)
            from alignment_db_sequence import resolve_sequence_id
            base_text = (seqlib_data.decode("utf-8", errors="replace") if seqlib_data else "") or ""
            if base_text and not base_text.endswith("\n"):
                base_text += "\n"
            base_ids = set(extract_ids_from_seqlib_text(base_text))
            for source_key in seq_source_keys:
                res = resolve_sequence_id(seq_source, source_key, try_external=True)
                if res and res.get("seq"):
                    sid = re.sub(r"[^A-Za-z0-9_-]", "_", source_key.strip())[:40] or "seq_from_id"
                    seq = re.sub(r"\s+", "", (res["seq"] or "").upper())
                    final_sid = sid
                    c = 2
                    while final_sid in base_ids:
                        final_sid = "%s_%d" % (sid, c)
                        c += 1
                    base_text += final_sid + ":" + seq + "\n"
                    base_ids.add(final_sid)
            seqlib_data = base_text.encode("utf-8")
        except Exception:
            pass

    seqlib_str = (seqlib_data or b"").decode("utf-8", errors="replace")
    seqlib_ids = extract_ids_from_seqlib_text(seqlib_str)
    if pairs_mode == "auto" and seqlib_ids and len(seqlib_ids) >= 2 and not pairs_data:
        pairs_data = build_all_pairs(seqlib_ids).encode("utf-8")

    ref_data = read_upload("ref_file")
    if not ref_data and ref_content:
        ref_data = ref_content.encode("utf-8")
    if not ref_data and not reference_homstrad and ref_example:
        ref_data = read_example(ref_example, "test")

    # Referenz aus HOMSTRAD (Datenbank)
    if reference_homstrad and pairs_data:
        pairs_str = pairs_data.decode("utf-8", errors="replace") if isinstance(pairs_data, bytes) else str(pairs_data)
        pairs_list = []
        for line in pairs_str.strip().splitlines():
            parts = line.strip().split()
            if len(parts) >= 2:
                pairs_list.append((parts[0], parts[1]))
        if pairs_list:
            try:
                sys.path.insert(0, SCRIPT_DIR)
                from homstrad_ref import build_ref_from_db
                ref_blocks = build_ref_from_db(pairs_list)
                if ref_blocks:
                    lines = []
                    for (a, b) in pairs_list:
                        key = (a, b) if (a, b) in ref_blocks else (b, a)
                        if key not in ref_blocks:
                            continue
                        line1, line2 = ref_blocks[key]
                        lines.append(">%s %s 0" % (a, b))
                        lines.append(line1)
                        lines.append(line2)
                        lines.append(line1)
                        lines.append(line2)
                    if lines:
                        ref_data = "\n".join(lines).encode("utf-8")
            except Exception:
                pass

    if not ref_data and reference_homstrad:
        print_result_start("Parameter-Tuning – Fehler", "../tuning.html", "Zurück zum Parameter-Tuning")
        print("<p class='error'>Keine HOMSTRAD-Referenz gefunden. Bitte PDB-IDs pr&uuml;fen (beide m&uuml;ssen in derselben HOMSTRAD-Familie liegen, z.&nbsp;B. 1bgxt und 1xo1a).</p>")
        print_result_end()
        return

    matrix_data = read_upload("matrix_file")
    if not matrix_data and matrix_example and (matrix_example or "").strip().lower() != "auto":
        matrix_data = read_example(matrix_example, "MATRICES")
    if not matrix_data and matrix_example and (matrix_example or "").strip().lower() != "auto":
        matrix_data = read_example(matrix_example, "test")
    go_list = (form.getfirst("go_list") or "-14 -12 -10 -8").strip()
    ge_list = (form.getfirst("ge_list") or "-2 -1").strip()
    mode = (form.getfirst("mode") or "local").strip().lower()
    if mode not in ("global", "local", "freeshift"):
        mode = "local"
    algorithm = (form.getfirst("algorithm") or "auto").strip().lower()
    if algorithm not in ("gotoh", "nw", "auto"):
        algorithm = "auto"
    matrix_mode = (form.getfirst("matrix_mode") or "example").strip().lower()
    matrix_auto = matrix_mode == "auto" or (form.getfirst("matrix_example") or "").strip() == "auto"

    if not pairs_data or not seqlib_data or not ref_data:
        print_result_start("Parameter-Tuning – Fehler", "../tuning.html", "Zurück zum Parameter-Tuning")
        print("<p class='error'>Pairs, Seqlib und Referenz angeben: PDB-IDs eingeben (z.&nbsp;B. 1bgxt, 1xo1a) und &quot;Auto&quot; bei Pairs w&auml;hlen, Referenz aus HOMSTRAD aktivieren oder Dateien hochladen bzw. Beispiele w&auml;hlen.</p>")
        print_result_end()
        return

    if matrix_auto:
        auto_matrix_list = _list_auto_matrices()
        if not auto_matrix_list:
            matrix_auto = False
            matrix_data = read_example("dayhoff.mat", "MATRICES") or read_example("dayhoff.mat", "test")

    tmpdir = tempfile.mkdtemp(prefix="tune_")
    try:
        with open(os.path.join(tmpdir, "pairs.txt"), "wb") as f:
            f.write(pairs_data)
        with open(os.path.join(tmpdir, "seqlib.txt"), "wb") as f:
            f.write(seqlib_data)
        with open(os.path.join(tmpdir, "ref.ali"), "wb") as f:
            f.write(ref_data)

        align_jar = os.path.abspath(ALIGNMENT_JAR if os.path.isfile(ALIGNMENT_JAR) else os.path.join(BASE_DIR, "alignment.jar"))
        val_jar = os.path.abspath(VALIDATE_JAR if os.path.isfile(VALIDATE_JAR) else os.path.join(BASE_DIR, "validateAli.jar"))
        if not os.path.isfile(TUNE_SCRIPT):
            print_result_start("Parameter-Tuning – Fehler", "../tuning.html", "Zurück zum Parameter-Tuning")
            print("<p class='error'>src/tune_params.py nicht gefunden. Bitte Ordner <code>src</code> auf den Server kopieren.</p>")
            print_result_end()
            return

        def run_one_tuning(matrix_path):
            cmd = [
                sys.executable, TUNE_SCRIPT,
                "--pairs", os.path.join(tmpdir, "pairs.txt"),
                "--seqlib", os.path.join(tmpdir, "seqlib.txt"),
                "-m", matrix_path,
                "--ref", os.path.join(tmpdir, "ref.ali"),
                "--go-list", *go_list.split(),
                "--ge-list", *ge_list.split(),
                "--mode", mode,
                "--algorithm", algorithm,
                "--alignment-jar", align_jar,
                "--validate-jar", val_jar,
            ]
            r = subprocess.run(cmd, cwd=BASE_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=600 if matrix_auto else 300, universal_newlines=True)
            return (r.stdout or "") + (r.stderr or "")

        def parse_output(out, matrix_name=""):
            rows = []
            good_range_lines = []
            for line in out.strip().split("\n"):
                if "\t" in line:
                    parts = line.split("\t")
                    try:
                        go = int(parts[0])
                        ge = int(parts[1])
                        if len(parts) >= 6 and parts[2].lower() in ("gotoh", "nw"):
                            algo = parts[2].strip()
                            sens = float(parts[3]) if parts[3].strip().lower() != "nan" else float("nan")
                            spec = float(parts[4]) if parts[4].strip().lower() != "nan" else float("nan")
                            f1 = float(parts[5]) if parts[5].strip().lower() != "nan" else float("nan")
                            rows.append((matrix_name, go, ge, algo, f1, sens, spec))
                        elif len(parts) >= 4 and parts[2].lower() in ("gotoh", "nw"):
                            algo = parts[2].strip()
                            val = float(parts[3]) if parts[3].strip().lower() != "nan" else float("nan")
                            rows.append((matrix_name, go, ge, algo, val, val, float("nan")))
                        elif len(parts) >= 3 and (parts[0].strip().startswith("-") or parts[0].strip().isdigit()):
                            val = float(parts[2]) if parts[2].strip().lower() != "nan" else float("nan")
                            rows.append((matrix_name, go, ge, "", val, val, float("nan")))
                    except ValueError:
                        pass
                if "Guter Bereich" in line or (line.strip().startswith("  --go ") and "F1 =" in line):
                    good_range_lines.append(line.strip())
            return rows, good_range_lines

        all_rows = []
        full_out = []

        if matrix_auto and auto_matrix_list:
            for mat_name in auto_matrix_list:
                mat_src = os.path.join(MATRICES_DIR, mat_name)
                if not os.path.isfile(mat_src):
                    raw = read_example(mat_name, "MATRICES") or read_example(mat_name, "test")
                    if raw:
                        mat_src = os.path.join(tmpdir, "m_" + mat_name)
                        with open(mat_src, "wb") as f:
                            f.write(raw)
                if not os.path.isfile(mat_src):
                    continue
                matrix_path = os.path.join(tmpdir, "matrix.mat")
                shutil.copy(mat_src, matrix_path)
                out = run_one_tuning(matrix_path)
                full_out.append("=== Matrix: %s ===\n%s" % (cgi.escape(mat_name), out))
                rows_one, _ = parse_output(out, mat_name)
                all_rows.extend(rows_one)
        else:
            matrix_path = os.path.join(tmpdir, "matrix.mat")
            if matrix_data and len(matrix_data) > 0:
                with open(matrix_path, "wb") as f:
                    f.write(matrix_data)
            elif os.path.isfile(DEFAULT_MATRIX):
                shutil.copy(DEFAULT_MATRIX, matrix_path)
            else:
                print_result_start("Parameter-Tuning – Fehler", "../tuning.html", "Zurück zum Parameter-Tuning")
                print("<p class='error'>Keine Substitutionsmatrix (dayhoff.mat) verf&uuml;gbar.</p>")
                print_result_end()
                return
            out = run_one_tuning(matrix_path)
            full_out.append(out)
            all_rows, best_line = parse_output(out, "")
            best_line = best_line or ""

        # Zeilen haben jetzt (mat_name, go, ge, algo, f1, sens, spec). Gute Zeilen: F1 im oberen Bereich
        good_rows = []
        if all_rows:
            valid = [r for r in all_rows if len(r) >= 5 and r[4] == r[4]]
            if valid:
                max_f1 = max(r[4] for r in valid)
                threshold = max_f1 * 0.9 if max_f1 > 0 else 0
                good_rows = [r for r in all_rows if len(r) >= 5 and r[4] == r[4] and r[4] >= threshold]

        print_result_start("Parameter-Tuning Ergebnis", "../tuning.html", "Zurück zum Parameter-Tuning")
        print("<h2>Parameter-Tuning Ergebnis</h2>")
        if all_rows:
            has_matrix = any(r[0] for r in all_rows)
            has_algo = any(r[3] for r in all_rows)
            print("<div style='overflow-x:auto;max-width:100%%;'>")
            print("<table class='val-table' style='font-size:0.9rem;'><thead><tr>")
            if has_matrix:
                print("<th>Matrix</th>")
            print("<th>Gap Open</th><th>Gap Extend</th>")
            if has_algo:
                print("<th>Algorithmus</th>")
            print("<th>Mittlere F1</th></tr></thead><tbody>")
            for r in all_rows:
                mat_name, go, ge, algo = r[0], r[1], r[2], r[3]
                f1 = r[4] if len(r) > 4 else float("nan")
                cls = " class='best'" if good_rows and r in good_rows else ""
                f1_str = "{:.2f}".format(f1) if f1 == f1 else "&ndash;"
                print("<tr{}>".format(cls))
                if has_matrix:
                    print("<td>%s</td>" % cgi.escape(mat_name or "&ndash;"))
                print("<td>{}</td><td>{}</td>".format(go, ge))
                if has_algo:
                    print("<td>%s</td>" % cgi.escape(algo or "&ndash;"))
                print("<td>{}</td></tr>".format(f1_str))
            print("</tbody></table>")
            print("</div>")
            if good_rows:
                max_f1 = max(r[4] for r in good_rows)
                min_f1 = min(r[4] for r in good_rows)
                print("<div class='good-range-box' style='margin-top:1rem;padding:1rem 1.25rem;max-width:520px;background:#e8f6f3;border-radius:10px;border:1px solid #c5e0db;'>")
                print("<p style='margin:0 0 0.4rem;font-size:0.95rem;'><strong>Guter Bereich</strong> (F1 &ge; %.2f)</p>" % (min_f1,))
                print("<p style='margin:0 0 0.5rem;font-size:0.82rem;color:#4a6560;'>Folgende Einstellungen eignen sich gut:</p>")
                print("<ul style='margin:0;padding-left:1.25rem;font-size:0.85rem;line-height:1.5;'>")
                for r in good_rows:
                    mat_name, go, ge, algo = r[0], r[1], r[2], r[3]
                    f1_val = r[4]
                    print("<li style='margin-bottom:0.25rem;'>%s, Gap Open %s, Gap Extend %s" % (cgi.escape(str(mat_name or "–")), go, ge))
                    if algo:
                        print(", %s" % cgi.escape(algo))
                    print(" &rarr; F1 = <strong>%.2f</strong></li>" % (f1_val,))
                print("</ul></div>")
        else:
            print("<p>Keine g&uuml;ltigen Tuning-Ergebnisse (evtl. Referenz passt nicht zu Pairs/Seqlib).</p>")
        print("<details class='tuning-raw-details' style='margin-top:1.5rem;'>")
        print("<summary style='cursor:pointer;font-weight:600;padding:0.5rem 0;'>Rohausgabe ein-/ausklappen</summary>")
        # Tab-getrennte Blöcke als Tabelle darstellen, damit Werte unter den Überschriften stehen
        for block in full_out:
            if not block or not isinstance(block, str):
                continue
            for part in block.split("\n\n"):
                part = part.strip()
                if not part:
                    continue
                lines = [l for l in part.splitlines() if l.strip()]
                if not lines:
                    continue
                first = lines[0]
                if "\t" in first and ("go" in first.lower() or "mean_f1" in first or "mean_sensitivity" in first):
                    headers = first.split("\t")
                    def _fmt_cell(s):
                        s = s.strip()
                        try:
                            f = float(s)
                            return "%.2f" % f
                        except ValueError:
                            return s
                    print("<div style='overflow-x:auto;max-width:100%%;margin-bottom:1rem;'>")
                    print("<table class='val-table raw-table' style='margin-bottom:0;font-size:0.85rem;'><thead><tr>")
                    for h in headers:
                        print("<th>%s</th>" % cgi.escape(h.strip()))
                    print("</tr></thead><tbody>")
                    for line in lines[1:]:
                        if "\t" in line:
                            cells = line.split("\t")
                            print("<tr>")
                            for i, c in enumerate(cells):
                                # Ab Spalte 4 (mean_*) Zahlen auf 2 Dezimalen
                                if i >= 3:
                                    print("<td>%s</td>" % cgi.escape(_fmt_cell(c)))
                                else:
                                    print("<td>%s</td>" % cgi.escape(c.strip()))
                            for _ in range(len(headers) - len(cells)):
                                print("<td></td>")
                            print("</tr>")
                    print("</tbody></table>")
                    print("</div>")
                else:
                    print("<pre class='raw' style='font-size:0.8rem;max-height:20em;overflow:auto;'>%s</pre>" % cgi.escape(part))
        print("</details>")
        print_result_end()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        try:
            print_result_start("Parameter-Tuning – Fehler", "../tuning.html", "Zurück zum Parameter-Tuning")
            print("<p class='error'>Ein unerwarteter Fehler ist aufgetreten.</p>")
            print("<pre class='raw'>")
            print(cgi.escape(traceback.format_exc()))
            print("</pre>")
            print_result_end()
        except Exception:
            print("Content-Type: text/html; charset=utf-8")
            print()
            print("<!DOCTYPE html><html><head><meta charset='utf-8'></head><body><h1>Fehler</h1><pre>")
            print(traceback.format_exc())
            print("</pre></body></html>")
