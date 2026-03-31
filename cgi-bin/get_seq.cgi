#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CGI: Sequenz(en) per PDB-, UniProt- oder SwissProt-ID abrufen.
Zuerst Datenbank, dann bei Bedarf online (RCSB für PDB, rest.uniprot.org für UniProt/SwissProt).
Ausgabe: FASTA (text/plain) oder Fehlerseite (text/html).
"""
import os
import sys
import cgi
import re

if hasattr(sys.stdout, "buffer"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

def main():
    form = cgi.FieldStorage()
    source = (form.getfirst("source") or "pdb").strip().lower()
    if source not in ("pdb", "uniprot", "swissprot"):
        source = "pdb"
    ids_raw = form.getfirst("id") or form.getfirst("ids") or ""
    ids = []
    for part in re.split(r"[\s,;]+", ids_raw):
        part = part.strip()
        if part:
            ids.append(part)
    if not ids:
        print("Content-Type: text/html; charset=utf-8")
        print()
        print("<!DOCTYPE html><html><head><meta charset='utf-8'><title>get_seq</title></head><body>")
        print("<p><a href='../get_seq.html'>&#8592; Zur&uuml;ck</a></p>")
        print("<p>Bitte mindestens eine ID angeben. Beispiel: <code>?source=pdb&amp;id=1bgxt</code> oder <code>?source=uniprot&amp;id=P12345</code></p>")
        print("</body></html>")
        return

    try:
        from alignment_db_sequence import resolve_sequence_id
    except ImportError:
        print("Content-Type: text/plain; charset=utf-8")
        print()
        print("Fehler: alignment_db_sequence nicht verfuegbar.")
        return

    results = []
    for sid in ids:
        res = resolve_sequence_id(source, sid, try_external=True)
        if res and res.get("seq"):
            header = res.get("header") or sid
            results.append((header, res["seq"]))
        else:
            results.append((None, None))

    if all(r[1] for r in results):
        print("Content-Type: text/plain; charset=utf-8")
        print()
        for header, seq in results:
            print(">" + (header or "sequence"))
            print(seq)
    else:
        print("Content-Type: text/html; charset=utf-8")
        print()
        print("<!DOCTYPE html><html><head><meta charset='utf-8'><title>get_seq – Fehler</title></head><body>")
        print("<p><a href='../get_seq.html'>&#8592; Zur&uuml;ck</a></p>")
        failed = [ids[i] for i in range(len(ids)) if not results[i][1]]
        print("<p>Sequenz(en) nicht gefunden f&uuml;r: " + ", ".join(failed) + ".</p>")
        print("<p>PDB: zuerst Datenbank, sonst RCSB. UniProt/SwissProt: rest.uniprot.org. Bitte IDs pr&uuml;fen.</p>")
        print("</body></html>")

if __name__ == "__main__":
    main()
