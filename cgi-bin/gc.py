#!/usr/bin/env python3

import sys

# FASTA-Datei kommt als Argument
if len(sys.argv) != 2:
    print("Usage: gc.py <fasta_file>")
    sys.exit(1)

filename = sys.argv[1]

sequences = {}
current_id = ""

with open(filename) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            current_id = line[1:]
            sequences[current_id] = ""
        else:
            sequences[current_id] += line

max_gc = -1.0
max_id = ""

for seq_id, seq in sequences.items():
    gc = (seq.count("G") + seq.count("C")) / len(seq) * 100
    if gc > max_gc:
        max_gc = gc
        max_id = seq_id

print(max_id)
print(f"{max_gc:.6f}")
