# -*- coding: utf-8 -*-
"""
Alignment-spezifischer Sequence-Lookup.
Wie db_sequence.py, aber mit robusterer PDB-ID-Normalisierung
fuer Eingaben wie 1bgxT, 1bgx_A oder 1bgxA00.
"""
import sys
import os
import re


def get_connection():
    try:
        import pymysql
    except ImportError:
        return None
    password = os.environ.get("ALIGNMENT_DB_PASSWORD", "").strip()
    if not password:
        try:
            with open(os.path.expanduser("~/.dbpass"), "r", encoding="utf-8") as f:
                password = f.read().strip()
        except Exception:
            password = ""
    if not password:
        return None
    try:
        return pymysql.connect(
            host=os.environ.get("ALIGNMENT_DB_HOST", "mysql2-ext.bio.ifi.lmu.de"),
            port=int(os.environ.get("ALIGNMENT_DB_PORT", "3306")),
            user=os.environ.get("ALIGNMENT_DB_USER", "bioprakt17"),
            password=password,
            database=os.environ.get("ALIGNMENT_DB_NAME", "bioprakt17"),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
    except Exception:
        return None


def get_sequence_by_id(source, source_key):
    conn = get_connection()
    if not conn:
        return None, None, None
    source = str(source or "").strip()
    source_key = str(source_key or "").strip()
    if not source_key:
        return None, None, None
    source_candidates = []
    for cand in [source, source.lower(), source.upper(), source.capitalize()]:
        if cand and cand not in source_candidates:
            source_candidates.append(cand)
    key_candidates = []
    for cand in [source_key, source_key.lower(), source_key.upper()]:
        if cand and cand not in key_candidates:
            key_candidates.append(cand)
    if source.lower() == "pdb":
        m = re.match(r"^([0-9][A-Za-z0-9]{3})", source_key)
        pdb4 = (m.group(1) if m else source_key[:4]).strip()
        for cand in [pdb4, pdb4.lower(), pdb4.upper()]:
            if cand and cand not in key_candidates:
                key_candidates.append(cand)
    try:
        with conn.cursor() as cur:
            for src in source_candidates:
                for key in key_candidates:
                    cur.execute(
                        "SELECT s.sequence_id, s.seq, s.description FROM sequence s "
                        "JOIN source_entry e ON e.sequence_id = s.sequence_id "
                        "WHERE e.source = %s AND e.source_key = %s LIMIT 1",
                        (src, key)
                    )
                    row = cur.fetchone()
                    if row:
                        return row["sequence_id"], (row["seq"] or "").strip(), (row["description"] or "")[:200]
                    cur.execute(
                        "SELECT orf_id, seq, header FROM orf WHERE source = %s AND source_key = %s LIMIT 1",
                        (src, key)
                    )
                    row = cur.fetchone()
                    if row:
                        return row["orf_id"], (row["seq"] or "").strip(), (row["header"] or "")[:200]
    except Exception:
        pass
    finally:
        conn.close()
    return None, None, None


def get_secondary_structure_by_sequence_id(sequence_id, method="HOMSTRAD_DSSP_HEC"):
    conn = get_connection()
    if not conn or not sequence_id:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ss_seq FROM sequence_secondary_structure "
                "WHERE sequence_id = %s AND method = %s LIMIT 1",
                (sequence_id, method)
            )
            row = cur.fetchone()
            if row and row.get("ss_seq"):
                return str(row["ss_seq"]).strip()
    except Exception:
        pass
    finally:
        conn.close()
    return None


def fetch_swissprot_sequence(accession):
    import urllib.request
    acc = str(accession).strip()
    if not acc:
        return None, None
    acc = re.sub(r"[^A-Za-z0-9_\-]", "", acc)[:20]
    if not acc:
        return None, None
    try:
        url = "https://rest.uniprot.org/uniprotkb/" + acc + ".fasta"
        req = urllib.request.Request(url, headers={"Accept": "text/plain"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        if not lines:
            return None, None
        header = ""
        seq_parts = []
        for line in lines:
            if line.startswith(">"):
                header = line[1:].strip()[:300]
            else:
                seq_parts.append(line.replace(" ", ""))
        seq = "".join(seq_parts)
        if not seq:
            return None, None
        return seq, header or "UniProt:" + acc
    except Exception:
        pass
    return None, None


def fetch_pdb_sequence(pdb_id):
    import urllib.request
    pdb_id = str(pdb_id).strip().upper()[:4]
    if len(pdb_id) < 4:
        return None, None
    # 1) RCSB REST API (UniProt consensus sequence)
    try:
        url = "https://data.rcsb.org/rest/v1/core/uniprot_consensus/" + pdb_id
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode("utf-8")
        import json
        j = json.loads(data)
        seq = (j.get("sequence") or {}).get("sequence")
        if seq:
            return seq, "PDB:" + pdb_id
    except Exception:
        pass
    # 2) Vollstaendige PDB-Datei von RCSB (SEQRES = 3-Buchstaben-Codes) – z. B. 1tim, 1crn
    _3to1 = {
        "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q", "GLU": "E",
        "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F",
        "PRO": "P", "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V", "UNK": "X",
    }
    try:
        url_full = "https://files.rcsb.org/download/" + pdb_id + ".pdb"
        req = urllib.request.Request(url_full, headers={"Accept": "text/plain"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        one_letter = []
        for m in re.finditer(r"(?m)^SEQRES\s+\d+\s+[A-Z]\s+\d+\s+([A-Z\s]+)\s*$", raw):
            three_letter = m.group(1).split()
            for t in three_letter:
                one_letter.append(_3to1.get(t, "X"))
        seq = "".join(one_letter)
        if seq:
            return seq, "PDB:" + pdb_id
    except Exception:
        pass
    return None, None


def _looks_like_uniprot_accession(key):
    """Typische UniProt-Accessions: P12345, Q9Y6K9, O00123 usw."""
    k = str(key).strip().upper()
    if len(k) < 6 or len(k) > 10:
        return False
    if k[0] in ("P", "Q", "O", "A", "B") and k[1:2].isdigit():
        return all(c.isalnum() or c in "-_" for c in k)
    return False


def resolve_sequence_id(source, source_key, try_external=True):
    internal_id, seq, header = get_sequence_by_id(source, source_key)
    if seq:
        ss_seq = get_secondary_structure_by_sequence_id(internal_id)
        return {"seq": seq, "header": header or source_key, "source_used": "db", "internal_id": internal_id, "ss_seq": ss_seq}
    if try_external and source_key:
        source_key = str(source_key).strip()
        src_upper = (source or "").strip().upper()
        # UniProt/SwissProt: explizit gewaehlt oder ID sieht wie Accession aus (z. B. P00439)
        if src_upper in ("SWISSPROT", "UNIPROT", "UNIPROTKB") or _looks_like_uniprot_accession(source_key):
            sp_seq, sp_header = fetch_swissprot_sequence(source_key)
            if sp_seq:
                return {"seq": sp_seq, "header": sp_header or source_key, "source_used": "swissprot", "internal_id": None, "ss_seq": None}
        # PDB: explizit gewaehlt oder ID sieht wie PDB aus (4 Zeichen)
        if src_upper in ("PDB", ""):
            pdb_key = source_key
            m = re.match(r"^([0-9][A-Za-z0-9]{3})", pdb_key)
            pdb_lookup = m.group(1) if m else pdb_key[:4]
            if len(pdb_lookup) == 4:
                pdb_seq, pdb_header = fetch_pdb_sequence(pdb_lookup)
                if pdb_seq:
                    return {"seq": pdb_seq, "header": pdb_header or source_key, "source_used": "pdb", "internal_id": None, "ss_seq": None}
    return {"seq": None, "header": None, "source_used": None, "internal_id": None, "ss_seq": None}
