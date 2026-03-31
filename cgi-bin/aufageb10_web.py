#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cgi
import html
import os
import tempfile
import traceback

import layout_group17 as layout

# -------------------------
# Helpers: FASTA parser/writer (robust für Multi-line Sequenzen)
# -------------------------

def parse_fasta_text(text: str):
    """Return list of (header_without_>, sequence_as_single_string)."""
    records = []
    header = None
    buf = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if header is not None:
                records.append((header, "".join(buf)))
            header = line[1:].strip()
            buf = []
        else:
            buf.append(line.strip())
    if header is not None:
        records.append((header, "".join(buf)))
    return records

def format_fasta(records):
    """records: list[(header_without_>, seq)] -> FASTA string (1 Zeile pro Seq)"""
    out = []
    for h, s in records:
        out.append(">" + h)
        out.append(s)
    return "\n".join(out) + ("\n" if out else "")

# -------------------------
# genome2orf: deine Logik (nur in Funktion gepackt)
# -------------------------

def read_fasta_file(path):
    seqs = {}
    cur = None
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                cur = line[1:].split()[0]
                seqs[cur] = []
            else:
                if cur:
                    seqs[cur].append(line.upper())
    return {k: "".join(v) for k, v in seqs.items()}

def revcomp(s):
    comp = {"A":"T","T":"A","C":"G","G":"C","N":"N"}
    return "".join(comp.get(b, "N") for b in reversed(s.upper()))

def genome2orf_run(organism_path, features_path):
    """Return ORFs as FASTA text."""
    seqs = read_fasta_file(organism_path)
    single = next(iter(seqs.values())) if len(seqs) == 1 else None

    out_records = []

    with open(features_path) as f:
        # Header überspringen (wie in deinem Code)
        try:
            next(f)
        except StopIteration:
            return ""

        for line in f:
            if not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 17 or parts[0] != "CDS":
                continue

            locus = parts[16].strip()
            if not locus:
                continue

            try:
                start, end = int(parts[7]), int(parts[8])
            except ValueError:
                continue

            lo, hi = sorted((start, end))
            strand = parts[9].strip()
            acc = parts[6].strip()

            seq = seqs.get(acc)

            if seq is None and acc:
                base = acc.split(".", 1)[0]
                seq = seqs.get(base)
                if seq is None:
                    for k in seqs:
                        if k.startswith(acc + "."):
                            seq = seqs[k]
                            break

            if seq is None:
                seq = single
            if seq is None or lo < 1 or hi > len(seq):
                continue

            gene = seq[lo-1:hi]
            if strand == "-":
                gene = revcomp(gene)

            out_records.append((locus, gene))

    return format_fasta(out_records)

# -------------------------
# dna2mrna: deine Logik als Funktion (FASTA text -> FASTA text)
# -------------------------

def dna2mrna_run(fasta_text):
    recs = parse_fasta_text(fasta_text)
    out = []
    for h, s in recs:
        # robust: uppercase, T->U
        rna = s.upper().replace("T", "U")
        out.append((h, rna))
    return format_fasta(out)

# -------------------------
# mrna2aa: deine Logik als Funktion (FASTA text -> FASTA text)
# - stop codon bricht ab
# - frameshift oder nicht-standard basen: skip
# - Reihenfolge bleibt erhalten
# -------------------------

CODON_TABLE = {
    "UUU": "F", "UUC": "F",
    "UUA": "L", "UUG": "L",
    "CUU": "L", "CUC": "L", "CUA": "L", "CUG": "L",
    "AUU": "I", "AUC": "I", "AUA": "I",
    "AUG": "M",
    "GUU": "V", "GUC": "V", "GUA": "V", "GUG": "V",
    "UCU": "S", "UCC": "S", "UCA": "S", "UCG": "S",
    "AGU": "S", "AGC": "S",
    "CCU": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACU": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCU": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "UAU": "Y", "UAC": "Y",
    "CAU": "H", "CAC": "H",
    "CAA": "Q", "CAG": "Q",
    "AAU": "N", "AAC": "N",
    "AAA": "K", "AAG": "K",
    "GAU": "D", "GAC": "D",
    "GAA": "E", "GAG": "E",
    "UGU": "C", "UGC": "C",
    "UGG": "W",
    "CGU": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGA": "R", "AGG": "R",
    "GGU": "G", "GGC": "G", "GGA": "G", "GGG": "G",
    "UAA": "STOP",
    "UAG": "STOP",
    "UGA": "STOP"
}

def translate_one(mrna):
    mrna = mrna.upper()
    if len(mrna) % 3 != 0:
        return None
    allowed = set("ACGU")
    if any(b not in allowed for b in mrna):
        return None

    protein = []
    for i in range(0, len(mrna), 3):
        codon = mrna[i:i+3]
        aa = CODON_TABLE.get(codon)
        if aa is None:
            return None
        if aa == "STOP":
            break
        protein.append(aa)
    return "".join(protein)

def mrna2aa_run(fasta_text):
    recs = parse_fasta_text(fasta_text)
    out = []
    for h, s in recs:
        prot = translate_one(s)
        if prot is not None:
            out.append((h, prot))
    return format_fasta(out)

# -------------------------
# CGI: Formular + Upload + Pipeline
# -------------------------

form = cgi.FieldStorage()

def page(title, body):
    layout.print_page_start(title)
    layout.print_main_start()
    print(body)
    layout.print_main_end()
    layout.print_page_end()

# 1) Erstaufruf: Formular anzeigen
if "organism" not in form or "features" not in form:
    page(
        "Aufgabe 10 – Workflow",
        """
        <h1>Aufgabe 10 – Genom → ORF → mRNA → Protein</h1>
        <p class="hint">Bitte lade die Organismus-FASTA und die Feature-Table (TSV) hoch.</p>

        <form method="post" enctype="multipart/form-data">
          <label><b>Organism (FASTA)</b></label><br>
          <input type="file" name="organism" required><br>

          <label><b>Features (Feature-Table TSV)</b></label><br>
          <input type="file" name="features" required><br>

          <button type="submit">Workflow ausführen</button>
        </form>
        """
    )
    raise SystemExit

org_item = form["organism"]
feat_item = form["features"]

if not getattr(org_item, "file", None) or not getattr(feat_item, "file", None):
    page("Fehler", "<h1>Fehler</h1><p>Uploads wurden nicht korrekt übertragen.</p>")
    raise SystemExit

# Uploads temporär speichern (damit genome2orf wie gewohnt mit Pfaden arbeiten kann)
org_tmp = tempfile.NamedTemporaryFile(delete=False)
feat_tmp = tempfile.NamedTemporaryFile(delete=False)

try:
    org_tmp.write(org_item.file.read())
    org_tmp.close()
    feat_tmp.write(feat_item.file.read())
    feat_tmp.close()

    # Pipeline
    orf_fasta = genome2orf_run(org_tmp.name, feat_tmp.name)
    mrna_fasta = dna2mrna_run(orf_fasta)
    aa_fasta = mrna2aa_run(mrna_fasta)

    page(
        "Aufgabe 10 – Ergebnis (Proteine)",
        f"""
        <h1>Aufgabe 10 – Ergebnis</h1>
        <p class="back"><a href="../index.html">← Zur Startseite</a></p>

        <h3>Protein-FASTA (Output von mrna2aa)</h3>
        <pre>{html.escape(aa_fasta) if aa_fasta else "(keine Proteine erzeugt)"}</pre>

        <details>
          <summary>Zwischenergebnisse anzeigen</summary>
          <h4>ORFs (genome2orf)</h4>
          <pre>{html.escape(orf_fasta) if orf_fasta else "(keine ORFs)"}</pre>
          <h4>mRNA (dna2mrna)</h4>
          <pre>{html.escape(mrna_fasta) if mrna_fasta else "(keine mRNA)"}</pre>
        </details>
        """
    )

except Exception:
    page("Fehler (Server)", f"<h1>Fehler</h1><pre>{html.escape(traceback.format_exc())}</pre>")

finally:
    try:
        os.unlink(org_tmp.name)
    except Exception:
        pass
    try:
        os.unlink(feat_tmp.name)
    except Exception:
        pass
