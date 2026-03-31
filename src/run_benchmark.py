# -*- coding: utf-8 -*-
"""
HOMSTRAD Correlations Benchmark: Liest alle .ali, splittet Train/Test,
führt Alignment mit verschiedenen Parametern aus, berechnet Metriken und erstellt Plots.
Aufruf: python run_benchmark.py [--project-root /path/to/alignment] [--quick]
"""

import argparse
import csv
import subprocess
import sys
import tempfile
from pathlib import Path

from homstad_parser import collect_all_families, get_pairs_from_family, parse_ali_file
from validation_metrics import compute_all_metrics

# Projektroot (enthält alignment.jar, MATRICES/, HOMSTRAD/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
HOMSTRAD_DIR = PROJECT_ROOT / "HOMSTRAD"
MATRICES_DIR = PROJECT_ROOT / "MATRICES"
JAR = PROJECT_ROOT / "alignment.jar"
PLOTS_DIR = PROJECT_ROOT / "plots"


def ungapped(seq: str) -> str:
    return seq.replace("-", "")


def run_aligner(seq1: str, seq2: str, id1: str, id2: str, matrix_path: Path, go: int, ge: int, mode: str, java_jar: Path, use_nw: bool = False) -> tuple:
    """
    Führt alignment.Main aus, liefert (cand_ali1, cand_ali2) oder (None, None) bei Fehler.
    use_nw=True: Needleman-Wunsch (lineare Gaps) statt Gotoh.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f_seqlib:
        f_seqlib.write(f"{id1}: {ungapped(seq1)}\n")
        f_seqlib.write(f"{id2}: {ungapped(seq2)}\n")
        seqlib_path = f_seqlib.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f_pairs:
        f_pairs.write(f"{id1} {id2}\n")
        pairs_path = f_pairs.name

    try:
        cmd = [
            "java", "-jar", str(java_jar),
            "--pairs", pairs_path,
            "--seqlib", seqlib_path,
            "-m", str(matrix_path),
            "--go", str(go),
            "--ge", str(ge),
            "--mode", mode,
            "--format", "ali",
        ]
        if use_nw:
            cmd.insert(cmd.index("--mode"), "--nw")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(PROJECT_ROOT))
        out = result.stdout
        if result.returncode != 0:
            return None, None
        lines = [l.strip() for l in out.strip().split("\n") if l.strip()]
        # Erwartung: ">id1 id2 score", "id1: aligned1", "id2: aligned2"
        if len(lines) < 3:
            return None, None
        def extract_ali(line: str) -> str:
            idx = line.find(": ")
            if idx >= 0:
                return line[idx + 2:].strip()
            return ""
        a1 = extract_ali(lines[1])
        a2 = extract_ali(lines[2])
        if not a1 or not a2 or len(a1) != len(a2):
            return None, None
        return a1, a2
    except Exception as e:
        return None, None
    finally:
        Path(seqlib_path).unlink(missing_ok=True)
        Path(pairs_path).unlink(missing_ok=True)


def main():
    global PROJECT_ROOT, HOMSTRAD_DIR, MATRICES_DIR, JAR, PLOTS_DIR
    parser = argparse.ArgumentParser(description="HOMSTRAD Correlations Benchmark")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT, help="Projektverzeichnis mit alignment.jar, HOMSTRAD/, MATRICES/")
    parser.add_argument("--quick", action="store_true", help="Schnelllauf: wenige Familien und Paare (~2–3 Min)")
    parser.add_argument("--test-only", action="store_true", help="Nur Test-Set verwenden (nach Split)")
    parser.add_argument("--max-pairs", type=int, default=300, metavar="N", help="Max. Anzahl Paare (Standard 300)")
    parser.add_argument("--all-pairs", action="store_true", help="Alle Paare verwenden (kann sehr lange dauern)")
    parser.add_argument("--full-grid", action="store_true", help="Volles Parameter-Grid (5 Gap-Open, 2 Gap-Extend)")
    args = parser.parse_args()

    PROJECT_ROOT = args.project_root
    HOMSTRAD_DIR = PROJECT_ROOT / "HOMSTRAD"
    MATRICES_DIR = PROJECT_ROOT / "MATRICES"
    JAR = PROJECT_ROOT / "alignment.jar"
    PLOTS_DIR = PROJECT_ROOT / "plots"

    if not JAR.exists():
        print("alignment.jar nicht gefunden. Bitte zuerst ./build/build.sh ausführen.", file=sys.stderr)
        sys.exit(1)
    if not HOMSTRAD_DIR.exists():
        print("HOMSTRAD/ nicht gefunden.", file=sys.stderr)
        sys.exit(1)

    # Familien laden und in Train/Test splitten (80/20)
    print("Lade HOMSTRAD-Familien...")
    families = collect_all_families(HOMSTRAD_DIR)
    if args.quick:
        families = families[:12]
    rng = __import__("random").Random(42)
    rng.shuffle(families)
    split_idx = max(1, int(0.8 * len(families)))
    train_families, test_families = families[:split_idx], families[split_idx:]
    train_pairs: list = []
    for _, pairs in train_families:
        train_pairs.extend(pairs)
    test_pairs: list = []
    for _, pairs in test_families:
        test_pairs.extend(pairs)

    print(f"Train: {len(train_families)} Familien, {len(train_pairs)} Paare. Test: {len(test_families)} Familien, {len(test_pairs)} Paare.")

    # Parameter-Grid (Standard: reduziert für kürzere Laufzeit)
    matrices = [
        ("BLOSUM62", MATRICES_DIR / "blosum62.mat"),
        ("PAM250", MATRICES_DIR / "pam250.mat"),
        ("Dayhoff", MATRICES_DIR / "dayhoff.mat"),
    ]
    matrices = [(n, p) for n, p in matrices if p.exists()]
    if not matrices:
        print("Keine Substitutionsmatrizen in MATRICES/ gefunden.", file=sys.stderr)
        sys.exit(1)

    if args.full_grid:
        gap_opens = [-20, -15, -12, -10, -8]
        gap_extends = [-2, -1]
    elif args.quick:
        gap_opens = [-15, -12]
        gap_extends = [-1]
    else:
        # Standard: kleineres Grid, trotzdem aussagekräftige Plots
        gap_opens = [-15, -12, -8]
        gap_extends = [-1]
    # Gotoh (global, local, freeshift) + Needleman-Wunsch (nw_global) zum Vergleich
    algorithms = [
        ("global", "global", False),
        ("local", "local", False),
        ("freeshift", "freeshift", False),
        ("nw_global", "global", True),
    ]
    mode_keys = [a[0] for a in algorithms]

    # Welche Paare bewerten (Standard: 300 Paare für aussagekräftige, nicht zu lange Läufe)
    pairs_to_run = test_pairs if args.test_only else (train_pairs + test_pairs)
    if args.quick:
        pairs_to_run = pairs_to_run[:40]
    elif not args.all_pairs:
        max_p = max(1, args.max_pairs)
        if len(pairs_to_run) > max_p:
            rng = __import__("random").Random(42)
            pairs_copy = list(pairs_to_run)
            rng.shuffle(pairs_copy)
            pairs_to_run = pairs_copy[:max_p]
            print(f"Es werden {max_p} zufällige Paare verwendet (--all-pairs für alle {len(pairs_copy)}).")

    # Ergebnisse: pro (mode, matrix, go, ge) Aggregation über alle Paare
    results: list = []
    total_runs = len(pairs_to_run) * len(algorithms) * len(matrices) * len(gap_opens) * len(gap_extends)
    print(f"Läufe: {len(pairs_to_run)} Paare × {len(algorithms)} Algorithmen × {len(matrices)} Matrizen × {len(gap_opens)} Gap-Open × {len(gap_extends)} Gap-Extend = {total_runs}")
    run_count = 0

    for mode_key, java_mode, use_nw in algorithms:
        for matrix_name, matrix_path in matrices:
            for go in gap_opens:
                for ge in gap_extends:
                    sens_list, spec_list, mse_list, inv_list = [], [], [], []
                    for (id1, id2, ref_a1, ref_a2) in pairs_to_run:
                        run_count += 1
                        if run_count % 500 == 0:
                            print(f"  {run_count}/{total_runs} ...")
                        cand_a1, cand_a2 = run_aligner(ref_a1, ref_a2, id1, id2, matrix_path, go, ge, java_mode, JAR, use_nw=use_nw)
                        if cand_a1 is None:
                            continue
                        m = compute_all_metrics(ref_a1, ref_a2, cand_a1, cand_a2)
                        sens_list.append(m["sensitivity"])
                        spec_list.append(m["specificity"])
                        mse_list.append(m["mean_shift_error"])
                        inv_list.append(m["inverse_mean_shift_error"])
                    if sens_list:
                        n = len(sens_list)
                        results.append({
                            "mode": mode_key,
                            "matrix": matrix_name,
                            "gap_open": go,
                            "gap_extend": ge,
                            "n_pairs": n,
                            "avg_sensitivity": sum(sens_list) / n,
                            "avg_specificity": sum(spec_list) / n,
                            "avg_mse": sum(mse_list) / n,
                            "avg_inv_mse": sum(inv_list) / n,
                        })

    # CSV speichern
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = PLOTS_DIR / "benchmark_results.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["mode", "matrix", "gap_open", "gap_extend", "n_pairs",
                                          "avg_sensitivity", "avg_specificity", "avg_mse", "avg_inv_mse"])
        w.writeheader()
        w.writerows(results)
    print(f"Ergebnisse: {out_csv}")

    # Plots erstellen
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("Matplotlib nicht installiert. Plots werden übersprungen. Bitte: pip install matplotlib")
        return

    _create_plots(results, gap_opens, gap_extends, matrices, mode_keys)
    print(f"Plots gespeichert in: {PLOTS_DIR}")

    # Kopie nach report/plots/ und web/plots/ für statische Webseite
    import shutil
    for dest_dir in [PROJECT_ROOT / "report" / "plots", PROJECT_ROOT / "web" / "plots"]:
        if dest_dir.parent.exists():
            dest_dir.mkdir(parents=True, exist_ok=True)
            for f in PLOTS_DIR.glob("*.png"):
                shutil.copy2(f, dest_dir / f.name)
            print(f"Plots nach {dest_dir} kopiert.")


def _create_plots(results: list, gap_opens: list, gap_extends: list, matrices: list, modes: list):
    import matplotlib.pyplot as plt
    import numpy as np

    # 1) Sensitivity & Specificity vs Gap Open (pro Mode, pro Matrix, ge=-1)
    for mode in modes:
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))
        for matrix_name, _ in matrices:
            for ge in gap_extends:
                subset = [r for r in results if r["mode"] == mode and r["matrix"] == matrix_name and r["gap_extend"] == ge]
                if not subset:
                    continue
                subset = sorted(subset, key=lambda x: x["gap_open"])
                x = [r["gap_open"] for r in subset]
                ax = axes[0]
                ax.plot(x, [r["avg_sensitivity"] for r in subset], "-o", label=f"{matrix_name} ge={ge}", markersize=4)
                ax = axes[1]
                ax.plot(x, [r["avg_specificity"] for r in subset], "-s", label=f"{matrix_name} ge={ge}", markersize=4)
        axes[0].set_xlabel("Gap open cost")
        axes[0].set_ylabel("Avg. Sensitivity")
        axes[0].set_title(f"Mode: {mode}")
        axes[0].legend(loc="best", fontsize=8)
        axes[0].grid(True, alpha=0.3)
        axes[1].set_xlabel("Gap open cost")
        axes[1].set_ylabel("Avg. Specificity")
        axes[1].set_title(f"Mode: {mode}")
        axes[1].legend(loc="best", fontsize=8)
        axes[1].grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(PLOTS_DIR / f"plot_sensitivity_specificity_vs_gapopen_{mode}.png", dpi=150, bbox_inches="tight")
        plt.close()

    # 2) Avg. Mean Shift Error vs Gap Open (pro Mode)
    for mode in modes:
        plt.figure(figsize=(7, 4))
        for matrix_name, _ in matrices:
            for ge in gap_extends:
                subset = [r for r in results if r["mode"] == mode and r["matrix"] == matrix_name and r["gap_extend"] == ge]
                if not subset:
                    continue
                subset = sorted(subset, key=lambda x: x["gap_open"])
                plt.plot([r["gap_open"] for r in subset], [r["avg_mse"] for r in subset], "-o", label=f"{matrix_name} ge={ge}", markersize=4)
        plt.xlabel("Gap open cost")
        plt.ylabel("Avg. Mean Shift Error")
        plt.title(f"Avg. Mean Shift Error vs Gap Open — {mode}")
        plt.legend(loc="best", fontsize=8)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(PLOTS_DIR / f"plot_avg_mse_vs_gapopen_{mode}.png", dpi=150, bbox_inches="tight")
        plt.close()

    # 3) Korrelation: Sensitivity vs Specificity (alle Konfigurationen, ein Punkt = eine Konfiguration)
    plt.figure(figsize=(6, 5))
    for mode in modes:
        subset = [r for r in results if r["mode"] == mode]
        if not subset:
            continue
        plt.scatter([r["avg_sensitivity"] for r in subset], [r["avg_specificity"] for r in subset],
                    label=mode, alpha=0.6, s=25)
    plt.xlabel("Avg. Sensitivity")
    plt.ylabel("Avg. Specificity")
    plt.title("Correlation: Sensitivity vs Specificity")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "plot_correlation_sensitivity_specificity.png", dpi=150, bbox_inches="tight")
    plt.close()

    # 4) Korrelation: Avg. MSE vs Avg. inverse MSE
    plt.figure(figsize=(6, 5))
    for mode in modes:
        subset = [r for r in results if r["mode"] == mode]
        if not subset:
            continue
        plt.scatter([r["avg_mse"] for r in subset], [r["avg_inv_mse"] for r in subset], label=mode, alpha=0.6, s=25)
    plt.xlabel("Avg. Mean Shift Error")
    plt.ylabel("Avg. Inverse Mean Shift Error")
    plt.title("Correlation: Avg. MSE vs Avg. Inverse MSE")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "plot_correlation_mse_invmse.png", dpi=150, bbox_inches="tight")
    plt.close()

    # 5) Global: alle Matrizen, ge=-1 — Sensitivity & Specificity in einem (Übersicht wie im Text)
    fig, ax = plt.subplots(figsize=(8, 5))
    for matrix_name, _ in matrices:
        subset = [r for r in results if r["mode"] == "global" and r["matrix"] == matrix_name and r["gap_extend"] == -1]
        if not subset:
            continue
        subset = sorted(subset, key=lambda x: x["gap_open"])
        x = [r["gap_open"] for r in subset]
        ax.plot(x, [r["avg_sensitivity"] for r in subset], "-o", label=f"{matrix_name} (Sens)", markersize=5)
        ax.plot(x, [r["avg_specificity"] for r in subset], "--s", label=f"{matrix_name} (Spec)", markersize=5)
    ax.set_xlabel("Gap open cost (gap extend = -1)")
    ax.set_ylabel("Metric value")
    ax.set_title("Global Gotoh: Sensitivity and Specificity vs Gap Open")
    ax.legend(loc="best", fontsize=8, ncol=2)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "plot_global_sensitivity_specificity_overview.png", dpi=150, bbox_inches="tight")
    plt.close()


if __name__ == "__main__":
    main()
