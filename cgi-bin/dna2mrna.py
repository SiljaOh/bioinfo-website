import argparse
import sys
parser = argparse.ArgumentParser()
parser.add_argument("--fasta", required=True)
args = parser.parse_args()

f=sys.stdin if args.fasta=="-" else open(args.fasta)
try:
    for line in f:
        line = line.strip()
        if line.startswith(">"):
            print(line)
        else:
            rna= line.replace("T", "U")
            print(rna)
finally:
    if f is not sys.stdin:
        f.close()
