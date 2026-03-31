#!/usr/bin/python3
import argparse
import os
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--DSSP', type=argparse.FileType('r'), nargs='+')
parser.add_argument('--PDB', type=argparse.FileType('r'), nargs='+')
parser.add_argument('--id', nargs='+')
parser.add_argument('--output', default='casp_all.seclib', type=argparse.FileType('a'))
args = parser.parse_args()

if not args.DSSP and not args.PDB and not args.id:
    parser.error("Mindestens --DSSP, --PDB oder --id angeben!")

seen_entries = set()

def write_entry(pdb_id, chain_id, full_aa, full_ss):
    #ID + Kette, duplikate vermeiden
    key = (pdb_id.upper(), chain_id.strip())
    if key in seen_entries:
        return
    seen_entries.add(key)
    # kurze as wegmachen
    if len(full_aa) >= 30:
        args.output.write(f"> {pdb_id.upper()}\n")
        args.output.write(f"AS {full_aa}\n")
        args.output.write(f"SS {full_ss}\n\n")

# dssp verarbeiten
if args.DSSP:
    for dssp in args.DSSP:
        # ID aus dateiname
        pdb_id = os.path.basename(dssp.name).split('.')[0].upper()[:4]
        chains = {}
        start = False

        for line in dssp:
            #start
            if '#  RESIDUE AA' in line:
                start = True
                continue
            if start and len(line) > 16:
                #buchstabe aa
                aa = line[13]
                if aa in ['!', '*']: continue
                chain_id = line[11].strip() or 'A'
                #ss struktur
                ss_raw = line[16]

                # mapping
                if ss_raw in ['H', 'G', 'I']: ss = 'H'
                elif ss_raw in ['E', 'B']: ss = 'E'
                else: ss = 'C'

                if chain_id not in chains:
                    #neue ketten hinzufügen
                    chains[chain_id] = {'aa': [], 'ss': []}
                chains[chain_id]['aa'].append(aa.upper())
                chains[chain_id]['ss'].append(ss)

        for chain_id, seqs in chains.items():
            write_entry(pdb_id, chain_id, ''.join(seqs['aa']), ''.join(seqs['ss']))
            break

#pdb
aa_map = {
    'ALA': 'A', 'ARG': 'R', 'ASN': 'N', 'ASP': 'D', 'CYS': 'C', 'GLU': 'E',
    'GLN': 'Q', 'GLY': 'G', 'HIS': 'H', 'ILE': 'I', 'LEU': 'L', 'LYS': 'K',
    'MET': 'M', 'MSE': 'M', 'PHE': 'F', 'PRO': 'P', 'SER': 'S', 'THR': 'T',
    'TRP': 'W', 'TYR': 'Y', 'VAL': 'V'
}

if args.PDB:
    for pdb in args.PDB:
        pdb_id = os.path.basename(pdb.name).split('.')[0].upper()[:4]
        chains = {}
        helix_or_sheet = []

        for line in pdb:
            #nur erstes model
            if line.startswith("ENDMDL"): break

            if line.startswith("ATOM"):
                #as name und chain
                res_name = line[17:20].strip()
                #wenn leer a
                chain_id = line[21].strip() or 'A'
                #welche reisude
                res_id = line[22:26].strip()
                #wie dssp
                if chain_id not in chains:
                    chains[chain_id] = {'aa': [], 'res_ids': []}
                if res_name in aa_map:
                    if not chains[chain_id]['res_ids'] or chains[chain_id]['res_ids'][-1] != res_id:
                        chains[chain_id]['aa'].append(aa_map[res_name])
                        chains[chain_id]['res_ids'].append(res_id)
            #finden was helix und sheet, typ in liste
            if line.startswith("HELIX"):
                helix_or_sheet.append(('H', line[19], line[21:25].strip(), line[33:37].strip()))
            elif line.startswith("SHEET"):
                helix_or_sheet.append(('E', line[21], line[22:26].strip(), line[33:37].strip()))
        #eine kette nach der anderen
        for chain_id, seqs in chains.items():
            #erstmal alles c, dann anpassen
            ss_seq = ['C'] * len(seqs['aa'])
            for typ, chain, start, end in helix_or_sheet:
                #nur aktuelle kette
                if chain != chain_id: continue
                #name as posi 10A = res, für jede as der kette i
                for i, res_id in enumerate(seqs['res_ids']):
                    try:
                        #umwandeln in int und buchstaben weg  zbb 10A
                        r_val = int(''.join(filter(str.isdigit, res_id)))
                        s_val = int(''.join(filter(str.isdigit, start)))
                        e_val = int(''.join(filter(str.isdigit, end)))
                        #wenn aa in bereich passt in struktur
                        if s_val <= r_val <= e_val:
                            #für stelle in E oder H umwandeln
                            ss_seq[i] = typ
                    except ValueError: pass

            write_entry(pdb_id, chain_id, ''.join(seqs['aa']), ''.join(ss_seq))
            break
