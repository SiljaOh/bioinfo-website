# -*- coding: utf-8 -*-
"""
HOMSTRAD .ali Parser (PIR/STAMP format).
Liest alle .ali Dateien und liefert pro Datei die gelisteten Sequenzen (id, aligned_sequence).
Für Validierung: Referenz-Alignment für ein Paar (i,j) = (aligned_i, aligned_j).
"""

import os
import re
from pathlib import Path
from typing import List, Tuple, Iterator


def _normalize_seq(s: str) -> str:
    """Entfernt Zeilenumbrüche, ersetzt / durch -, entfernt * und Leerzeichen."""
    s = s.replace("\r", "").replace("\n", "").replace(" ", "")
    s = s.replace("/", "-")  # Chain break in PIR
    # Nur erlaubte Zeichen (Amino-Buchstaben + Gap)
    return "".join(c for c in s if c in "ACDEFGHIKLMNPQRSTVWY-" or c == "*").replace("*", "")


def parse_ali_file(path: Path) -> List[Tuple[str, str]]:
    """
    Parst eine HOMSTRAD .ali Datei.
    Returns: Liste von (id, aligned_sequence). Alle aligned_sequences haben dieselbe Länge (MSA).
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    entries: List[Tuple[str, str]] = []
    current_id = None
    current_lines: List[str] = []

    for line in text.splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        if line.startswith("C;") or line.startswith("#"):
            continue
        if line.startswith(">P1;"):
            if current_id is not None and current_lines:
                seq = _normalize_seq("".join(current_lines))
                if seq and len(seq) > 10:  # Mindestlänge
                    entries.append((current_id, seq))
            # Neuer Eintrag
            current_id = line[4:].strip().split()[0] if line[4:].strip() else None
            current_lines = []
            continue
        if current_id is not None:
            # Sequenzzeile: bis ---* oder Zeile die mit * endet
            if "---*" in line or line.strip().endswith("*"):
                part = line.split("---*")[0] if "---*" in line else line.rstrip("*")
                current_lines.append(_normalize_seq(part))
                seq = _normalize_seq("".join(current_lines))
                if seq and len(seq) > 10:
                    entries.append((current_id, seq))
                current_id = None
                current_lines = []
            else:
                current_lines.append(line)

    if current_id is not None and current_lines:
        seq = _normalize_seq("".join(current_lines))
        if seq and len(seq) > 10:
            entries.append((current_id, seq))

    return entries


def alignment_length(entries: List[Tuple[str, str]]) -> int:
    """Einheitliche MSA-Länge (alle Einträge sollten gleich lang sein)."""
    if not entries:
        return 0
    return len(entries[0][1])


def get_pairs_from_family(entries: List[Tuple[str, str]], max_pairs_per_family: int = 50) -> List[Tuple[str, str, str, str]]:
    """
    Erzeugt Paare (id1, id2, ref_ali1, ref_ali2) für alle i<j.
    ref_ali1/ref_ali2 sind die Referenz-Alignment-Strings (gleiche Länge).
    Begrenzt auf max_pairs_per_family zufällige Paare, um Laufzeit zu begrenzen.
    """
    import random
    n = len(entries)
    if n < 2:
        return []
    length = alignment_length(entries)
    pairs: List[Tuple[str, str, str, str]] = []
    for i in range(n):
        for j in range(i + 1, n):
            a1, a2 = entries[i][1], entries[j][1]
            if len(a1) != length or len(a2) != length:
                continue
            pairs.append((entries[i][0], entries[j][0], a1, a2))
    if len(pairs) > max_pairs_per_family:
        random.Random(42).shuffle(pairs)
        pairs = pairs[:max_pairs_per_family]
    return pairs


def collect_all_families(homstad_dir: Path) -> List[Tuple[str, List[Tuple[str, str, str, str]]]]:
    """
    Durchsucht homstad_dir rekursiv nach *.ali, parst jede Datei,
    liefert [(family_name, list of (id1, id2, ref_ali1, ref_ali2)), ...].
    """
    results: List[Tuple[str, List[Tuple[str, str, str, str]]]] = []
    for ali_path in sorted(homstad_dir.rglob("*.ali")):
        try:
            entries = parse_ali_file(ali_path)
        except Exception as e:
            print(f"Skip {ali_path}: {e}")
            continue
        if len(entries) < 2:
            continue
        pairs = get_pairs_from_family(entries)
        if not pairs:
            continue
        family_name = ali_path.parent.name if ali_path.parent != homstad_dir else ali_path.stem
        results.append((family_name, pairs))
    return results
