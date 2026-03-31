# -*- coding: utf-8 -*-
"""HOMSTRAD-Referenz: parse_aln_file, build_ref_from_homstrad, build_ref_from_db. Wird von validate.cgi genutzt."""
import os
import re


def _norm_id(s):
    if not s:
        return ""
    return re.sub(r"[^a-z0-9]", "", s.strip().lower())


def _pdb_id_match(candidate_id, homstrad_id):
    """True if candidate (e.g. 1bgxt) matches HOMSTRAD id (e.g. 1bgxA00). PDB: first 4 chars match."""
    nc = _norm_id(candidate_id)
    nh = _norm_id(homstrad_id)
    if not nc or not nh:
        return nc == nh
    if len(nc) >= 4 and len(nh) >= 4:
        return nc[:4] == nh[:4]
    return nc == nh


def parse_aln_file(filepath):
    """Parst .aln/.fasta: Liste von (id, aligned_sequence)."""
    entries = []
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(">"):
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
            idx = line.index(":")
            fid = line[:idx].strip()
            seq = line[idx + 1:].strip().replace(" ", "")
            if fid and seq:
                entries.append((fid, seq))
        elif line.strip():
            parts = line.split(None, 1)
            if len(parts) >= 2:
                fid, seq = parts[0], parts[1].replace(" ", "")
                if fid and seq:
                    entries.append((fid, seq))
        i += 1
    return entries


def build_ref_from_homstrad(homstrad_dir, pairs_list):
    """ref_blocks[(id1,id2)] = (line1, line2) aus HOMSTRAD-Verzeichnis."""
    ref_blocks = {}
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
                            if _norm_id(id1) == _norm_id(orig[0]):
                                ref_blocks[orig] = ("{}: {}".format(orig[0], seq1), "{}: {}".format(orig[1], seq2))
                            else:
                                ref_blocks[orig] = ("{}: {}".format(orig[0], seq2), "{}: {}".format(orig[1], seq1))
                    # Match by PDB base (first 4 chars): e.g. 1bgxt / 2pgd to 1bgxA00 / 2pgdA00
                    for (a, b) in pairs_list:
                        if (a, b) in ref_blocks or (b, a) in ref_blocks:
                            continue
                        if _pdb_id_match(a, id1) and _pdb_id_match(b, id2):
                            ref_blocks[(a, b)] = ("{}: {}".format(a, seq1), "{}: {}".format(b, seq2))
                        elif _pdb_id_match(a, id2) and _pdb_id_match(b, id1):
                            ref_blocks[(a, b)] = ("{}: {}".format(a, seq2), "{}: {}".format(b, seq1))
    return ref_blocks


def _get_db_connection():
    """DB-Verbindung für HOMSTRAD-Referenz aus der Datenbank (Passwort aus ALIGNMENT_DB_PASSWORD oder ~/.dbpass)."""
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
            return None
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


def build_ref_from_db(pairs_list):
    """
    Lädt Referenz-Blöcke aus der Datenbank (alignment + alignment_row + source_entry).
    Berücksichtigt sowohl Import mit source='homstrad', type='homstrad' als auch
    bestehende Daten mit source='pdb', type='msa', damit Referenzen in beiden Fällen gefunden werden.
    Rückgabe: ref_blocks[(id1, id2)] = ("id1: seq1", "id2: seq2"). Abgleich über erste 4 Zeichen (PDB).
    """
    conn = _get_db_connection()
    if not conn:
        return None
    ref_blocks = {}
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT a.alignment_id, ar.sequence_id, ar.aligned_seq, LOWER(se.source_key) AS source_key
                FROM alignment a
                JOIN alignment_row ar ON ar.alignment_id = a.alignment_id
                JOIN source_entry se ON se.sequence_id = ar.sequence_id
                    AND LOWER(se.source) IN ('homstrad', 'pdb')
                WHERE LOWER(a.type) IN ('homstrad', 'msa')
            """)
            rows = cur.fetchall()
    finally:
        conn.close()
    if not rows:
        return ref_blocks
    # alignment_id -> Liste (source_key, aligned_seq)
    by_align = {}
    for r in rows:
        aid = r["alignment_id"]
        if aid not in by_align:
            by_align[aid] = []
        by_align[aid].append((r["source_key"], r["aligned_seq"]))
    for (a, b) in pairs_list:
        for aid, entries in by_align.items():
            if len(entries) < 2:
                continue
            seq_for_a = None  # aligned_seq für ID a
            seq_for_b = None  # aligned_seq für ID b
            for sk, seq in entries:
                if _pdb_id_match(a, sk):
                    seq_for_a = seq
                if _pdb_id_match(b, sk):
                    seq_for_b = seq
            if seq_for_a and seq_for_b and seq_for_a != seq_for_b:
                ref_blocks[(a, b)] = ("{}: {}".format(a, seq_for_a), "{}: {}".format(b, seq_for_b))
                break
    return ref_blocks
