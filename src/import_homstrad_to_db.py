#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Importiert HOMSTRAD-Referenz aus dem Ordner „2019_Feb copy“ (.ali + .tem)
in die Tabellen: alignment, sequence, source_entry, alignment_row, secondary_structure.

Damit kann die Validation (validate.cgi) die Referenz aus der Datenbank laden
statt aus dem Dateisystem. Kein HOMSTRAD_DIR auf dem Server nötig.

Verwendung:
  python3 scripts/import_homstrad_to_db.py [--homstrad-root "2019_Feb copy"] [--dry-run]
"""

import argparse
import os
import re
import sys
def read_db_password():
    password = os.environ.get("ALIGNMENT_DB_PASSWORD", "").strip()
    if password:
        return password
    try:
        with open(os.path.expanduser("~/.dbpass"), "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def get_connection():
    try:
        import pymysql
    except ImportError:
        print("Fehler: pymysql ist nicht installiert. Bitte: python3 -m pip install pymysql", file=sys.stderr)
        sys.exit(1)
    password = read_db_password()
    if not password:
        print("Fehler: Kein DB-Passwort (ALIGNMENT_DB_PASSWORD oder ~/.dbpass).", file=sys.stderr)
        sys.exit(1)
    return pymysql.connect(
        host=os.environ.get("ALIGNMENT_DB_HOST", "mysql2-ext.bio.ifi.lmu.de"),
        port=int(os.environ.get("ALIGNMENT_DB_PORT", "3306")),
        user=os.environ.get("ALIGNMENT_DB_USER", "bioprakt17"),
        password=password,
        database=os.environ.get("ALIGNMENT_DB_NAME", "bioprakt17"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def parse_ali_file(path):
    """Liest .ali (PIR-Format): Liste von (seq_id, aligned_seq). aligned_seq enthält Gaps (-)."""
    entries = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line.startswith(">P1;"):
            i += 1
            continue
        seq_id = line[4:].strip()
        i += 2  # Überspringen der zweiten Zeile (structureX:... oder sequence)
        parts = []
        while i < len(lines) and not lines[i].strip().startswith(">P1;"):
            s = lines[i].strip().replace(" ", "")
            if s and not s.startswith("C;"):
                parts.append(s)
            i += 1
        aligned_seq = "".join(parts).replace("*", "")
        if seq_id and aligned_seq:
            entries.append((seq_id, aligned_seq))
    return entries


def parse_tem_secondary_structure(path):
    """Liest aus .tem die Blöcke 'secondary structure and phi angle'. Rückgabe: {seq_id: aligned_ss} (H/E/C/-)."""
    result = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line.startswith(">P1;"):
            i += 1
            continue
        seq_id = line[4:].strip()
        i += 1
        label = lines[i].strip() if i < len(lines) else ""
        i += 1
        if label.lower() != "secondary structure and phi angle":
            while i < len(lines) and not lines[i].strip().startswith(">P1;"):
                i += 1
            continue
        parts = []
        while i < len(lines) and not lines[i].strip().startswith(">P1;"):
            s = lines[i].strip().replace(" ", "")
            if s and not s.startswith("C;"):
                parts.append(s)
            i += 1
        raw_ss = "".join(parts).replace("*", "")
        # H/E/P/C -> H/E/C, Gaps bleiben
        aligned_ss = "".join(
            "H" if c in "H" else "E" if c in "E" else "-" if c == "-" else "C"
            for c in raw_ss
        )
        if seq_id and aligned_ss:
            result[seq_id] = aligned_ss
    return result


def ensure_tables(cur):
    """Stellt sicher, dass alignment, alignment_row, secondary_structure existieren (namen wie in Doku)."""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alignment (
            alignment_id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            type VARCHAR(64) NOT NULL DEFAULT 'msa',
            UNIQUE KEY uk_name_type (name, type)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alignment_row (
            row_id INT AUTO_INCREMENT PRIMARY KEY,
            alignment_id INT NOT NULL,
            sequence_id INT NOT NULL,
            aligned_seq LONGTEXT NOT NULL,
            KEY idx_align (alignment_id),
            KEY idx_seq (sequence_id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS secondary_structure (
            alignment_id INT NOT NULL,
            sequence_id INT NOT NULL,
            aligned_ss LONGTEXT NOT NULL,
            PRIMARY KEY (alignment_id, sequence_id)
        )
    """)


def get_or_create_sequence_id(cur, source_key, ungapped_seq, source="homstrad", dry_run=False):
    """Liefert sequence_id für source_key. Legt sequence + source_entry an, falls nötig."""
    sk = (source_key or "").strip()
    if not sk:
        return None
    cur.execute(
        "SELECT sequence_id FROM source_entry WHERE LOWER(source)=%s AND LOWER(source_key)=%s LIMIT 1",
        (source.lower(), sk.lower()),
    )
    row = cur.fetchone()
    if row:
        return row["sequence_id"]
    if dry_run:
        return -1  # Platzhalter
    cur.execute("INSERT INTO sequence (seq) VALUES (%s)", (ungapped_seq or "",))
    seq_id = cur.lastrowid
    cur.execute(
        "INSERT INTO source_entry (source, source_key, sequence_id) VALUES (%s, %s, %s)",
        (source, sk, seq_id),
    )
    return seq_id


def get_or_create_alignment_id(cur, family_name, a_type="homstrad", dry_run=False):
    """Liefert alignment_id für diese Familie. Bei Re-Import: vorhandene Zeilen löschen."""
    cur.execute(
        "SELECT alignment_id FROM alignment WHERE name=%s AND type=%s LIMIT 1",
        (family_name, a_type),
    )
    row = cur.fetchone()
    if row:
        aid = row["alignment_id"]
        if not dry_run:
            cur.execute("DELETE FROM secondary_structure WHERE alignment_id=%s", (aid,))
            cur.execute("DELETE FROM alignment_row WHERE alignment_id=%s", (aid,))
        return aid
    if dry_run:
        return -1
    cur.execute("INSERT INTO alignment (name, type) VALUES (%s, %s)", (family_name, a_type))
    return cur.lastrowid


def run_import(homstrad_root, dry_run=False):
    stats = {"families": 0, "sequences": 0, "rows": 0, "ss": 0, "skipped_fam": 0}

    if dry_run:
        # Nur Dateien parsen, keine DB
        for family in sorted(os.listdir(homstrad_root)):
            fam_dir = os.path.join(homstrad_root, family)
            if not os.path.isdir(fam_dir):
                continue
            ali_path = os.path.join(fam_dir, family + ".ali")
            if not os.path.isfile(ali_path):
                stats["skipped_fam"] += 1
                continue
            try:
                entries = parse_ali_file(ali_path)
            except Exception:
                stats["skipped_fam"] += 1
                continue
            if len(entries) < 2:
                stats["skipped_fam"] += 1
                continue
            stats["families"] += 1
            tem_path = os.path.join(fam_dir, family + ".tem")
            ss_map = parse_tem_secondary_structure(tem_path) if os.path.isfile(tem_path) else {}
            for seq_id, aligned_seq in entries:
                stats["rows"] += 1
                if seq_id in ss_map and len(ss_map[seq_id]) == len(aligned_seq):
                    stats["ss"] += 1
        print("Dry-Run (keine DB): Familien:", stats["families"], "| Alignment-Zeilen:", stats["rows"], "| Sekundärstruktur:", stats["ss"])
        if stats["skipped_fam"]:
            print("Übersprungene Familien:", stats["skipped_fam"])
        return

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            ensure_tables(cur)

            for family in sorted(os.listdir(homstrad_root)):
                fam_dir = os.path.join(homstrad_root, family)
                if not os.path.isdir(fam_dir):
                    continue
                ali_path = os.path.join(fam_dir, family + ".ali")
                if not os.path.isfile(ali_path):
                    stats["skipped_fam"] += 1
                    continue

                entries = parse_ali_file(ali_path)
                if len(entries) < 2:
                    stats["skipped_fam"] += 1
                    continue

                tem_path = os.path.join(fam_dir, family + ".tem")
                ss_map = parse_tem_secondary_structure(tem_path) if os.path.isfile(tem_path) else {}

                alignment_id = get_or_create_alignment_id(cur, family, a_type="homstrad", dry_run=dry_run)
                stats["families"] += 1

                for seq_id, aligned_seq in entries:
                    ungapped = aligned_seq.replace("-", "")
                    seq_id_db = get_or_create_sequence_id(cur, seq_id, ungapped, source="homstrad", dry_run=dry_run)
                    if seq_id_db is None:
                        continue
                    if dry_run:
                        stats["rows"] += 1
                        if seq_id in ss_map:
                            stats["ss"] += 1
                        continue
                    if seq_id_db <= 0:
                        continue
                    cur.execute(
                        "INSERT INTO alignment_row (alignment_id, sequence_id, aligned_seq) VALUES (%s, %s, %s)",
                        (alignment_id, seq_id_db, aligned_seq),
                    )
                    stats["rows"] += 1
                    if seq_id in ss_map and len(ss_map[seq_id]) == len(aligned_seq):
                        cur.execute(
                            "INSERT INTO secondary_structure (alignment_id, sequence_id, aligned_ss) VALUES (%s, %s, %s)",
                            (alignment_id, seq_id_db, ss_map[seq_id]),
                        )
                        stats["ss"] += 1

        if dry_run:
            conn.rollback()
        else:
            conn.commit()
    finally:
        conn.close()

    print("Import fertig (HOMSTRAD → alignment, alignment_row, secondary_structure, sequence, source_entry).")
    print("Familien:", stats["families"], "| Alignment-Zeilen:", stats["rows"], "| Sekundärstruktur:", stats["ss"])
    if stats["skipped_fam"]:
        print("Übersprungene Familien (kein .ali oder <2 Sequenzen):", stats["skipped_fam"])


def main():
    default_root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "2019_Feb copy")
    parser = argparse.ArgumentParser(description="HOMSTRAD-Referenz aus 2019_Feb copy in die DB importieren.")
    parser.add_argument("--homstrad-root", default=default_root, help="Pfad zum HOMSTRAD-Ordner (z. B. 2019_Feb copy)")
    parser.add_argument("--dry-run", action="store_true", help="Nur parsen, nichts in die DB schreiben")
    args = parser.parse_args()

    if not os.path.isdir(args.homstrad_root):
        print("Fehler: Ordner nicht gefunden:", args.homstrad_root, file=sys.stderr)
        sys.exit(1)
    run_import(args.homstrad_root, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
