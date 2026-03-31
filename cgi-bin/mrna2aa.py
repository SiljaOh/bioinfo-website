import argparse
import sys
parser = argparse.ArgumentParser()
parser.add_argument("--fasta",required=True)
args = parser.parse_args()

codon_table = {
    "UUU": "F", "UUC": "F",
    "UUA": "L", "UUG": "L",
    "CUU": "L", "CUC": "L", "CUA": "L", "CUG": "L",
    "AUU": "I", "AUC": "I", "AUA": "I",
    "AUG": "M",
    "GUU": "V", "GUC": "V", "GUA": "V", "GUG": "V",
    "UCU": "S", "UCC": "S", "UCA": "S", "UCG": "S",
    "AGU": "S", "AGC": "S",
    "CCU": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACU": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCU": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "UAU": "Y", "UAC": "Y",
    "CAU": "H", "CAC": "H",
    "CAA": "Q", "CAG": "Q",
    "AAU": "N", "AAC": "N",
    "AAA": "K", "AAG": "K",
    "GAU": "D", "GAC": "D",
    "GAA": "E", "GAG": "E",
    "UGU": "C", "UGC": "C",
    "UGG": "W",
    "CGU": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGA": "R", "AGG": "R",
    "GGU": "G", "GGC": "G", "GGA": "G", "GGG": "G",
    "UAA": "STOP",
    "UAG": "STOP",
    "UGA": "STOP"
}

def translate(mrna):
    if len(mrna)%3!=0:
        return None
    allowed=set("ACGU")
    if any(b not in allowed for b in mrna):
        return None

    protein = ""
    for i in range(0, len(mrna), 3):
        codon = mrna[i:i + 3]

        amino_acid = codon_table.get(codon)
        if amino_acid is None:
            return None
        if amino_acid =="STOP":
            break

        protein += amino_acid
    return protein

f=sys.stdin if args.fasta == "-" else open(args.fasta)
try:
    header = None
    sequence = ""
    for line in f:
        line = line.strip()
        if not line: #leere Zeilen ignorieren
            continue
        if line.startswith(">"):
            if header is not None:
                prot=translate(sequence)
                if prot is not None:
                    print(header)
                    print(prot)
            #neuen Header speichern
            header = line
            sequence = ""
        else:
            sequence += line
    #letzte Zeile auch noch
    if header is not None:
        prote = translate(sequence)
        if prote is not None:
           print(header)
           print(prote)

finally:
    if f is not sys.stdin:
        f.close()