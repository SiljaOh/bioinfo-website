#!/usr/bin/env python3
# CGI: HOMSTRAD Alignments zu PDB-ID(s) anzeigen inkl. Sekundärstruktur

import os
import html
import cgi
import mysql.connector
import layout_group17 as layout

# --- DB Einstellungen
DB_HOST = "mysql2-ext.bio.ifi.lmu.de"
DB_NAME = "bioprakt17"
DB_USER = "bioprakt17"

# Passwort aus Datei lesen (CGI bekommt oft keine ENV Variablen)
PW_FILE = os.path.join(os.path.dirname(__file__), ".secrets", "mysql_pw.txt")

def load_pw():
    try:
        with open(PW_FILE, "r") as f:
            return f.read().strip()
    except Exception:
        return ""

DB_PW = load_pw()

def norm_id(s: str) -> str:
    s = (s or "").strip().replace(" ", "").lower()
    if not s:
        return ""

    # Fall: 5 Zeichen wie "1bgxt" -> so lassen (pdb+chain als 5. Zeichen)
    if len(s) == 5 and s[:4].isalnum() and s[4].isalnum():
        return s

    # Fall: Format "1bgx_T"
    if "_" in s:
        pdb, chain = s.split("_", 1)
        return f"{pdb[:4]}_{chain[:1].upper()}" if chain else pdb[:4]

    # sonst nur 4-stellige PDB-ID
    return s[:4]

def connect():
    return mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PW, database=DB_NAME
    )

def fetchall(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchall()

def fetchone(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchone()

def resolve_keys(cur, pdb_or_key: str):
    """
    Robust:
    - akzeptiert Eingabe "1bgx" oder "1bgx_T"
    - findet source_key unabhängig von Groß/Kleinschreibung bei source
    - findet Keys auch wenn sie nicht exakt underscore-format haben
    """
    if not pdb_or_key:
        return []

    # Wenn Nutzer schon eine Chain angegeben hat: versuche exakt zu matchen
    if "_" in pdb_or_key:
        row = fetchone(cur,
            "SELECT source_key FROM source_entry "
            "WHERE LOWER(source)='pdb' AND source_key=%s",
            (pdb_or_key,))
        if row:
            return [row[0]]

        # Fallback: manche speichern ohne underscore (z.B. 1bgxT)
        pdb, chain = pdb_or_key.split("_", 1)
        alt = f"{pdb}{chain}"
        row = fetchone(cur,
            "SELECT source_key FROM source_entry "
            "WHERE LOWER(source)='pdb' AND source_key=%s",
            (alt,))
        return [row[0]] if row else []

    # Nur pdb-ID: nimm alle Keys, die mit pdb anfangen (alle Chains/Formate)
    pattern = pdb_or_key + "%"
    rows = fetchall(cur,
        "SELECT source_key FROM source_entry "
        "WHERE LOWER(source)='pdb' AND source_key LIKE %s "
        "ORDER BY source_key",
        (pattern,))
    return [r[0] for r in rows]

def families_for_key(cur, source_key: str):
    rows = fetchall(cur, """
        SELECT f.family_id, f.name
        FROM family_member fm
        JOIN family f ON f.family_id = fm.family_id
        WHERE fm.source='pdb' AND fm.source_key=%s
        ORDER BY f.name
    """, (source_key,))
    return rows  # list of (family_id, family_name)

def common_families(cur, key1: str, key2: str):
    rows = fetchall(cur, """
        SELECT f.family_id, f.name
        FROM family_member fm1
        JOIN family_member fm2 ON fm1.family_id = fm2.family_id
        JOIN family f ON f.family_id = fm1.family_id
        WHERE fm1.source='pdb' AND fm2.source='pdb'
          AND fm1.source_key=%s AND fm2.source_key=%s
        ORDER BY f.name
    """, (key1, key2))
    return rows

def alignment_id_for_family(cur, family_name: str):
    row = fetchone(cur,
        "SELECT alignment_id FROM alignment WHERE name=%s AND type='msa'",
        (family_name,))
    return row[0] if row else None

def msa_rows_with_ss(cur, alignment_id: int):
    """
    Holt alle Zeilen (PDB_key + aligned_seq + aligned_ss) für ein MSA in EINER Query.
    aligned_ss kann NULL sein (falls nicht vorhanden).
    """
    rows = fetchall(cur, """
        SELECT
            se.source_key,
            ar.sequence_id,
            ar.aligned_seq,
            ss.aligned_ss
        FROM alignment_row ar
        JOIN source_entry se ON se.sequence_id = ar.sequence_id AND LOWER(se.source)='pdb'
        LEFT JOIN secondary_structure ss
            ON ss.alignment_id = ar.alignment_id AND ss.sequence_id = ar.sequence_id
        WHERE ar.alignment_id=%s
        ORDER BY se.source_key
    """, (alignment_id,))
    # rows: list of (source_key, sequence_id, aligned_seq, aligned_ss)
    return rows

def html_header(title="HOMSTRAD Viewer"):
    layout.print_page_start(title)
    layout.print_main_start()
    print('<p class="back"><a href="../index.html">← Zur Startseite</a></p>')
    print(f"<h1>{html.escape(title)}</h1>")

def html_footer():
    layout.print_main_end()
    layout.print_page_end()

def show_form(pdb1="", pdb2=""):
    print("""
<form method="get" action="homstrad.cgi">
  PDB-ID 1 (z.B. 1bgxt, 1tbo oder 2mbr): <input name="pdb1" value="{p1}" />
  <br><br>
  PDB-ID 2 (optional): <input name="pdb2" value="{p2}" />
  <br><br>
  <button type="submit">Search</button>
</form>
<hr>
""".format(p1=html.escape(pdb1), p2=html.escape(pdb2)))

def show_msa(cur, family_name: str, highlight_keys=None):
    highlight_keys = set(highlight_keys or [])
    aid = alignment_id_for_family(cur, family_name)
    if aid is None:
        print(f"<p><b>{html.escape(family_name)}</b>: kein alignment in DB gefunden.</p>")
        return

    rows = msa_rows_with_ss(cur, aid)
    print(f"<h3>Family: {html.escape(family_name)} (MSA)</h3>")
    print('<div class="small">Ausgabe: pro Sequenz eine SS-Zeile (aligned_ss) + SEQ-Zeile (aligned_seq). Gaps sind synchron.</div>')

    for skey, seq_id, aseq, ass in rows:
        label = skey
        if skey in highlight_keys:
            label = ">>> " + label + " <<<"

        # SS optional; wenn NULL -> placeholder
        ss_line = ass if ass else "(not available)"

        print("<pre>"
              + html.escape(label) + "\n"
              + "SS : " + html.escape(ss_line) + "\n"
              + "SEQ: " + html.escape(aseq) + "\n"
              + "</pre>")

def show_pairwise_from_msa(cur, family_name: str, key1: str, key2: str):
    aid = alignment_id_for_family(cur, family_name)
    if aid is None:
        return

    rows = msa_rows_with_ss(cur, aid)
    rowmap = {skey: (seq_id, aseq, ass) for skey, seq_id, aseq, ass in rows}

    if key1 not in rowmap or key2 not in rowmap:
        return

    seq1_id, a1, ss1 = rowmap[key1]
    seq2_id, a2, ss2 = rowmap[key2]

    print(f"<h3>Pairwise (aus MSA extrahiert): {html.escape(family_name)}</h3>")
    print("<pre>")
    print(html.escape(key1))
    print("SS : " + html.escape(ss1 if ss1 else "(not available)"))
    print("SEQ: " + html.escape(a1))
    print()
    print(html.escape(key2))
    print("SS : " + html.escape(ss2 if ss2 else "(not available)"))
    print("SEQ: " + html.escape(a2))
    print("</pre>")

def main():
    html_header("HOMSTRAD alignment viewer")

    if not DB_PW:
        print("<p><b>Fehler:</b> DB-Passwort konnte nicht geladen werden.</p>")
        print(f"<p class='small'>Erwartet in: <code>{html.escape(PW_FILE)}</code></p>")
        html_footer()
        return

    form = cgi.FieldStorage()
    pdb1_in = form.getfirst("pdb1", "")
    pdb2_in = form.getfirst("pdb2", "")

    show_form(pdb1_in, pdb2_in)

    pdb1 = norm_id(pdb1_in)
    pdb2 = norm_id(pdb2_in)

    if not pdb1:
        print("<p class='small'>Bitte mindestens PDB-ID 1 eingeben.</p>")
        html_footer()
        return

    conn = connect()
    try:
        with conn.cursor(buffered=True) as cur:
            keys1 = resolve_keys(cur, pdb1)
            keys2 = resolve_keys(cur, pdb2) if pdb2 else []

            if not keys1:
                print(f"<p><b>Keine Treffer</b> für PDB-ID 1: {html.escape(pdb1_in)}</p>")
                html_footer()
                return

            # --- Fall: nur eine ID ---
            if not pdb2:
                print(f"<p><b>PDB-ID 1:</b> {html.escape(pdb1_in)} → Keys: {html.escape(', '.join(keys1))}</p>")
                for k in keys1:
                    fams = families_for_key(cur, k)
                    if not fams:
                        print(f"<p>{html.escape(k)}: keine HOMSTRAD families gefunden.</p>")
                        continue
                    print(f"<h3>Alignments für {html.escape(k)}</h3>")
                    for _, fam_name in fams:
                        show_msa(cur, fam_name, highlight_keys=[k])
                html_footer()
                return

            # --- Fall: zwei IDs ---
            if not keys2:
                print(f"<p><b>Keine Treffer</b> für PDB-ID 2: {html.escape(pdb2_in)}</p>")
                html_footer()
                return

            print(f"<p><b>PDB-ID 1:</b> {html.escape(pdb1_in)} → Keys: {html.escape(', '.join(keys1))}</p>")
            print(f"<p><b>PDB-ID 2:</b> {html.escape(pdb2_in)} → Keys: {html.escape(', '.join(keys2))}</p>")

            # erste chain-kombination suchen mit gemeinsamer Family
            best = None
            for k1 in keys1:
                for k2 in keys2:
                    commons = common_families(cur, k1, k2)
                    if commons:
                        best = (k1, k2, commons)
                        break
                if best:
                    break

            if best:
                k1, k2, commons = best
                print(f"<p><b>Gemeinsame Familie gefunden</b> für {html.escape(k1)} und {html.escape(k2)}:</p>")
                for _, fam_name in commons:
                    show_pairwise_from_msa(cur, fam_name, k1, k2)
                    show_msa(cur, fam_name, highlight_keys=[k1, k2])
                html_footer()
                return

            # keine gemeinsame Familie -> zeige families getrennt
            print("<p><b>Keine gemeinsame Familie.</b> Zeige families separat.</p>")

            print("<h3>Families/Alignments für PDB-ID 1</h3>")
            for k1 in keys1:
                fams = families_for_key(cur, k1)
                for _, fam_name in fams:
                    show_msa(cur, fam_name, highlight_keys=[k1])

            print("<h3>Families/Alignments für PDB-ID 2</h3>")
            for k2 in keys2:
                fams = families_for_key(cur, k2)
                for _, fam_name in fams:
                    show_msa(cur, fam_name, highlight_keys=[k2])

    finally:
        conn.close()

    html_footer()

if __name__ == "__main__":
    main()
