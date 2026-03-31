#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# HOMSTRAD 80/20 → für jede (GO, GE)-Kombination Alignment + Validate → 6 3D-Plots
# Sens, Spec, MSE, IMSE, Coverage, F1 über GO (0 bis -20, Schritt 5) und GE (0 bis -5, Schritt 1)
# Global Gotoh, Dayhoff-Matrix

import argparse
import random
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
JAR_ALI = ROOT / "alignment.jar"
JAR_VAL = ROOT / "validateAli.jar"
HOMSTRAD_DIR = ROOT / "HOMSTRAD"
MATRIX = ROOT / "MATRICES" / "dayhoff.mat"
if not MATRIX.exists():
    MATRIX = ROOT / "MATRICES" / "blosum62.mat"
OUT_DIR = ROOT / "plots_3d"
GO_VALUES = [0, -5, -10, -15, -20]   # 5 Werte
GE_VALUES = [0, -1, -2, -3, -4, -5]   # 6 Werte


def _norm(s):
    return "".join(
        c for c in s.replace("\r", "").replace("\n", "").replace(" ", "").replace("/", "-")
        if c in "ACDEFGHIKLMNPQRSTVWY-*"
    ).replace("*", "")


def parse_ali(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    entries, cur_id, cur = [], None, []
    for line in text.splitlines():
        line = line.rstrip()
        if not line.strip() or line.startswith("C;") or line.startswith("#"):
            continue
        if line.startswith(">P1;"):
            if cur_id and cur:
                seq = _norm("".join(cur))
                if len(seq) > 10:
                    entries.append((cur_id, seq))
            cur_id = line[4:].strip().split()[0] if line[4:].strip() else None
            cur = []
            continue
        if cur_id:
            if "---*" in line or line.strip().endswith("*"):
                part = line.split("---*")[0] if "---*" in line else line.rstrip("*")
                cur.append(_norm(part))
                seq = _norm("".join(cur))
                if len(seq) > 10:
                    entries.append((cur_id, seq))
                cur_id, cur = None, []
            else:
                cur.append(line)
    if cur_id and cur:
        seq = _norm("".join(cur))
        if len(seq) > 10:
            entries.append((cur_id, seq))
    return entries


def collect_families(homstrad_dir, max_pairs_per_fam=50):
    out = []
    for ali_path in sorted(homstrad_dir.rglob("*.ali")):
        try:
            entries = parse_ali(ali_path)
        except Exception:
            continue
        if len(entries) < 2:
            continue
        L = len(entries[0][1])
        pairs = [
            (entries[i][0], entries[j][0], entries[i][1], entries[j][1])
            for i in range(len(entries))
            for j in range(i + 1, len(entries))
            if len(entries[i][1]) == L and len(entries[j][1]) == L
        ]
        if len(pairs) > max_pairs_per_fam:
            random.Random(42).shuffle(pairs)
            pairs = pairs[:max_pairs_per_fam]
        if not pairs:
            continue
        name = ali_path.parent.name if ali_path.parent != homstrad_dir else ali_path.stem
        out.append((name, pairs))
    return out


def run_alignment(id1, id2, s1, s2, mat, go, ge):
    s1 = s1.replace("-", "").replace(".", "")
    s2 = s2.replace("-", "").replace(".", "")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".s", delete=False) as f:
        f.write(f"{id1}: {s1}\n{id2}: {s2}\n")
        sl = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".p", delete=False) as f:
        f.write(f"{id1} {id2}\n")
        pa = f.name
    try:
        r = subprocess.run(
            [
                "java", "-jar", str(JAR_ALI),
                "--pairs", pa, "--seqlib", sl, "-m", str(mat),
                "--go", str(go), "--ge", str(ge), "--mode", "global", "--format", "ali",
            ],
            cwd=str(ROOT), capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0:
            return None, None
        lines = [l.strip() for l in r.stdout.strip().split("\n") if l.strip()]
        if len(lines) < 3:
            return None, None
        def seq(l):
            i = l.find(": ")
            return l[i + 2:].strip() if i >= 0 else ""
        a1, a2 = seq(lines[1]), seq(lines[2])
        return (a1, a2) if a1 and a2 and len(a1) == len(a2) else (None, None)
    finally:
        Path(sl).unlink(missing_ok=True)
        Path(pa).unlink(missing_ok=True)


def run_validate(content):
    """Liefert pro Block: sensitivity, specificity, coverage, mse, inv_mse, f1."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(content)
        p = f.name
    try:
        r = subprocess.run(
            ["java", "-jar", str(JAR_VAL), "-f", p],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60,
        )
        if r.returncode != 0:
            return []
        out = []
        for line in r.stdout.splitlines():
            if not line.strip().startswith(">"):
                continue
            P = line[1:].strip().split()
            if len(P) < 5:
                continue
            try:
                sens = float(P[-5])
                spec = float(P[-4])
                cov = float(P[-3])
                inv_mse = float(P[-2])
                mse = float(P[-1])
                f1 = 2.0 * sens * spec / (sens + spec) if (sens + spec) > 0 else 0.0
                out.append({
                    "sensitivity": sens,
                    "specificity": spec,
                    "coverage": cov,
                    "mse": mse,
                    "inv_mse": inv_mse,
                    "f1": f1,
                })
            except (ValueError, IndexError):
                pass
        return out
    finally:
        Path(p).unlink(missing_ok=True)


def main():
    p = argparse.ArgumentParser(description="3D-Plots: Sens, Spec, MSE, IMSE, Coverage, F1 über GO/GE (Global Gotoh, Dayhoff)")
    p.add_argument("--homstrad-dir", type=Path, default=HOMSTRAD_DIR)
    p.add_argument("--max-pairs", type=int, default=60)
    args = p.parse_args()

    if not JAR_ALI.exists():
        print("alignment.jar fehlt", file=sys.stderr)
        sys.exit(1)
    if not JAR_VAL.exists():
        print("validateAli.jar fehlt", file=sys.stderr)
        sys.exit(1)
    if not args.homstrad_dir.exists():
        print("HOMSTRAD fehlt:", args.homstrad_dir, file=sys.stderr)
        sys.exit(1)
    if not MATRIX.exists():
        print("Dayhoff-Matrix fehlt (MATRICES/dayhoff.mat)", file=sys.stderr)
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    families = collect_families(args.homstrad_dir)
    random.Random(42).shuffle(families)
    split = max(1, int(0.8 * len(families)))
    train_fam, test_fam = families[:split], families[split:]
    test_pairs = [p for _, pairs in test_fam for p in pairs]
    if len(test_pairs) > args.max_pairs:
        random.Random(43).shuffle(test_pairs)
        test_pairs = test_pairs[:args.max_pairs]
    print(f"Test-Paare: {len(test_pairs)}. GO={GO_VALUES}, GE={GE_VALUES}")

    # Grid: (go, ge) -> Mittelwerte der 6 Metriken
    results = {}
    total_runs = len(GO_VALUES) * len(GE_VALUES)
    run_idx = 0
    for go in GO_VALUES:
        for ge in GE_VALUES:
            run_idx += 1
            print(f"  [{run_idx}/{total_runs}] GO={go}, GE={ge} ...", flush=True)
            blocks = []
            for id1, id2, r1, r2 in test_pairs:
                c1, c2 = run_alignment(id1, id2, r1, r2, MATRIX, go, ge)
                if c1 is None:
                    continue
                content = f">{id1}_{id2}\n{id1}: {c1}\n{id2}: {c2}\n{id1}: {r1}\n{id2}: {r2}\n"
                blocks.extend(run_validate(content))
            if not blocks:
                results[(go, ge)] = {
                    "sensitivity": 0.0, "specificity": 0.0, "coverage": 0.0,
                    "mse": 0.0, "inv_mse": 0.0, "f1": 0.0,
                }
            else:
                n = len(blocks)
                results[(go, ge)] = {
                    "sensitivity": sum(b["sensitivity"] for b in blocks) / n,
                    "specificity": sum(b["specificity"] for b in blocks) / n,
                    "coverage": sum(b["coverage"] for b in blocks) / n,
                    "mse": sum(b["mse"] for b in blocks) / n,
                    "inv_mse": sum(b["inv_mse"] for b in blocks) / n,
                    "f1": sum(b["f1"] for b in blocks) / n,
                }

    try:
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D
    except ImportError as e:
        print("Matplotlib/NumPy nötig: pip install matplotlib numpy", file=sys.stderr)
        sys.exit(1)

    # 2D-Arrays für Surface: Zeilen = GO, Spalten = GE
    go_arr = np.array(GO_VALUES)
    ge_arr = np.array(GE_VALUES)
    X, Y = np.meshgrid(go_arr, ge_arr, indexing="ij")
    Z_sens = np.array([[results[(go, ge)]["sensitivity"] for ge in GE_VALUES] for go in GO_VALUES])
    Z_spec = np.array([[results[(go, ge)]["specificity"] for ge in GE_VALUES] for go in GO_VALUES])
    Z_mse = np.array([[results[(go, ge)]["mse"] for ge in GE_VALUES] for go in GO_VALUES])
    Z_imse = np.array([[results[(go, ge)]["inv_mse"] for ge in GE_VALUES] for go in GO_VALUES])
    Z_cov = np.array([[results[(go, ge)]["coverage"] for ge in GE_VALUES] for go in GO_VALUES])
    Z_f1 = np.array([[results[(go, ge)]["f1"] for ge in GE_VALUES] for go in GO_VALUES])

    metrics = [
        ("sensitivity", Z_sens, "Sensitivity", "Sensitivity (GO, GE)"),
        ("specificity", Z_spec, "Specificity", "Specificity (GO, GE)"),
        ("mse", Z_mse, "MSE", "Mean Shift Error (GO, GE)"),
        ("imse", Z_imse, "IMSE", "Inverse Mean Shift Error (GO, GE)"),
        ("coverage", Z_cov, "Coverage", "Coverage (GO, GE)"),
        ("f1", Z_f1, "F1", "F1-Score (GO, GE)"),
    ]

    for key, Z, title, fig_title in metrics:
        fig = plt.figure(figsize=(9, 7))
        ax = fig.add_subplot(111, projection="3d")
        ax.plot_surface(X, Y, Z, cmap="viridis", alpha=0.9, edgecolor="none")
        ax.set_xlabel("Gap Open (GO)")
        ax.set_ylabel("Gap Extend (GE)")
        ax.set_zlabel(title)
        ax.set_title(f"Global Gotoh, Dayhoff — {fig_title}")
        out_path = OUT_DIR / f"plot_3d_{key}.png"
        plt.tight_layout()
        plt.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Gespeichert: {out_path}")

    print("Fertig. 6 Plots in", OUT_DIR)


if __name__ == "__main__":
    main()
