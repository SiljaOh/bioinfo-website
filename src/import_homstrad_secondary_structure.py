#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
        print("Fehler: pymysql ist nicht installiert. Bitte zuerst 'python3 -m pip install pymysql' ausfuehren.", file=sys.stderr)
        sys.exit(1)

    password = read_db_password()
    if not password:
        print("Fehler: Kein DB-Passwort gefunden. Bitte ALIGNMENT_DB_PASSWORD setzen oder ~/.dbpass anlegen.", file=sys.stderr)
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


def parse_pir_records(path):
    records = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line.startswith(">P1;"):
            i += 1
            continue

        seq_id = line[4:].strip()
        label = lines[i + 1].strip() if i + 1 < len(lines) else ""
        i += 2

        parts = []
        while i < len(lines) and not lines[i].startswith(">P1;"):
            s = lines[i].strip().replace(" ", "")
            if s and not s.startswith("C;"):
                parts.append(s)
            i += 1

        seq = "".join(parts).replace("*", "")
        records.append((seq_id, label, seq))

    return records


def dssp_to_hec(ss_text):
    out = []
    for ch in ss_text:
        if ch in "HGI":
            out.append("H")
        elif ch in "EB":
            out.append("E")
        elif ch == "-":
            continue
        else:
            out.append("C")
    return "".join(out)


def extract_dssp_entries(tem_path):
    entries = {}
    for seq_id, label, seq in parse_pir_records(tem_path):
        if label.strip().upper() != "DSSP":
            continue
        seq_key = seq_id.strip().lower()
        if not seq_key:
            continue
        hec = dssp_to_hec(seq)
        if hec:
            entries[seq_key] = hec
    return entries


def lookup_sequence_id(cur, source, source_key):
    source = (source or "").strip().lower()
    source_key = (source_key or "").strip().lower()
    if not source_key:
        return None

    candidates = [source_key]
    if source == "pdb":
        m = re.match(r"^([0-9][a-z0-9]{3})", source_key)
        pdb4 = m.group(1) if m else source_key[:4]
        if pdb4 and pdb4 not in candidates:
            candidates.append(pdb4)

    for key in candidates:
        cur.execute(
            "SELECT sequence_id FROM source_entry "
            "WHERE LOWER(source) = %s AND LOWER(source_key) = %s "
            "LIMIT 1",
            (source, key),
        )
        row = cur.fetchone()
        if row:
            return row["sequence_id"]
    return None


def ensure_table(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sequence_secondary_structure (
            sequence_id INT NOT NULL,
            method VARCHAR(50) NOT NULL DEFAULT 'HOMSTRAD_DSSP_HEC',
            ss_seq LONGTEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (sequence_id, method)
        )
        """
    )


def import_homstrad(root_dir, source, method, dry_run=False):
    conn = get_connection()
    inserted = 0
    updated = 0
    skipped = []

    try:
        with conn.cursor() as cur:
            ensure_table(cur)

            for family in sorted(os.listdir(root_dir)):
                fam_dir = os.path.join(root_dir, family)
                if not os.path.isdir(fam_dir):
                    continue

                tem_path = os.path.join(fam_dir, family + ".tem")
                if not os.path.isfile(tem_path):
                    continue

                dssp_entries = extract_dssp_entries(tem_path)
                for source_key, ss_seq in sorted(dssp_entries.items()):
                    sequence_id = lookup_sequence_id(cur, source, source_key)
                    if not sequence_id:
                        skipped.append((family, source_key))
                        continue

                    cur.execute(
                        "SELECT ss_seq FROM sequence_secondary_structure "
                        "WHERE sequence_id = %s AND method = %s",
                        (sequence_id, method),
                    )
                    old = cur.fetchone()

                    if not dry_run:
                        cur.execute(
                            "INSERT INTO sequence_secondary_structure (sequence_id, method, ss_seq) "
                            "VALUES (%s, %s, %s) "
                            "ON DUPLICATE KEY UPDATE ss_seq = VALUES(ss_seq), updated_at = CURRENT_TIMESTAMP",
                            (sequence_id, method, ss_seq),
                        )

                    if old is None:
                        inserted += 1
                    elif old["ss_seq"] != ss_seq:
                        updated += 1

        if dry_run:
            conn.rollback()
        else:
            conn.commit()
    finally:
        conn.close()

    print("Import fertig.")
    print("Neu eingefuegt:", inserted)
    print("Aktualisiert:", updated)
    print("Nicht zugeordnet:", len(skipped))
    if skipped:
        print("\nBeispiele fuer nicht gefundene IDs:")
        for family, source_key in skipped[:20]:
            print(" -", family, "->", source_key)
        if len(skipped) > 20:
            print(" ...", len(skipped) - 20, "weitere")


def main():
    default_root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "2019_Feb copy")

    parser = argparse.ArgumentParser(description="Importiert HOMSTRAD-DSSP-Sekundaerstrukturen in sequence_secondary_structure.")
    parser.add_argument("--homstrad-root", default=default_root, help="Pfad zum HOMSTRAD-Ordner, z. B. '2019_Feb copy'")
    parser.add_argument("--source", default="pdb", help="Source-Wert in source_entry, Standard: pdb")
    parser.add_argument("--method", default="HOMSTRAD_DSSP_HEC", help="Methodenname in der Zieltabelle")
    parser.add_argument("--dry-run", action="store_true", help="Nur testen, nichts in die DB schreiben")
    args = parser.parse_args()

    if not os.path.isdir(args.homstrad_root):
        print("Fehler: HOMSTRAD-Ordner nicht gefunden:", args.homstrad_root, file=sys.stderr)
        sys.exit(1)

    import_homstrad(args.homstrad_root, args.source, args.method, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
