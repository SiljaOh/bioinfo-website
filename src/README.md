# src/ – Projekt-Code

In diesem Ordner liegen **alle wichtigen Codes** des Alignment-Projekts (ohne weitere Unterordner außer den Java-Packages).

## Inhalt

| Typ | Dateien |
|-----|--------|
| **Java (Package alignment)** | `alignment/` – Main.java, AlignmentTool.java, ValidateAli.java, SubstMatrix.java, SsMatrix.java, LocalAlignment.java, GlobalAlignment.java, Backtracking.java, Recursion.java, FreeShiftAlignment.java, CheckScore.java, TestAlignment.java, Benchmark.java |
| **Java (Package AlignmentTool)** | `AlignmentTool/` – validateAliwithcomm.java |
| **Python** | run_validation_homstrad.py, run_validation_3d_plots.py, get_seq.py, tune_params.py, alignment_validate_pipeline.py, run_benchmark.py, homstad_parser.py, validation_metrics.py, import_homstrad_to_db.py, import_homstrad_secondary_structure.py |

## Aufruf (aus Projektroot)

- **JARs bauen:** `./build/build.sh` und `./build/build_validate.sh` (lesen aus `src/alignment/`)
- **Validation HOMSTRAD:** `python3 src/run_validation_homstrad.py [--homstrad-dir PFAD]`
- **Pipeline:** `python3 src/alignment_validate_pipeline.py --pairs ... --seqlib ... -m ... -o report`
- **Tuning:** `python3 src/tune_params.py --pairs ... --seqlib ... -m ... --ref ...`
- **Benchmark:** `python3 src/run_benchmark.py [--quick]`

Die gebauten JARs (alignment.jar, validateAli.jar) und dayhoff.mat liegen im **Projektroot** und werden von den Skripten dort erwartet.
