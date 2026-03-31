#!/usr/bin/env python3
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--organism", required=True)
parser.add_argument("--features", required=True)
args = parser.parse_args()

#step 1 fasta einlesen
def read_fasta(path):
    seqs = {}
    cur = None
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                cur = line[1:].split()[0]
                seqs[cur] = []
            else:
                if cur:
                    seqs[cur].append(line.upper())
    return {k: "".join(v) for k, v in seqs.items()}


def revcomp(s):
    comp = {"A":"T","T":"A","C":"G","G":"C","N":"N"}
    return "".join(comp.get(b, "N") for b in reversed(s.upper()))


seqs = read_fasta(args.organism)
single = next(iter(seqs.values())) if len(seqs) == 1 else None #?

#features einlesen
with open(args.features) as f:
    next(f)  # Header überspringen
    for line in f:
        if not line.strip():
            continue
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 17 or parts[0] != "CDS":
            continue

        locus = parts[16].strip()
        if not locus:
            continue

        try:
            start, end = int(parts[7]), int(parts[8])
        except ValueError:
            continue

        lo, hi = sorted((start, end))
        strand = parts[9].strip()
        acc = parts[6].strip()

        seq = seqs.get(acc)

        if seq is None and acc:
            base = acc.split(".", 1)[0]
            seq = seqs.get(base)
            if seq is None:
                for k in seqs:
                    if k.startswith(acc + "."):
                        seq = seqs[k]
                        break

        if seq is None:
            seq = single
        if seq is None or lo < 1 or hi > len(seq):
            continue

        gene = seq[lo-1:hi]
        if strand == "-":
            gene = revcomp(gene)

        print(">" + locus)
        print(gene)