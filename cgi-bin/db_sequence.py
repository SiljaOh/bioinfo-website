# -*- coding: utf-8 -*-
"""
Sequence-Lookup: zuerst in der DB (source_entry -> sequence), optional extern (PDB/SwissProt).
ER: source_entry (source, source_key) -> sequence_id -> sequence (seq, accession, ...)
    orf (source, source_key, seq) als Alternative.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db_config import get_connection

def get_sequence_by_id(source, source_key):
    """
    Sucht eine Sequenz anhand von source (z.B. 'PDB', 'SwissProt') und source_key (z.B. PDB-ID).
    Returns: (sequence_id, seq_string, header) oder (None, None, None) wenn nicht gefunden.
    """
    conn = get_connection()
    if not conn:
        return None, None, None
    try:
        with conn.cursor() as cur:
            # source_entry -> sequence
            cur.execute(
                "SELECT s.sequence_id, s.seq, s.description FROM sequence s "
                "JOIN source_entry e ON e.sequence_id = s.sequence_id "
                "WHERE e.source = %s AND e.source_key = %s LIMIT 1",
                (str(source).strip(), str(source_key).strip())
            )
            row = cur.fetchone()
            if row:
                return row["sequence_id"], (row["seq"] or "").strip(), (row["description"] or "")[:200]
            # Fallback: orf-Tabelle (source, source_key, seq, header)
            cur.execute(
                "SELECT orf_id, seq, header FROM orf WHERE source = %s AND source_key = %s LIMIT 1",
                (str(source).strip(), str(source_key).strip())
            )
            row = cur.fetchone()
            if row:
                return row["orf_id"], (row["seq"] or "").strip(), (row["header"] or "")[:200]
    except Exception:
        pass
    finally:
        conn.close()
    return None, None, None


def fetch_swissprot_sequence(accession):
    """
    Holt eine Sequenz von UniProt/SwissProt (REST API).
    accession: UniProt-ID (z.B. P12345, A0A024R1R8).
    Returns: (seq_string, header) oder (None, None).
    Benoetigt ausgehenden HTTPS-Zugriff auf rest.uniprot.org (kein API-Key).
    """
    import urllib.request
    import re
    acc = str(accession).strip()
    if not acc:
        return None, None
    # Sonderzeichen entfernen, typisch alphanumerisch + Unterstriche
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
    """
    Versucht, eine Sequenz von PDB zu holen (z.B. per REST-API).
    Returns: (seq_string, header) oder (None, None).
    """
    import urllib.request
    import re
    pdb_id = str(pdb_id).strip().upper()[:4]
    if len(pdb_id) < 4:
        return None, None
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
        # Fallback: CIF/FASTA von RCSB
        url2 = "https://files.rcsb.org/header/" + pdb_id + ".pdb"
        with urllib.request.urlopen(url2, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        seq = "".join(m.group(1).replace(" ", "") for m in re.finditer(r"(?m)^SEQRES.*\s([A-Z\s]+)\s*$", raw) if m)
        if seq:
            return seq, "PDB:" + pdb_id
    except Exception:
        pass
    return None, None


def resolve_sequence_id(source, source_key, try_external=True):
    """
    Kombinierter Lookup: zuerst DB, dann bei try_external PDB (wenn source PDB) oder nur DB.
    Returns: dict mit seq, header, source_used ('db'|'pdb'|None), internal_id.
    """
    internal_id, seq, header = get_sequence_by_id(source, source_key)
    if seq:
        return {"seq": seq, "header": header or source_key, "source_used": "db", "internal_id": internal_id}
    if try_external and source_key:
        src_upper = (source or "").strip().upper()
        if src_upper in ("PDB", ""):
            pdb_seq, pdb_header = fetch_pdb_sequence(source_key)
            if pdb_seq:
                return {"seq": pdb_seq, "header": pdb_header or source_key, "source_used": "pdb", "internal_id": None}
        if src_upper in ("SWISSPROT", "UNIPROT", "UNIPROTKB"):
            sp_seq, sp_header = fetch_swissprot_sequence(source_key)
            if sp_seq:
                return {"seq": sp_seq, "header": sp_header or source_key, "source_used": "swissprot", "internal_id": None}
    return {"seq": None, "header": None, "source_used": None, "internal_id": None}
