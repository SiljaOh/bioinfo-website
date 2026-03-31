#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bonus Parameter Tuning: Testet verschiedene --go/--ge auf einem Validierungsset
und wählt die beste Einstellung (nach mittlerer Sensitivity).
Usage:
  python3 tune_params.py --pairs pairs.txt --seqlib seqlib.txt -m dayhoff.mat \\
    --ref validation_ref.ali [--go-list -14 -12 -10] [--ge-list -2 -1]
"""
import argparse
import subprocess
import sys
import tempfile
import os


def _id_from_seq_line(line):
    """Extrahiert ID aus Zeile 'Id: Sequenz' (oder 'Id:Sequenz')."""
    if ":" in line:
        return line.split(":", 1)[0].strip()
    return line.split(None, 1)[0].strip() if line else None


def read_ref_blocks(path):
    """Liest Referenz-Datei (ValidateAli-Format); liefert pro (id1, id2) die Zeilen 3 und 4 (Referenz).
    Key = (id1, id2) aus den ersten beiden Sequenzzeilen (vor ':'), nicht aus dem Header."""
    blocks = {}
    with open(path, "r", encoding="utf-8") as f:
        header = None
        line1 = line2 = line3 = line4 = None
        for raw in f:
            line = raw.rstrip()
            if line.startswith(">"):
                if header is not None and line1 is not None and line2 is not None and line3 is not None and line4 is not None:
                    id1 = _id_from_seq_line(line1)
                    id2 = _id_from_seq_line(line2)
                    if id1 and id2:
                        blocks[(id1, id2)] = (line3, line4)
                header = line
                line1 = line2 = line3 = line4 = None
                continue
            if line1 is None:
                line1 = line
            elif line2 is None:
                line2 = line
            elif line3 is None:
                line3 = line
            elif line4 is None:
                line4 = line
        if header is not None and line1 is not None and line2 is not None and line3 is not None and line4 is not None:
            id1 = _id_from_seq_line(line1)
            id2 = _id_from_seq_line(line2)
            if id1 and id2:
                blocks[(id1, id2)] = (line3, line4)
    return blocks


def run_align(jar, pairs_path, seqlib_path, matrix_path, go, ge, mode="global", algorithm="gotoh", cwd=None):
    """Führt alignment.jar aus, liefert stdout (ali-Format). algorithm: gotoh | nw."""
    cmd = [
        "java", "-jar", jar,
        "--pairs", str(pairs_path), "--seqlib", str(seqlib_path), "-m", str(matrix_path),
        "--go", str(go), "--ge", str(ge), "--mode", mode, "--format", "ali"
    ]
    if algorithm == "nw":
        # --nw als eigenständiges Flag vor --format einfügen
        idx = cmd.index("--format") if "--format" in cmd else len(cmd)
        cmd.insert(idx, "--nw")
    r = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=120, universal_newlines=True)
    if r.returncode != 0:
        return None, r.stderr or r.stdout
    return r.stdout, None


def merge_with_ref(ali_stdout, ref_blocks):
    """Kombiniert Alignment-Ausgabe (Header + Zeile1, Zeile2) mit Referenz (Zeile3, Zeile4) zu ValidateAli-Input."""
    out = []
    block = []
    for raw in ali_stdout.splitlines():
        line = raw.rstrip()
        if line.startswith(">"):
            if block:
                if len(block) >= 3:  # header + line1 + line2
                    parts = block[0][1:].strip().split()
                    if len(parts) >= 2:
                        key = (parts[0], parts[1])
                        if key in ref_blocks:
                            ref3, ref4 = ref_blocks[key]
                            out.append(block[0])
                            out.append(block[1])
                            out.append(block[2])
                            out.append(ref3)
                            out.append(ref4)
                block = []
            block.append(line)
        elif block and len(block) == 1:
            block.append(line)
        elif block and len(block) == 2:
            block.append(line)
    if block and len(block) >= 3:
        parts = block[0][1:].strip().split()
        if len(parts) >= 2:
            key = (parts[0], parts[1])
            if key in ref_blocks:
                ref3, ref4 = ref_blocks[key]
                out.append(block[0])
                out.append(block[1])
                out.append(block[2])
                out.append(ref3)
                out.append(ref4)
    return "\n".join(out) + "\n" if out else ""


def run_validate(jar, input_content, cwd=None):
    """Führt validateAli.jar aus; liefert stdout (Header-Zeilen mit Scores)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ali", delete=False, encoding="utf-8") as f:
        f.write(input_content)
        f.flush()
        try:
            r = subprocess.run(["java", "-jar", jar, "-f", f.name], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, universal_newlines=True)
            if r.returncode != 0:
                return None, r.stderr or r.stdout
            return r.stdout, None
        finally:
            os.unlink(f.name)


def parse_validation_metrics(validate_stdout):
    """Extrahiert aus ValidateAli-Ausgabe pro Block sens, spec; liefert (mean_sens, mean_spec, mean_f1). F1 = 2*sens*spec/(sens+spec)."""
    sens_list = []
    spec_list = []
    f1_list = []
    if not (validate_stdout or isinstance(validate_stdout, str)):
        return float("nan"), float("nan"), float("nan")
    for line in (validate_stdout or "").splitlines():
        if line.strip().startswith(">"):
            parts = line[1:].strip().split()
            if len(parts) >= 5:
                try:
                    s = float(parts[-5])
                    p = float(parts[-4])
                    sens_list.append(s)
                    spec_list.append(p)
                    if s + p > 0:
                        f1_list.append(2.0 * s * p / (s + p))
                    else:
                        f1_list.append(0.0)
                except (ValueError, IndexError):
                    pass
    mean_sens = sum(sens_list) / len(sens_list) if sens_list else float("nan")
    mean_spec = sum(spec_list) / len(spec_list) if spec_list else float("nan")
    mean_f1 = sum(f1_list) / len(f1_list) if f1_list else float("nan")
    return mean_sens, mean_spec, mean_f1


def main():
    ap = argparse.ArgumentParser(description="Parameter Tuning für Alignment (--go/--ge)")
    ap.add_argument("--pairs", required=True, help="Pairs-Datei")
    ap.add_argument("--seqlib", required=True, help="Seqlib-Datei")
    ap.add_argument("-m", "--matrix", required=True, dest="matrix", help="Substitutionsmatrix")
    ap.add_argument("--ref", required=True, help="Referenz-Datei (ValidateAli-Format, 5 Zeilen pro Block)")
    ap.add_argument("--go-list", nargs="+", type=int, default=[-14, -12, -10], help="Gap-Open-Werte")
    ap.add_argument("--ge-list", nargs="+", type=int, default=[-2, -1], help="Gap-Extend-Werte")
    ap.add_argument("--alignment-jar", default="alignment.jar", help="Pfad zu alignment.jar")
    ap.add_argument("--validate-jar", default="validateAli.jar", help="Pfad zu validateAli.jar")
    ap.add_argument("--mode", default="global", choices=["global", "local", "freeshift"])
    ap.add_argument("--algorithm", default="auto", choices=["gotoh", "nw", "auto"],
                    help="gotoh = nur Gotoh, nw = nur NW, auto = v.a. Gotoh, wenig NW")
    args = ap.parse_args()

    base = os.path.dirname(os.path.abspath(args.alignment_jar)) if os.path.isfile(args.alignment_jar) else "."
    align_jar = args.alignment_jar if os.path.isabs(args.alignment_jar) or os.path.isfile(args.alignment_jar) else os.path.join(base, "alignment.jar")
    val_jar = args.validate_jar if os.path.isabs(args.validate_jar) or os.path.isfile(args.validate_jar) else os.path.join(base, "validateAli.jar")

    ref_blocks = read_ref_blocks(args.ref)
    if not ref_blocks:
        print("Keine Referenz-Blöcke in --ref gefunden.", file=sys.stderr)
        sys.exit(1)

    # Bei auto: für jedes (go, ge) Gotoh; für jedes 4. (go, ge) zusätzlich NW (wenig NW, oft Gotoh)
    combos = [(go, ge) for go in args.go_list for ge in args.ge_list]
    if args.algorithm == "auto":
        run_list = []
        for i, (go, ge) in enumerate(combos):
            run_list.append((go, ge, "gotoh"))
            if i % 4 == 0:
                run_list.append((go, ge, "nw"))
    elif args.algorithm == "nw":
        run_list = [(go, ge, "nw") for go, ge in combos]
    else:
        run_list = [(go, ge, "gotoh") for go, ge in combos]

    best_go = best_ge = best_algo = None
    best_f1 = -1.0
    results = []

    for go, ge, algo in run_list:
        ali_out, err = run_align(align_jar, args.pairs, args.seqlib, args.matrix, go, ge, args.mode, algorithm=algo, cwd=base)
        if err:
            print(f"Alignment fehlgeschlagen go={go} ge={ge} algo={algo}: {err[:200]}", file=sys.stderr)
            results.append((go, ge, algo, float("nan"), float("nan"), float("nan")))
            continue
        merged = merge_with_ref(ali_out, ref_blocks)
        if not merged.strip():
            print(f"Warnung: Kein überlappender Output für go={go} ge={ge} algo={algo}", file=sys.stderr)
            results.append((go, ge, algo, float("nan"), float("nan"), float("nan")))
            continue
        val_out, err = run_validate(val_jar, merged, cwd=base)
        if err:
            print(f"Validate fehlgeschlagen go={go} ge={ge} algo={algo}: {err[:200]}", file=sys.stderr)
            results.append((go, ge, algo, float("nan"), float("nan"), float("nan")))
            continue
        mean_sens, mean_spec, mean_f1 = parse_validation_metrics(val_out)
        results.append((go, ge, algo, mean_sens, mean_spec, mean_f1))
        if mean_f1 == mean_f1 and mean_f1 > best_f1:
            best_f1 = mean_f1
            best_go, best_ge, best_algo = go, ge, algo

    print("go\tge\talgorithm\tmean_sensitivity\tmean_specificity\tmean_f1")
    for r in results:
        go, ge, algo, sens, spec, f1 = r[0], r[1], r[2], r[3], r[4], r[5]
        print(f"{go}\t{ge}\t{algo}\t{sens}\t{spec}\t{f1}")
    print()
    # Guter Bereich: alle Zeilen mit F1 im oberen Bereich (z. B. >= 90 % des Max)
    valid_f1 = [r for r in results if r[5] == r[5]]
    if valid_f1:
        max_f1 = max(r[5] for r in valid_f1)
        threshold = max_f1 * 0.9 if max_f1 > 0 else 0
        good = [r for r in results if r[5] == r[5] and r[5] >= threshold]
        print(f"Guter Bereich (F1 >= {threshold:.2f}):")
        for r in good:
            print(f"  --go {r[0]} --ge {r[1]} --algorithm {r[2]}  (F1 = {r[5]:.4f}, Sens = {r[3]:.4f}, Spec = {r[4]:.4f})")
    else:
        print("Keine gültigen F1-Werte.")


if __name__ == "__main__":
    main()
