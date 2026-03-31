#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# HOMSTRAD einlesen → 80/20 Split → alignment.jar → validateAli.jar → Werte + Plot
# Aufruf: python3 run_validation_homstrad.py [--homstrad-dir PFAD] [--max-pairs 60]
import argparse, random, subprocess, sys, tempfile#Imports
from pathlib import Path#Pfad-Objekt

ROOT = Path(__file__).resolve().parent.parent  # Projektroot (Skript liegt in src/)
JAR_ALI, JAR_VAL = ROOT / "alignment.jar", ROOT / "validateAli.jar"#JAR-Pfade
HOMSTRAD_DIR = ROOT / "HOMSTRAD"#HOMSTRAD-Ordner
MATRIX = ROOT / "MATRICES" / "dayhoff.mat" if (ROOT / "MATRICES" / "dayhoff.mat").exists() else ROOT / "MATRICES" / "blosum62.mat"#Substitutionsmatrix
OUT_PLOT = ROOT / "validation_plot.png"#Plot-Ausgabe


def _norm(s):#Sequenz normalisieren (Gaps, Zeichen)
    return "".join(c for c in s.replace("\r", "").replace("\n", "").replace(" ", "").replace("/", "-") if c in "ACDEFGHIKLMNPQRSTVWY-*").replace("*", "")#nur erlaubte Zeichen


def parse_ali(path):#Eine .ali Datei parsen
    """Eine .ali Datei → Liste (id, aligned_seq)."""
    text = path.read_text(encoding="utf-8", errors="replace")#Datei lesen
    entries, cur_id, cur = [], None, []#Einträge, aktuelle ID, Zeilenpuffer
    for line in text.splitlines():#Zeile für Zeile
        line = line.rstrip()#Leerzeichen rechts
        if not line.strip() or line.startswith("C;") or line.startswith("#"): continue#Leer/Kommentar überspringen
        if line.startswith(">P1;"):#Neuer Eintrag (PIR-Header)
            if cur_id and cur:#Vorherigen speichern
                seq = _norm("".join(cur))#Sequenz zusammensetzen
                if len(seq) > 10: entries.append((cur_id, seq))#mind. 10 Zeichen
            cur_id = line[4:].strip().split()[0] if line[4:].strip() else None#ID aus Header
            cur = []#Puffer leeren
            continue
        if cur_id:#Sequenzzeilen
            if "---*" in line or line.strip().endswith("*"):#Ende dieses Eintrags
                part = line.split("---*")[0] if "---*" in line else line.rstrip("*")#Teil bis Ende-Marker
                cur.append(_norm(part))#normalisiert anhängen
                seq = _norm("".join(cur))#komplette Sequenz
                if len(seq) > 10: entries.append((cur_id, seq))#speichern
                cur_id, cur = None, []#zurücksetzen
            else: cur.append(line)#Zeile anhängen
    if cur_id and cur:#Letzten Eintrag speichern
        seq = _norm("".join(cur))
        if len(seq) > 10: entries.append((cur_id, seq))
    return entries#Liste (id, seq)


def collect_families(homstrad_dir, max_pairs_per_fam=50):#Alle Familien aus HOMSTRAD
    """Alle *.ali durchsuchen → [(family_name, [(id1,id2,ref1,ref2), ...]), ...]."""
    out = []#Ergebnisliste
    for ali_path in sorted(homstrad_dir.rglob("*.ali")):#alle .ali rekursiv
        try: entries = parse_ali(ali_path)#Datei parsen
        except Exception: continue#Fehler → überspringen
        if len(entries) < 2: continue#mind. 2 Einträge nötig
        L = len(entries[0][1])#MSA-Länge
        pairs = [(entries[i][0], entries[j][0], entries[i][1], entries[j][1])#alle Paare i<j
                 for i in range(len(entries)) for j in range(i + 1, len(entries))
                 if len(entries[i][1]) == L and len(entries[j][1]) == L]#gleiche Länge
        if len(pairs) > max_pairs_per_fam: random.Random(42).shuffle(pairs); pairs = pairs[:max_pairs_per_fam]#begrenzen
        if not pairs: continue
        name = ali_path.parent.name if ali_path.parent != homstrad_dir else ali_path.stem#Familienname
        out.append((name, pairs))#anhängen
    return out


def run_alignment(id1, id2, s1, s2, mat, go, ge):#alignment.jar aufrufen
    """alignment.jar: Paare + Seqlib → Kandidat (ali)."""
    s1, s2 = s1.replace("-", "").replace(".", ""), s2.replace("-", "").replace(".", "")#Gaps entfernen
    with tempfile.NamedTemporaryFile(mode="w", suffix=".s", delete=False) as f:#Seqlib temp
        f.write(f"{id1}: {s1}\n{id2}: {s2}\n"); sl = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".p", delete=False) as f:#Pairs temp
        f.write(f"{id1} {id2}\n"); pa = f.name
    try:
        r = subprocess.run(["java", "-jar", str(JAR_ALI), "--pairs", pa, "--seqlib", sl, "-m", str(mat),#JAR starten
            "--go", str(go), "--ge", str(ge), "--mode", "global", "--format", "ali"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=120)
        if r.returncode != 0: return None, None#Fehler
        L = [l.strip() for l in r.stdout.strip().split("\n") if l.strip()]#Ausgabe zeilenweise
        if len(L) < 3: return None, None#zu wenig Zeilen
        def seq(l): i = l.find(": "); return l[i+2:].strip() if i >= 0 else ""#Sequenz nach ":"
        a1, a2 = seq(L[1]), seq(L[2])#Kandidat-Sequenzen
        return (a1, a2) if a1 and a2 and len(a1) == len(a2) else (None, None)#oder Fehler
    finally: Path(sl).unlink(missing_ok=True); Path(pa).unlink(missing_ok=True)#Temp löschen


def run_validate(content):#validateAli.jar aufrufen
    """validateAli.jar -f: Block (Kandidat+Ref) → sens, spec, cov, mse."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:#Input temp
        f.write(content); p = f.name
    try:
        r = subprocess.run(["java", "-jar", str(JAR_VAL), "-f", p], cwd=str(ROOT), capture_output=True, text=True, timeout=60)#JAR
        if r.returncode != 0: return []#Fehler
        out = []#Ergebnis
        for line in r.stdout.splitlines():#jede Zeile
            if not line.strip().startswith(">"): continue#nur Header-Zeilen
            P = line[1:].strip().split()#Teile nach ">"
            if len(P) < 5: continue#sens, spec, cov, invMse, mse
            try: out.append({"sensitivity": float(P[-5]), "specificity": float(P[-4]), "coverage": float(P[-3]), "mse": float(P[-1])})#Metriken
            except (ValueError, IndexError): pass#ungültig überspringen
        return out
    finally: Path(p).unlink(missing_ok=True)#Temp löschen


def main():#Hauptablauf
    p = argparse.ArgumentParser(description="HOMSTRAD 80/20 → Alignment → ValidateAli → Plot")#Parser
    p.add_argument("--homstrad-dir", type=Path, default=HOMSTRAD_DIR)#HOMSTRAD-Pfad
    p.add_argument("--max-pairs", type=int, default=60)#max. Paare
    p.add_argument("--go", type=int, default=-12); p.add_argument("--ge", type=int, default=-1)#Gap-Kosten
    args = p.parse_args()#einlesen
    if not JAR_ALI.exists(): print("alignment.jar fehlt", file=sys.stderr); sys.exit(1)#Prüfung
    if not JAR_VAL.exists(): print("validateAli.jar fehlt", file=sys.stderr); sys.exit(1)
    if not args.homstrad_dir.exists(): print("HOMSTRAD fehlt:", args.homstrad_dir, file=sys.stderr); sys.exit(1)
    if not MATRIX.exists(): print("Matrix fehlt (MATRICES/)", file=sys.stderr); sys.exit(1)

    families = collect_families(args.homstrad_dir)#HOMSTRAD laden
    random.Random(42).shuffle(families)#80/20: mischen (reproduzierbar)
    split = max(1, int(0.8 * len(families)))#80 % Grenze
    train_fam, test_fam = families[:split], families[split:]#aufteilen
    train_pairs = [p for _, pairs in train_fam for p in pairs]#alle Train-Paare
    test_pairs = [p for _, pairs in test_fam for p in pairs]#alle Test-Paare
    print(f"80% Train: {len(train_fam)} Fam, {len(train_pairs)} Paare | 20% Test: {len(test_fam)} Fam, {len(test_pairs)} Paare")#Ausgabe
    pairs = test_pairs#nur Test validieren
    if len(pairs) > args.max_pairs: random.Random(43).shuffle(pairs := list(pairs)); pairs = pairs[:args.max_pairs]#begrenzen
    print(f"Validiere {len(pairs)} Paare ...")

    all_b = []#alle Validierungsblöcke
    for i, (id1, id2, r1, r2) in enumerate(pairs):#pro Paar
        c1, c2 = run_alignment(id1, id2, r1, r2, MATRIX, args.go, args.ge)#Alignment
        if c1 is None: continue#Fehler überspringen
        all_b.extend(run_validate(f">{id1}_{id2}\n{id1}: {c1}\n{id2}: {c2}\n{id1}: {r1}\n{id2}: {r2}\n"))#ValidateAli-Format: Kandidat+Ref
        if (i + 1) % 20 == 0: print(f"  {i+1}/{len(pairs)}")#Fortschritt
    if not all_b: print("Keine Ergebnisse"); sys.exit(1)#nichts rausgekommen

    n = len(all_b)#Anzahl
    sens = [b["sensitivity"] for b in all_b]; spec = [b["specificity"] for b in all_b]#Listen
    cov = [b["coverage"] for b in all_b]; mse = [b["mse"] for b in all_b]
    print(f"\n--- ValidateAli: n={n} ---\nSensitivity  Mittel {sum(sens)/n:.4f} (Min {min(sens):.4f}, Max {max(sens):.4f})")#Ausgabe
    print(f"Specificity  Mittel {sum(spec)/n:.4f} (Min {min(spec):.4f}, Max {max(spec):.4f})\nCoverage {sum(cov)/n:.4f}  MSE {sum(mse)/n:.4f}")

    try:#Plot
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt#Backend + pyplot
        plt.figure(figsize=(6, 5))#Größe
        plt.scatter(sens, spec, alpha=0.6, s=30, c="steelblue")#Punkte
        plt.xlabel("Sensitivity"); plt.ylabel("Specificity"); plt.title("HOMSTRAD 80/20: Sens vs Spec")#Achsen
        plt.axhline(sum(spec)/n, color="gray", linestyle="--", alpha=0.6); plt.axvline(sum(sens)/n, color="gray", linestyle=":", alpha=0.6)#Mittellinien
        plt.grid(True, alpha=0.3); plt.tight_layout(); plt.savefig(OUT_PLOT, dpi=150, bbox_inches="tight"); plt.close()#speichern
        print(f"Plot: {OUT_PLOT}")
    except ImportError: print("Matplotlib fehlt → pip install matplotlib")#Fallback


if __name__ == "__main__": main()#Start
