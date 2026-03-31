#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pipeline: Alignment ausfuehren -> Referenz aus HOMSTRAD oder --ref holen ->
Validation ausfuehren -> Plots/Report ausgeben.

Verwendung (auf dem Bioclient, HOMSTRAD unter /mnt/extstud/...):
  python3 src/alignment_validate_pipeline.py \\
    --pairs web/test/example.pairs --seqlib web/test/example.seqlib -m Data/dayhoff.mat \\
    --homstrad-dir /mnt/extstud/praktikum/bioprakt/Data/HOMSTRAD_DB/2019_Feb \\
    --alignment-jar alignment.jar --validate-jar validateAli.jar \\
    -o report

Mit vorgegebener Referenz-Datei (ohne HOMSTRAD):
  python3 src/alignment_validate_pipeline.py \\
    --pairs pairs.txt --seqlib seqlib.txt -m dayhoff.mat --ref referenz.ali -o report
"""
from __future__ import print_function

import argparse
import json
import os
import re
import subprocess
import sys


def _norm_id(s):
    """ID fuer Abgleich normalisieren (Kleinbuchstaben, Unterstriche weg)."""
    if not s:
        return ""
    return re.sub(r"[^a-z0-9]", "", s.strip().lower())


def read_pairs(path):
    """Liest Pairs-Datei: Zeilen 'id1 id2', liefert Liste von (id1, id2)."""
    pairs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                pairs.append((parts[0].strip(), parts[1].strip()))
    return pairs


def parse_aln_file(filepath):
    """
    Parst eine Alignment-Datei (FASTA-aehnlich oder id: seq).
    Liefert Liste von (id, aligned_sequence).
    """
    entries = []
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(">"):
            # FASTA: >id oder >id description
            fid = line[1:].strip().split()[0] if line[1:].strip() else ""
            seq_parts = []
            i += 1
            while i < len(lines) and not lines[i].startswith(">"):
                s = lines[i].strip()
                if s and not s.startswith("#"):
                    seq_parts.append(s.replace(" ", ""))
                i += 1
            if fid:
                entries.append((fid, "".join(seq_parts)))
            continue
        if ":" in line:
            # id: sequence
            idx = line.index(":")
            fid = line[:idx].strip()
            seq = line[idx + 1 :].strip().replace(" ", "")
            if fid and seq:
                entries.append((fid, seq))
        elif line.strip():
            # id  sequence (Leerzeichen/Tab)
            parts = line.split(None, 1)
            if len(parts) >= 2:
                fid, seq = parts[0], parts[1].replace(" ", "")
                if fid and seq:
                    entries.append((fid, seq))
        i += 1
    return entries


def build_ref_from_homstrad(homstrad_dir, pairs_list):
    """
    Durchsucht homstrad_dir rekursiv nach .aln/.pir/.fasta/.afa;
    baut ref_blocks[(id1, id2)] = ("id1: seq1", "id2: seq2").
    Exakter Abgleich: Keys sind (id1, id2) wie in der HOMSTRAD-Datei; beim Merge
    wird (id1, id2) und (id2, id1) probiert. Zusaetzlich: normalisierte IDs
    (Kleinbuchstaben, Sonderzeichen weg) fuer Pairs-IDs zum Lookup.
    """
    ref_blocks = {}
    pair_ids = set(pairs_list)
    pair_norm_to_orig = {}
    for a, b in pairs_list:
        nk = (_norm_id(a), _norm_id(b))
        if nk not in pair_norm_to_orig:
            pair_norm_to_orig[nk] = (a, b)

    for root, _dirs, files in os.walk(homstrad_dir):
        for f in files:
            if not (f.endswith(".aln") or f.endswith(".pir") or f.endswith(".fasta") or f.endswith(".afa")):
                continue
            path = os.path.join(root, f)
            try:
                entries = parse_aln_file(path)
            except Exception:
                continue
            if len(entries) < 2:
                continue
            for i in range(len(entries)):
                for j in range(i + 1, len(entries)):
                    id1, seq1 = entries[i]
                    id2, seq2 = entries[j]
                    line1 = "{}: {}".format(id1, seq1)
                    line2 = "{}: {}".format(id2, seq2)
                    ref_blocks[(id1, id2)] = (line1, line2)
                    ref_blocks[(id2, id1)] = (line2, line1)
                    n1, n2 = _norm_id(id1), _norm_id(id2)
                    nk = (n1, n2) if n1 <= n2 else (n2, n1)
                    if nk in pair_norm_to_orig:
                        orig = pair_norm_to_orig[nk]
                        if orig not in ref_blocks and (orig[1], orig[0]) not in ref_blocks:
                            # Referenzzeilen mit unseren IDs (wie im Alignment), Reihenfolge passend zu orig
                            if _norm_id(id1) == _norm_id(orig[0]):
                                ref_blocks[orig] = ("{}: {}".format(orig[0], seq1), "{}: {}".format(orig[1], seq2))
                            else:
                                ref_blocks[orig] = ("{}: {}".format(orig[0], seq2), "{}: {}".format(orig[1], seq1))
    return ref_blocks


def _id_from_line(ln):
    """Extrahiert ID aus Zeile 'id: seq' oder 'id  seq'."""
    if ":" in ln:
        return ln[: ln.index(":")].strip()
    parts = ln.split(None, 1)
    return parts[0].strip() if parts else ""


def read_ref_blocks(path):
    """Liest Referenz-Datei (ValidateAli-Format); liefert ref_blocks[(id1,id2)] = (line3, line4). Key aus Inhalt (id vor ':' in Zeile 1 und 2)."""
    blocks = {}
    with open(path, "r", encoding="utf-8") as f:
        header = None
        line1 = line2 = line3 = line4 = None
        for raw in f:
            line = raw.rstrip()
            if line.startswith(">"):
                if header is not None and line1 is not None and line2 is not None and line3 is not None and line4 is not None:
                    id1, id2 = _id_from_line(line1), _id_from_line(line2)
                    if id1 and id2:
                        blocks[(id1, id2)] = (line3, line4)
                header = line
                line1 = line2 = line3 = line4 = None
                continue
            if line1 is None:
                line1 = line
            elif line2 is None:
                line2 = line
            elif line3 is None:
                line3 = line
            elif line4 is None:
                line4 = line
        if line1 and line2 and line3 and line4:
            id1, id2 = _id_from_line(line1), _id_from_line(line2)
            if id1 and id2:
                blocks[(id1, id2)] = (line3, line4)
    return blocks


def run_align(jar, pairs_path, seqlib_path, matrix_path, go, ge, mode="global", cwd=None):
    """Fuehrt alignment.jar aus, liefert stdout (ali-Format)."""
    cmd = [
        "java", "-jar", jar,
        "--pairs", str(pairs_path), "--seqlib", str(seqlib_path), "-m", str(matrix_path),
        "--go", str(go), "--ge", str(ge), "--mode", mode, "--format", "ali"
    ]
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        return None, r.stderr or r.stdout
    return r.stdout, None


def merge_with_ref(ali_stdout, ref_blocks):
    """Kombiniert Alignment-Ausgabe (Header + Z1, Z2) mit Referenz (Z3, Z4) zu ValidateAli-Input."""
    out = []
    block = []
    for raw in ali_stdout.splitlines():
        line = raw.rstrip()
        if line.startswith(">"):
            if block and len(block) >= 3:
                parts = block[0][1:].strip().split()
                if len(parts) >= 2:
                    key = (parts[0], parts[1])
                    if key in ref_blocks:
                        ref3, ref4 = ref_blocks[key]
                        out.append(block[0])
                        out.append(block[1])
                        out.append(block[2])
                        out.append(ref3)
                        out.append(ref4)
            block = [line]
        elif block:
            if len(block) == 1:
                block.append(line)
            elif len(block) == 2:
                block.append(line)
    if block and len(block) >= 3:
        parts = block[0][1:].strip().split()
        if len(parts) >= 2 and (parts[0], parts[1]) in ref_blocks:
            ref3, ref4 = ref_blocks[(parts[0], parts[1])]
            out.append(block[0])
            out.append(block[1])
            out.append(block[2])
            out.append(ref3)
            out.append(ref4)
    return "\n".join(out) + "\n" if out else ""


def run_validate(jar, input_content, cwd=None):
    """Fuehrt validateAli.jar aus; liefert stdout."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ali", delete=False, encoding="utf-8") as f:
        f.write(input_content)
        f.flush()
        try:
            r = subprocess.run(["java", "-jar", jar, "-f", f.name], cwd=cwd, capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                return None, r.stderr or r.stdout
            return r.stdout, None
        finally:
            os.unlink(f.name)


def parse_validation_to_dict(validate_stdout):
    """Parst ValidateAli-Ausgabe in dasselbe Dict wie parse_validation_to_json.py."""
    blocks = []
    for line in validate_stdout.splitlines():
        line = line.rstrip()
        if line.startswith(">"):
            parts = line[1:].strip().split()
            if len(parts) >= 5:
                try:
                    sens = float(parts[-5])
                    spec = float(parts[-4])
                    cov = float(parts[-3])
                    inv_mse = float(parts[-2])
                    mse = float(parts[-1])
                    header = " ".join(parts[:-5]) if len(parts) > 5 else parts[0]
                    label = header.split()[0][:12] if header else "Block"
                    blocks.append({
                        "header": header, "label": label,
                        "sensitivity": sens, "specificity": spec, "coverage": cov,
                        "mse": mse, "inv_mse": inv_mse,
                    })
                except (ValueError, IndexError):
                    pass
    sens = [b["sensitivity"] for b in blocks]
    spec = [b["specificity"] for b in blocks]
    cov = [b["coverage"] for b in blocks]
    mse = [b["mse"] for b in blocks]
    inv_mse = [b["inv_mse"] for b in blocks]
    labels = [b["label"] for b in blocks]
    return {
        "source": "validation.out",
        "n_blocks": len(blocks),
        "blocks": blocks,
        "sens": sens, "spec": spec, "cov": cov, "mse": mse, "inv_mse": inv_mse,
        "labels": labels,
    }


def main():
    ap = argparse.ArgumentParser(
        description="Pipeline: Alignment -> HOMSTRAD/Ref -> Validation -> Report/Plots"
    )
    ap.add_argument("--pairs", required=True, help="Pairs-Datei")
    ap.add_argument("--seqlib", required=True, help="Seqlib-Datei")
    ap.add_argument("-m", "--matrix", required=True, dest="matrix", help="Substitutionsmatrix")
    ap.add_argument("--ref", default=None, help="Referenz-Datei (ValidateAli-Format, 5 Zeilen/Block). Alternativ --homstrad-dir.")
    ap.add_argument("--homstrad-dir", default=None, help="HOMSTRAD-Verzeichnis (z.B. /mnt/extstud/praktikum/bioprakt/Data/HOMSTRAD_DB/2019_Feb)")
    ap.add_argument("-o", "--output-dir", default="report", help="Ausgabeordner (validation.out, validation_data.json, report.html)")
    ap.add_argument("--go", type=int, default=-12, help="Gap Open")
    ap.add_argument("--ge", type=int, default=-1, help="Gap Extend")
    ap.add_argument("--mode", default="global", choices=["global", "local", "freeshift"])
    ap.add_argument("--alignment-jar", default="alignment.jar", help="Pfad zu alignment.jar")
    ap.add_argument("--validate-jar", default="validateAli.jar", help="Pfad zu validateAli.jar")
    args = ap.parse_args()

    if not args.ref and not args.homstrad_dir:
        print("Bitte --ref ODER --homstrad-dir angeben.", file=sys.stderr)
        sys.exit(1)
    if args.ref and args.homstrad_dir:
        print("Nur eines von --ref und --homstrad-dir angeben.", file=sys.stderr)
        sys.exit(1)

    base = os.path.dirname(os.path.abspath(args.alignment_jar)) if os.path.isfile(args.alignment_jar) else "."
    align_jar = args.alignment_jar if os.path.isabs(args.alignment_jar) or os.path.isfile(args.alignment_jar) else os.path.join(base, "alignment.jar")
    val_jar = args.validate_jar if os.path.isabs(args.validate_jar) or os.path.isfile(args.validate_jar) else os.path.join(base, "validateAli.jar")

    pairs_list = read_pairs(args.pairs)
    if not pairs_list:
        print("Keine Paare in --pairs gefunden.", file=sys.stderr)
        sys.exit(1)

    if args.ref:
        if not os.path.isfile(args.ref):
            print("Referenz-Datei nicht gefunden:", args.ref, file=sys.stderr)
            sys.exit(1)
        ref_blocks = read_ref_blocks(args.ref)
        print("Referenz aus Datei gelesen: {} Bloecke.".format(len(ref_blocks)))
    else:
        if not os.path.isdir(args.homstrad_dir):
            print("HOMSTRAD-Verzeichnis nicht gefunden:", args.homstrad_dir, file=sys.stderr)
            sys.exit(1)
        ref_blocks = build_ref_from_homstrad(args.homstrad_dir, pairs_list)
        print("HOMSTRAD durchsucht: {} Referenz-Paare gefunden.".format(len(ref_blocks)))

    if not ref_blocks:
        print("Keine Referenz-Blöcke verfuegbar. Pruefe Pairs-IDs vs. HOMSTRAD-Dateien.", file=sys.stderr)
        sys.exit(1)

    ali_out, err = run_align(align_jar, args.pairs, args.seqlib, args.matrix, args.go, args.ge, args.mode, cwd=base)
    if err:
        print("Alignment fehlgeschlagen:", err[:500], file=sys.stderr)
        sys.exit(1)

    merged = merge_with_ref(ali_out, ref_blocks)
    if not merged.strip():
        print("Kein ueberlappender Output (Alignment-IDs und Referenz-IDs passen nicht).", file=sys.stderr)
        sys.exit(1)

    val_out, err = run_validate(val_jar, merged, cwd=base)
    if err:
        print("Validation fehlgeschlagen:", err[:500], file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)
    out_ali = os.path.join(args.output_dir, "validation_input.ali")
    out_val = os.path.join(args.output_dir, "validation.out")
    out_json = os.path.join(args.output_dir, "validation_data.json")
    out_html = os.path.join(args.output_dir, "report.html")

    with open(out_ali, "w", encoding="utf-8") as f:
        f.write(merged)
    with open(out_val, "w", encoding="utf-8") as f:
        f.write(val_out)

    data = parse_validation_to_dict(val_out)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Report-HTML: validation_plots.html mit eingebettetem JSON (kein fetch noetig)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    plots_html_path = os.path.join(os.path.dirname(script_dir), "web", "validation_plots.html")
    json_str = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")
    if os.path.isfile(plots_html_path):
        with open(plots_html_path, "r", encoding="utf-8") as f:
            html = f.read()
        # Eingebettete Daten: Script-Tag mit JSON direkt nach <body> einfuegen
        embed = '<script id="pipeline-validation-data" type="application/json">' + json_str + '</script>\n  '
        if "<body>" in html:
            html = html.replace("<body>", "<body>\n  " + embed, 1)
        # Wenn #pipeline-validation-data vorhanden, davon laden; sonst fetch wie bisher
        load_inline = (
            "(function(){ var el = document.getElementById('pipeline-validation-data');"
            " if (el && el.textContent) { try { var d = JSON.parse(el.textContent);"
            " if (d.sens && d.sens.length) { sens = d.sens; spec = d.spec; cov = d.cov; mse = d.mse; inv = d.inv_mse || [];"
            " labels = d.labels || sens.map(function(_,i){ return 'B'+i; });"
            " var s = document.querySelector('.sub'); if (s) s.innerHTML = 'Pipeline-Report: <code>' + (d.source || 'validation.out') + '</code> (' + (d.n_blocks || sens.length) + ' Bl&ouml;cke).';"
            " drawCharts(); return; } } catch(e) {} }"
            " return fetch(\"test/validation_data.json\")"
        )
        html = html.replace("fetch(\"test/validation_data.json\")", load_inline, 1)
        with open(out_html, "w", encoding="utf-8") as f:
            f.write(html)
    else:
        with open(out_html, "w", encoding="utf-8") as f:
            f.write("<!DOCTYPE html><html><head><meta charset='utf-8'><title>Report</title></head><body><h1>Pipeline-Report</h1><pre>")
            f.write(val_out)
            f.write("</pre><p>validation_data.json und validation.out liegen in diesem Ordner. Fuer Plots: validation_data.json nach web/test/ kopieren und web/validation_plots.html oeffnen.</p></body></html>")

    print("Fertig. Ausgabe in {}:".format(args.output_dir))
    print("  - validation_input.ali  (Kandidat + Referenz)")
    print("  - validation.out        (ValidateAli-Rohausgabe)")
    print("  - validation_data.json  (fuer Plots)")
    print("  - report.html          (Report inkl. Plots; im Browser oeffnen)")
    print()
    print("Validation-Auszug (erste Zeilen):")
    for line in val_out.splitlines()[:15]:
        print(line)


if __name__ == "__main__":
    main()
