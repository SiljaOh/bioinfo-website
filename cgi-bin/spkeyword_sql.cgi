#!/usr/bin/env python3
import argparse
import pymysql
import getpass
import os
import sys
import urllib.parse

# ======= BLATT 1 (Aufgabe 6) – SwissProt swissprot45.dat Parsing (spkeyword.py)
# ssh -p 12 fiocco@bioclient2.bio.ifi.lmu.de
# mysql -h mysql2-ext.bio.ifi.lmu.de -u bioprakt17 bioprakt17 -p
# user="bioprakt17"

# ======= BLATT 2 (Aufgabe 6) – SwissProt SQL-Abfrage (spkeyword-sql.py)
# spkeyword.py --keyword <k1> <k2> [--swissprot <file>|--db]
# " | " --> entweder <file> oder <db> lesen

# Remote-DB
# ssh -p 12 fiocco@bioclient2.bio.ifi.lmu.de
# mysql -h mysql2-ext.bio.ifi.lmu.de -u bioprakt17 bioprakt17 -p
# user="bioprakt17"

# Befehle in MariaDB
# \q - MariaDB beenden
# \c - Query abbrechen


def norm_kw(s: str) -> str:
    s = s.strip().strip('"').strip("'")
    s = " ".join(s.split())
    s = s.rstrip(".;")
    if not s:
        return ""
    return s

# Aufgabe 6 : Swissprot-Keyword
# zu allen gegebenen Keywords Eintrage aus der Swissprot Datei swissprot45.dat
# path:
# 1) ssh -p 12 fiocco@bioclient2.bio.ifi.lmu.de
# 2) /mnt/extstud/praktikum/bioprakt/Data/swissprot45.dat
# Mindestens eines dieser Keywords im Keyword-Feld enthalten.
# Formatspezifikation (https://web.expasy.org/docs/userman.html).
# ACHTUNG: das ganze Keyword suchen ("membrane" anders als "outer membrane protein";
# die AC-Nummern der gefundenen Eintrage wird lexikographisch sortiert: z.B.:
# spkeyword.py --keyword <k1> ... <kn> --swissprot <infile>
# <AC1>
# <AC2>

## STRUKTUR:
# 1) parser mit nargs="+", d.h. mind. 1 Keyword; datei "swissprot45.dat"
# 2) Lesen: pro Zeile
# 3) Gelesen Daten in repository speichern
# 4) Parsen nach AC
# 5) Parsen nach KW
# 6) Treffer speichern
# 7) Ausgabe sortiert nach AC-Nummern der gefundenen Eintrage (lexikographisch)
# 8) Skript ueber CGI in unsere Praktikumswebsite integriert.

## 1) PARSER
# in Terminal (bash): python script.py --input swissprot45.dat

### HEAD bzw. KEYWORDS (s. Formatspezifikation (https://web.expasy.org/docs/userman.html)
## ID = EntryName Status; SequenceLength.;
## AC = ACcession number, AC   AC_number_1;[ AC_number_2;]...[ AC_number_N;],
# - Semicolons separate the accession numbers and a semicolon terminates the list.
# - If necessary, more than one AC line can be used.

## DT = DaTe, DD-MMM-YYYY, integrated into UniProtKB/database_name.  ;
## DE = DEscription;
# Each name is shown on a separate line; lines may therefore exceed 80 characters.
# Protein naming guidelines are described in the International protein nomenclature guidelines.
## OS = ;
## OC = Organism Classification;
# The format of the OC line is:    OC   Node[; Node...].
# OC   Eukaryota; Metazoa; Chordata; Craniata; Vertebrata; Euteleostomi; Mammalia;
## OX = Organism taxonomy cross-reference (specific organism in a taxonomic database)
# Example: OX Taxonomy_database_Qualifier=Taxonomic code;
# Example: OX   NCBI_TaxID=9606;
## KW         Associated keyword (accession)    Optional; Once or more

### also WICHTIG "AC" und "KW"

def build_parser():
    p = argparse.ArgumentParser()
    p.add_argument("--keyword", nargs="+", required=True)

    # " | " --> entweder <file> oder <db> lesen
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--swissprot", type=argparse.FileType("r"))
    src.add_argument("--db", action="store_true")
    return p

def process(entry, wanted):
    # entry = Liste aller Zeilen eines SwissProt-Eintrags (bis "//")
    # wanted = Menge der gesuchten Keywords
    acs = []             # Liste der Accession-Nummern
    kw_buffer = []       # temporärer Speicher für rohe bzw. unverarbeitete KW-Zeilen

    for line in entry:
        if line.startswith("AC   "):
            for t in line[5:].strip().split(";"):
                t = t.strip()
                if t:
                    acs.append(t)

        elif line.startswith("KW   "):
            kw_buffer.append(line[5:].strip())

    # ALLE KW-Zeilen zusammenführen
    kw_text = " ".join(kw_buffer)

    kws = set()
    for t in kw_text.split(";"):
        t = norm_kw(t)
        if t:
            kws.add(t)

    if not wanted.isdisjoint(kws):          # prüft, ob mindestens ein Keyword übereinstimmt
        return acs

    return []

# ssh -p 12 fiocco@bioclient2.bio.ifi.lmu.de
# mysql -h mysql2-ext.bio.ifi.lmu.de -u bioprakt17 bioprakt17 -p
# user="bioprakt17"
# dbpass = getpass.getpass("DB password: ")
# MariaDB = MySQL-kompatible Datenbank
# Passwort explizit oder über os.environ (und nicht im Code gespeichert)?

def searchinDB_AC(wanted):
    #Liste von AC-Codes aus unserer Datenbank
    # DB-Passwort interaktiv abfragen (nicht im Code speichern)
    # DB-Passwort einmal abfragen und an die DB-Funktion weitergeben

    dbpass = "$1$18yyYqpW$y//O6M/6c6ke8EGazjJTx/"
    connection = pymysql.connect(
        host="mysql2-ext.bio.ifi.lmu.de",
        port=3306,
        user="bioprakt17",
        password=dbpass,
        database="bioprakt17"
    )

    cursor = connection.cursor()

    keyword_list = list(wanted)
    if not keyword_list:
        cursor.close()
        connection.close()
        return []

    placeholders = ",".join(["%s"] * len(keyword_list))

#   sql_search bzw. SQL code mit f-string
#   sequence → sequence_keyword → keyword (Many-to-Many-Beziehung)
#   DISTINCT entfernt Duplikate (wg. JOIN/Many-to-Many)
#   JOIN 1: sequence → sequence_keyword (über sequence_id)
#   JOIN 2: sequence_keyword → keyword (über keyword_id)
#   WHERE: Filter auf keyword.word
#   ORDER BY: sortierte Ausgabe
#   s  = sequence
#   sk = sequence_keyword
#   kw = keyword

    sql_search = f"""
    SELECT DISTINCT s.accession
    FROM sequence s
    JOIN sequence_keyword sk ON sk.sequence_id = s.sequence_id
    JOIN keyword kw ON kw.keyword_id = sk.keyword_id
    WHERE kw.word IN ({placeholders})
	AND s.accession IS NOT NULL
    ORDER BY s.accession    
    """

    # parametrisierte Ausführung:
    cursor.execute(sql_search, keyword_list)            # SQL-Struktur und Werte werden getrennt übergeben (Schutz vor SQL-Injection)
    results = cursor.fetchall()                         # Treffer holen (als Liste von Tupeln)
    cursor.close()
    connection.close()

    return [row[0] for row in results]                  # Rückgabe nur der ersten Spalte/row[0] (AC) als einfache Liste

def main():

    # --- CGI Modus ---
    if os.environ.get("GATEWAY_INTERFACE"):

        qs = os.environ.get("QUERY_STRING", "")
        params = urllib.parse.parse_qs(qs, keep_blank_values=True)

        kws = params.get("keyword", [])  

    # Unterstützung für Komma-getrennte Eingabe
    if len(kws) == 1 and "," in kws[0]:
        kws = [k.strip() for k in kws[0].split(",")]

    # Leere Einträge entfernen
    kws = [k for k in kws if k.strip()]

    # Wenn keine Keywords angegeben → Formular anzeigen
    if not kws:
        print("Content-Type: text/html; charset=utf-8")
        print()
        print("""
<html>
<head>
<meta charset="utf-8">
<title>SwissProt Keyword (SQL)</title>
<style>
:root { --tum-blue-dark: #003359; }
body { font-family: Arial, Helvetica, sans-serif; color: var(--tum-blue-dark); }
a { color: var(--tum-blue-dark); }
</style>
</head>
<body>

<h1>SwissProt Keyword – SQL Version (Blatt 2)</h1>

<form method="get" action="spkeyword_sql.cgi">
<label>Keywords (Leerzeichen getrennt):</label>
<input name="keyword" size="60" value="">
<button type="submit">Suchen</button>
</form>

<p><a href="spkeyword.cgi">Zur Blatt-1 File Version</a></p>
<p><a href="../index.html">Zurück zur Startseite</a></p>

</body>
</html>
""")
        raise SystemExit(0)

    # Wenn Keywords vorhanden → Textausgabe der Treffer
    print("Content-Type: text/plain; charset=utf-8")
    print()

    # Übergabe an argparse / DB-Modus
    sys.argv = [sys.argv[0], "--keyword", *kws, "--db"]

    args = build_parser().parse_args()                  # Kommandozeilenargumente einlesen (--keyword, --swissprot oder --db)
    # Verzweigung
    # --- A) DB-Modus ---
    if args.db:                                         # Falls --db gesetzt ist
        wanted = set(norm_kw(k) for k in args.keyword)  # Keywords "normalisieren" und als Menge speichern
        wanted.discard("")                              # leere Einträge entfernen
        accessioncodes = searchinDB_AC(wanted)          # DB-Abfrage durchführen -> Liste von Accessions (AC)

        try:
            for ac in accessioncodes:                   # jede gefundene Accession wird ausgegeben
                print(ac)
        except BrokenPipeError:
            pass

        return

    # --- B) File-Modus (SwissProt-Datei) ---
    wanted = set(norm_kw(k) for k in args.keyword)
    wanted.discard("")

    hits = set()                                        # Menge aller gefundenen Accessions (verhindert Duplikate als Set)
    entry = []                                          # sammelt Zeilen eines SwissProt-Eintrags bis "//"

    for line in args.swissprot:                         # Datei zeilenweise lesen (wie gehabt in Blatt 1)
        line = line.rstrip("\n")                        # Zeilenumbruch entfernen

        if line.startswith("//"):                       # Ende eines SwissProt-Eintrags
            if entry:                                   # Eintrag nicht leer ist -> verarbeiten
                for ac in process(entry, wanted):       # AC + KW prüfen
                    hits.add(ac)                        # gefundene AC speichern
            entry = []                                  # aktueller Block ist abgeschlossen → Liste leeren für den nächsten Eintrag
        else:
            entry.append(line)                          # Zeile im aktuellen Eintrag sammeln

    # Datei endet eventuell nicht mit //
    if entry:
        for ac in process(entry, wanted):
            hits.add(ac)

    try:
        for ac in sorted(hits):
            print(ac)
    except BrokenPipeError:
        pass

if __name__ == "__main__":
    main()
