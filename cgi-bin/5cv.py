#!/usr/bin/python3
import sys
import subprocess
from pathlib import Path
import shutil
import re

k = 5
seclib_file = "CB513DSSP.db"
alignments_dir = "CB513MultipleAlignments"

#seclib rein
text = Path(seclib_file).read_text().strip()
entries = text.split("\n\n")

def get_seq(entry):
    for l in entry.split("\n"):
        if l.startswith("AS "):
            return l[3:].strip()

def get_id(entry):
    for l in entry.split("\n"):
        if l.startswith(">"):
            return l[1:].strip()

def seq_len(entry):
    return len(get_seq(entry))

#länge sortieren
entries.sort(key=seq_len)

#folds
folds = [[] for _ in range(k)]
for i, e in enumerate(entries):
    folds[i % k].append(e)
sorted_ref_data = []
for f in folds:
    sorted_ref_data.extend(f)
sorted_seclib_file = "CB513_sorted_reference.db"
Path(sorted_seclib_file).write_text("\n\n".join(sorted_ref_data))

selected_arg = [arg for arg in sys.argv if arg in ["gor1", "gor3", "gor4"]]
methods = selected_arg if selected_arg else ["gor1", "gor3", "gor4"]
# Filtere GOR5 explizit aus den Argumenten
requested_gor5 = [arg for arg in sys.argv if arg.startswith("gor5_")]
run_all_gor5 = (len(sys.argv) == 1)

def parse_mean(line):
    m = re.search(r'Mean:\s*([\d.]+)', line, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return None

def parse_summary_file(summary_file):
    scores = {}
    if not Path(summary_file).exists():
        print(f"  WARNING: Summary file not found: {summary_file}")
        return scores

    with open(summary_file, "r") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue

            if re.match(r'^q3\s*:', stripped, re.IGNORECASE):
                val = parse_mean(stripped)
                if val is not None:
                    scores["Q3"] = val
            elif re.match(r'^qobs_h\s*:|^q3_h\s*:', stripped, re.IGNORECASE):
                val = parse_mean(stripped)
                if val is not None:
                    scores["H"] = val
            elif re.match(r'^qobs_e\s*:|^q3_e\s*:', stripped, re.IGNORECASE):
                val = parse_mean(stripped)
                if val is not None:
                    scores["E"] = val
            elif re.match(r'^qobs_c\s*:|^q3_c\s*:', stripped, re.IGNORECASE):
                val = parse_mean(stripped)
                if val is not None:
                    scores["C"] = val
            elif re.match(r'^sov\s*:', stripped, re.IGNORECASE):
                val = parse_mean(stripped)
                if val is not None:
                    scores["SOV"] = val
            elif re.match(r'^sov_h\s*:', stripped, re.IGNORECASE):
                val = parse_mean(stripped)
                if val is not None:
                    scores["SOV_H"] = val
            elif re.match(r'^sov_e\s*:', stripped, re.IGNORECASE):
                val = parse_mean(stripped)
                if val is not None:
                    scores["SOV_E"] = val
            elif re.match(r'^sov_c\s*:', stripped, re.IGNORECASE):
                val = parse_mean(stripped)
                if val is not None:
                    scores["SOV_C"] = val

    if not scores:
        print(f"  WARNING: No scores parsed from {summary_file}!")
    else:
        print(f"  Parsed: {scores}")

    return scores

all_results = {}

for fold in range(k):
    print(f"\n=== Fold {fold+1} ===")
    test  = folds[fold]
    train = [e for j, f in enumerate(folds) if j != fold for e in f]

    #train
    Path("train.db").write_text("\n\n".join(train))

    test_ref_file = f"test_ref_fold{fold + 1}.db"
    Path(test_ref_file).write_text("\n\n".join(test))

    # test gor 1-4
    fasta_lines = []
    for e in test:
        fasta_lines.append(">" + get_id(e))
        fasta_lines.append(get_seq(e))
    test_fasta_file = f"test_fold{fold+1}.fasta"
    Path(test_fasta_file).write_text("\n".join(fasta_lines))

    # test id maf filter
    test_ids = [get_id(e) for e in test]

    for method in methods:
        model_file = f"{method}_fold{fold+1}.model"

        #train
        subprocess.run(["java", "-jar","train.jar",  "--db", "train.db", "--method", method, "--model", model_file], check=True)

        # predict
        pred_file = f"{method}_fold{fold+1}.txt"
        subprocess.run([
            "java", "-cp", "predict.jar", "de.lmu.ifi.bio.gor.cli.Predict",
            "--model", model_file, "--format", "txt", "--seq", test_fasta_file
        ], stdout=open(pred_file, "w"), check=True)

        #Validate
        summary_file  = f"{method}_fold{fold+1}_summary.txt"
        detailed_file = f"{method}_fold{fold+1}_detailed.txt"
        subprocess.run([
            "java", "-cp", "validateGor.jar", "de.lmu.ifi.bio.gor.cli.validateGor",
            "-p", pred_file, "-r", test_ref_file, "-s", summary_file, "-d", detailed_file, "-f", "txt"
        ], check=True)

        all_results.setdefault(method, []).append(parse_summary_file(summary_file))

        # --- GOR 5 Logik ---
        gor5_key = f"gor5_{method}"
        # Nur ausführen, wenn der Ordner da ist UND die Methode gewollt ist
        if Path(alignments_dir).exists() and (run_all_gor5 or gor5_key in requested_gor5):

            fold_maf_dir = Path(f"fold{fold + 1}_maf")
            fold_maf_dir.mkdir(exist_ok=True)

            # Optimierung: Nur kopieren, wenn Ordner leer ist
            if not any(fold_maf_dir.iterdir()):
                for aln_file in Path(alignments_dir).rglob("*.aln"):
                    if any(tid in aln_file.stem for tid in test_ids):
                        shutil.copy(aln_file, fold_maf_dir)
            pred_file5 = f"{gor5_key}_fold{fold + 1}.txt"
            subprocess.run([
                "java", "-cp", "predict.jar", "de.lmu.ifi.bio.gor.cli.Predict",
                "--model", model_file, "--format", "txt", "--maf", str(fold_maf_dir)
            ], stdout=open(pred_file5, "w"), check=True)

            summary_file5 = f"{gor5_key}_fold{fold + 1}_summary.txt"
            detailed_file5 = f"{gor5_key}_fold{fold + 1}_detailed.txt"
            subprocess.run([
                "java", "-cp", "validateGor.jar", "de.lmu.ifi.bio.gor.cli.validateGor",
                "-p", pred_file5, "-r", test_ref_file, "-s", summary_file5, "-d", detailed_file5, "-f", "txt"
            ], check=True)

            all_results.setdefault(gor5_key, []).append(parse_summary_file(summary_file5))



#durchschnittswerte über alle folds
keys = ["Q3", "H", "E", "C", "SOV", "SOV_H", "SOV_E", "SOV_C"]

print(f"{'Method':<12} {'Q3_overall':<12} {'Q3_H':<8} {'Q3_E':<8} {'Q3_C':<8} {'SOV':<8} {'SOV_H':<8} {'SOV_E':<8} {'SOV_C'}")
print("-" * 80)

for method, scores_list in all_results.items():
    avg = {}
    for key in keys:
        vals = [s[key] for s in scores_list if key in s]
        avg[key] = sum(vals) / len(vals) if vals else float('nan')

    print(f"{method:<12} {avg['Q3']:<12.3f} {avg['H']:<8.3f} {avg['E']:<8.3f} {avg['C']:<8.3f} {avg['SOV']:<8.3f} {avg['SOV_H']:<8.3f} {avg['SOV_E']:<8.3f} {avg['SOV_C']:.3f}")
