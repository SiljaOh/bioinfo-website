#!/usr/bin/env python3

import argparse
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# makescc.py (Aufgabe 11)

# Mapping von 3 Letter Aminosäuren (PDB) zu 1 Letter Code fuer Algorithmus
# für Sequenzdarstellung und weitere Berechnungen ist der 1-Letter-Code besser
AA3_TO_AA1: Dict[str, str] = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D",
    "CYS": "C", "GLN": "Q", "GLU": "E", "GLY": "G",
    "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K",
    "MET": "M", "PHE": "F", "PRO": "P", "SER": "S",
    "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}

@dataclass # -> speichert pro Residue genau ein Atom:
# @dataclass ist ein Decorator: Sprachkonstrukt in Python, mit dem man das Verhalten einer Funktion oder Klasse erweitert oder verändert, ohne deren Code direkt zu modifizieren.
class ResidueAtom:
    chain: str          # Ketten-ID = einbuchstabiger Identifikator, der eine Polypeptidkette innerhalb einer PDB-Struktur kennzeichnet.
    resseq: int         # Positionsnummer im PDB
    serial: int         # Atomnummer
    aa1: str            # Aminosäure als 1-Letter-Code
    x: float            # 3D-Koordinaten
    y: float            # 3D-Koordinaten
    z: float            # 3D-Koordinaten
    ss: str = "C"       # Sekundaerstruktur: H (Helix), E (Extended for beta-sheet), C (Coil)


def parse_args() -> argparse.Namespace:
    # Namespace ist ein Container = Objekt, das mehrere zusammengehörige Werte strukturiert speichert und über Namen zugänglich macht.
    # argparse ist das Standard-Modul in Python zur Verarbeitung von Kommandozeilenargumenten.
    # sys.argv ist die Liste der Kommandozeilenargumente, mit denen ein Python-Programm gestartet wurde.
    # CAVE: Ohne type-Angabe wäre der Standardtyp str, d.h. args.distance wäre ein String.
    # contact matrix = contact matrix eine quadratische Matrix, die speichert, welche Residuen miteinander in Kontakt stehen.
    # default = None -> Wenn dieses Argument auf der Kommandozeile nicht angegeben wird, bekommt es automatisch den Wert None.
    p = argparse.ArgumentParser(description="Generate sscc table for a PDB id or local PDB file")
    p.add_argument("--id", required=True, help="PDB id (e.g. 1CRN) or local path to .pdb file")
    p.add_argument("--distance", required=True, type=float, help="contact cutoff distance in Angstrom")
    p.add_argument("--type", required=True, dest="atom_type", help="atom name, e.g. CA or CB")
    p.add_argument("--length", required=True, type=int, help="local contact max sequence distance")
    p.add_argument("--contactmatrix", default=None, help="optional: write contact matrix to this file")
    return p.parse_args()


# Funktion 1) download_pdb
# Lädt eine PDB-Datei entweder von lokalem Pfad oder per Download (RCSB)
# Rückgabe: Liste von Zeilen (List[str]), inklusive Zeilenumbrüche
def download_pdb(pdb_id_or_path: str) -> List[str]:
    import os
    # falls der Input ein existierender Dateipfad ist:
    if os.path.isfile(pdb_id_or_path):
        with open(pdb_id_or_path, "r", encoding="utf-8", errors="replace") as f:
            return f.readlines()

    # strip() entfernt Whitespaces, upper() normalisiert auf Großbuchstaben
    pdb_id = pdb_id_or_path.strip().upper()
    url = f"https://files.rcsb.org/download/{pdb_id}.pdb"    # Standard-Download-URL für PDB-Dateien vom RCSB

    with urllib.request.urlopen(url) as response:
        text = response.read().decode("utf-8", errors="replace")    # decode mit UTF-8; ungültige Bytes werden ersetzt statt Exception auszulösen

    return text.splitlines(keepends=True)


# Funktion 2) extract_ss_ranges
# Liest HELIX- und SHEET-Records aus einer PDB-Datei
# Rückgabe:
#   helix  -> Liste von (chain, start_resseq, end_resseq)
#   sheet  -> Liste von (chain, start_resseq, end_resseq)
# chain ist der Ketten-Identifier einer PDB-Struktur.
# (chain, start_resseq, end_resseq) ist ein Tupel, das einen Sekundärstruktur-Bereich beschreibt.
# resseq = Nummer, die im PDB-File jedem Residue zugeordnet ist.
# end_resseq = end-residue-sequenznummer eines Sekundärstruktur-Bereichs
def extract_ss_ranges(
    pdb_lines: List[str]
) -> Tuple[List[Tuple[str, int, int]], List[Tuple[str, int, int]]]:
    # HELIX und SHEET Bereiche aus Header lesen
    helix: List[Tuple[str, int, int]] = []
    sheet: List[Tuple[str, int, int]] = []

    for line in pdb_lines:
        rec = line[0:6].strip()

        if rec == "HELIX":
            chain = line[19:20].strip()
            start_s = line[21:25].strip()
            end_s = line[33:37].strip()
            if chain and start_s and end_s:
                helix.append((chain, int(start_s), int(end_s)))

        elif rec == "SHEET":
            chain = line[21:22].strip() or "?"
            start_s = line[22:26].strip()
            end_s = line[33:37].strip()
            if chain and start_s and end_s:
                sheet.append((chain, int(start_s), int(end_s)))

    return helix, sheet


# Funktion 3) keep_only_model_one
def keep_only_model_one(pdb_lines: List[str]) -> List[str]:
    # wenn MODEL existiert, nur Modell 1 behalten, sonst alles
    if not any(line.startswith("MODEL") for line in pdb_lines):
        return pdb_lines

    out: List[str] = []
    in_first = False

    for line in pdb_lines:
        if line.startswith("MODEL"):
            in_first = (line[10:14].strip() == "1")
            continue

        if line.startswith("ENDMDL"):
            if in_first:
                break
            continue

        if in_first:
            out.append(line)

    return out


# Funktion 4) parse_residue_atoms
# -> extrahiert aus einer PDB-Datei pro Residue genau ein bestimmtes Atom (z.B. CA) und speichert dessen Koordinaten
def parse_residue_atoms(
    pdb_lines: List[str],
    atom_type: str,
    aa3_to_aa1: dict
) -> List[ResidueAtom]:
    # pro Residue genau ein Atom sammeln, zB CA
    want = atom_type.strip()
    residues: List[ResidueAtom] = []
    seen = set()

    for line in pdb_lines:
        if not line.startswith("ATOM"):
            continue

        if line[12:16].strip() != want:
            continue

        alt_loc = line[16:17]
        if alt_loc not in (" ", "A"):
            continue

        resname3 = line[17:20].strip()
        chain = line[21:22].strip()
        resseq_s = line[22:26].strip()
        serial_s = line[6:11].strip()

        if not resseq_s or not serial_s:
            continue

        key = (chain, int(resseq_s))
        if key in seen:
            continue
        seen.add(key)

        aa1 = aa3_to_aa1.get(resname3, "X")

        x = float(line[30:38].strip())
        y = float(line[38:46].strip())
        z = float(line[46:54].strip())

        residues.append(
            ResidueAtom(chain, int(resseq_s), int(serial_s), aa1, x, y, z)
        )

    return residues


# Funktion 5) ss_for_residue
# -> bestimmt für ein einzelnes Residue, ob es zu einer Helix (H), einem Sheet (E) oder keiner definierten Sekundärstruktur (C) gehört.
def ss_for_residue(
    chain: str,
    resseq: int,
    helix_ranges,
    sheet_ranges
) -> str:
    # H falls in HELIX Bereich, sonst E falls in SHEET Bereich, sonst C
    for ch, start, end in helix_ranges:
        if ch == chain and start <= resseq <= end:
            return "H"

    for ch, start, end in sheet_ranges:
        if ch == chain and start <= resseq <= end:
            return "E"

    return "C"


# Funktion 6) compute_contacts
# für alle Residue Paare wird die euklidische Distanz zwischen den ausgewählten Atomen (z.B. CA)
# euklidische Distanz = normale, direkte Abstand zwischen zwei Punkten im Raum, wie man ihn aus dem Satz des Pythagoras kennt.
def compute_contacts(residues, distance_cutoff, local_length):
    # Kontakt wenn Distanz kleiner cutoff

    # Anzahl residues
    n = len(residues)
    # Zähler für Kontakte pro Residue
    # local_counts[i]  -> Kontakte mit kleinem Sequenzabstand
    # global_counts[i] -> alle übrigen Kontakte
    global_counts = [0] * n
    local_counts = [0] * n

    # Kontaktmatrix:
    # contact_matrix[i][j] = 1 falls Distanz < Cutoff,
    # sonst 0 (binäre Darstellung der Struktur als Graph)
    contact_matrix = [[0] * n for _ in range(n)]

    # Distanzmatrix:
    # distance_matrix[i][j] speichert die euklidische Distanz
    # zwischen Residue i und j
    distance_matrix = [[0.0] * n for _ in range(n)]

    # Jedes Residue-Paar genau einmal betrachten
    # (j startet bei i+1, um Doppelberechnung zu vermeiden)
    for i in range(n):
        ai = residues[i]
        for j in range(i + 1, n):
            aj = residues[j]

            # Berechnung
            # Koordinaten in der PDB-Datei sind kartesische Koordinaten in Ångström.
            dx = ai.x - aj.x
            dy = ai.y - aj.y
            dz = ai.z - aj.z
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)

            distance_matrix[i][j] = dist
            distance_matrix[j][i] = dist

            if dist < distance_cutoff:
                contact_matrix[i][j] = 1
                contact_matrix[j][i] = 1

                # prüfen, ob beide Residues in derselben Kette sind
                same_chain = ai.chain == aj.chain
                # Sequenzabstand
                seq_gap = abs(ai.resseq - aj.resseq)

                # Definition eines lokalen Kontakts:
                # gleicher Chain-Identifier und geringer Sequenzabstand (< local_length)
                if same_chain and 0 < seq_gap < local_length:
                    local_counts[i] += 1
                    local_counts[j] += 1
                else:
                    global_counts[i] += 1
                    global_counts[j] += 1

    return global_counts, local_counts, contact_matrix, distance_matrix


# Funktion 7) write_contact_matrix (nur wenn --contactmatrix benutzt wird)
# -> schreibt die berechnete Kontaktmatrix als tabulator-getrennte Textdatei (TSV) in eine Datei.
def write_contact_matrix(path, residues, contact_matrix):
    labels = [f"{r.chain}{r.resseq}" for r in residues]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\t" + "\t".join(labels) + "\n")
        for i, row in enumerate(contact_matrix):
            f.write(labels[i] + "\t" + "\t".join(str(v) for v in row) + "\n")

def write_distance_heatmap(path, distance_matrix):
    plt.figure(figsize=(6, 6))
    plt.imshow(distance_matrix, cmap="viridis", origin="lower")
    plt.colorbar(label="Distance (Å)")
    plt.xlabel("Residue index")
    plt.ylabel("Residue index")
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()


def main(args=None) -> int:
    if args is None:
        args = parse_args()
   # Logik/Struktur:
   # 1) args
   # 2) PDB laden
   # 3) Helix/Sheet ranges
   # 4) Model 1 filtern
   # 5) Residues extrahieren (Atomtyp)
   # 6) ss zuweisen
   # 7) Kontakte berechnen
   # 8) Tabelle ausgeben
   # 9) optional Matrix schreiben
   # 10) Exitcode 0

    # 1) Argumente/Variable lesen (args)

    # 2) Werte in Variable schreiben + PDB laden
    pdb_id = args.id
    distance_cutoff = args.distance
    atom_type = args.atom_type
    local_length = args.length
    contactmatrix_path = args.contactmatrix

    pdb_lines_all = download_pdb(pdb_id)

    # 3) Sekundaerstruktur Bereiche auslesen
    helix_ranges, sheet_ranges = extract_ss_ranges(pdb_lines_all)

    # 4) Modell 1 ablesen
    pdb_lines_model_one = keep_only_model_one(pdb_lines_all)

    # 5) Residues sammeln / extrahieren
    residues = parse_residue_atoms(
        pdb_lines_model_one,
        atom_type,
        AA3_TO_AA1
    )

    # 6) ss pro Residue setzen (ss = Sekundärstruktur)
    for r in residues:
        r.ss = ss_for_residue(r.chain, r.resseq, helix_ranges, sheet_ranges)

    # 7) Kontakte berechnen
    global_counts, local_counts, contact_matrix, distance_matrix = compute_contacts(
        residues,
        distance_cutoff,
        local_length
    )
    write_distance_heatmap("distance_map.png", distance_matrix)

    # 8) Secondary Structure Contact Count (sscc) ausgeben
    print("chain\tpos\tserial\taa\tss\tglobal\tlocal")
    for i, r in enumerate(residues):
        print(
            f"{r.chain}\t{r.resseq}\t{r.serial}\t"
            f"{r.aa1}\t{r.ss}\t"
            f"{global_counts[i]}\t{local_counts[i]}"
        )

    # 9) Dateien schreiben
    if contactmatrix_path is not None:
        write_contact_matrix(contactmatrix_path, residues, contact_matrix)

    # 10) Exitcode 0 (Zahl an das Betriebssystem zurück)
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
