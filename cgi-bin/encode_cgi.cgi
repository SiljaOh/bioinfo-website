#!/usr/bin/python3
import re
import os
import io
import base64
from mycgi import Form


# --- LOGIK VON ENCODE.PY (angepasst für Web-Input) ---

def parse_csv_content(content):
    data_list = []
    lines = content.strip().splitlines()
    if not lines:
        return []

    header = lines[0].strip().split(',')
    for line in lines[1:]:
        line = line.strip()
        if not line: continue
        values = line.split(',')
        row_dict = dict(zip(header, values))
        data_list.append(row_dict)
    return data_list


def get_exptypes_tsv(data):
    counts = {}
    for row in data:
        dt = row.get('Data_Type', 'Unknown')
        counts[dt] = counts.get(dt, 0) + 1

    output = ""
    for dt in sorted(counts.keys()):
        output += f"{dt}\t{counts[dt]}\n"
    return output


def get_antibodies_tsv(data):
    all_cells = sorted(list(set(row.get('Cell_Type', 'Unknown') for row in data)))
    cell_antibodies = {cell: set() for cell in all_cells}

    for row in data:
        if row.get('Data_Type') == 'ChIP-seq':
            cell = row.get('Cell_Type', 'Unknown')
            factors = row.get('Experimental_Factors', '')
            match = re.search(r'Antibody=(\S+)', factors)
            if match:
                cell_antibodies[cell].add(match.group(1))

    output = ""
    for cell in all_cells:
        output += f"{cell}\t{len(cell_antibodies[cell])}\n"
    return output


def get_chip_rna_tsv(data):
    res = {}
    for row in data:
        cell = row.get('Cell_Type', 'Unknown')
        dcc = row.get('DCC_Accession', '').strip()
        dtype = row.get('Data_Type', '').strip()
        factors = row.get('Experimental_Factors', '')

        if not dcc: continue
        if cell not in res:
            res[cell] = {'rna': [], 'chip': []}

        if dtype == 'RNA-seq':
            res[cell]['rna'].append(dcc)
        elif dtype == 'ChIP-seq':
            match = re.search(r'Antibody=(\S+)', factors)
            if match and match.group(1) == 'H3K27me3':
                res[cell]['chip'].append(dcc)

    output = "cell line\tRNAseq Accession\tChIPseq Accession\n"
    for cell in sorted(res.keys()):
        if res[cell]['rna'] and res[cell]['chip']:
            rna_ids = ",".join(sorted(res[cell]['rna']))
            chip_ids = ",".join(sorted(res[cell]['chip']))
            output += f"{cell}\t{rna_ids}\t{chip_ids}\n"
    return output


# --- HAUPTPROGRAMM ---

def main():
    form = Form()
    print("Content-Type: text/html; charset=utf-8\n")

    # CSS Header (identisch zum Prosite Scanner für Konsistenz)
    print("""
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <title>ENCODE Metadata Analyzer</title>
        <style>
            :root {
                --primary-blue: #2c3e50;
                --accent-blue: #3498db;
                --science-green: #27ae60;
                --light-bg: #f4f7f6;
                --white: #ffffff;
                --border-color: #dcdde1;
            }
            body { font-family: 'Segoe UI', sans-serif; background-color: var(--light-bg); color: var(--primary-blue); padding: 40px; display: flex; flex-direction: column; align-items: center; }
            .container { background: var(--white); padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); max-width: 900px; width: 100%; }
            h1 { color: var(--primary-blue); border-bottom: 3px solid var(--accent-blue); padding-bottom: 10px; margin-top: 0; }
            fieldset { border: 1px solid var(--border-color); border-radius: 8px; padding: 20px; margin-bottom: 25px; background-color: #fafafa; }
            legend { font-weight: bold; color: var(--accent-blue); padding: 0 10px; }
            .input-group { margin-bottom: 15px; }
            label { display: block; font-weight: 600; margin-bottom: 5px; }
            select, input[type="file"] { width: 100%; padding: 10px; border: 1px solid var(--border-color); border-radius: 5px; margin-bottom: 10px; }
            input[type="submit"] { background-color: var(--accent-blue); color: white; border: none; padding: 12px 25px; border-radius: 5px; cursor: pointer; font-weight: bold; width: 100%; }
            input[type="submit"]:hover { background-color: #2980b9; }
            .download-btn { display: inline-block; background-color: var(--science-green); color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold; margin-bottom: 20px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; border-radius: 8px; overflow: hidden; }
            th { background-color: var(--primary-blue); color: white; padding: 12px; text-align: left; }
            td { padding: 12px; border-bottom: 1px solid #eee; font-size: 0.9em; }
            .status-msg { padding: 15px; border-radius: 5px; margin: 15px 0; }
            .error { background: #fadbd8; color: #a93226; border-left: 5px solid #a93226; }
            .warning { background: #fef9e7; color: #9a7d0a; border-left: 5px solid #f1c40f; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>ENCODE Metadata Analyzer</h1>
            <form method="post" enctype="multipart/form-data">
                <fieldset>
                    <legend>CSV Datenquelle & Analyse</legend>
                    <div class="input-group">
                        <label>1. ENCODE CSV Datei hochladen</label>
                        <input type="file" name="csv_file">
                    </div>
                    <div class="input-group">
                        <label>2. Analyse-Typ wählen</label>
                        <select name="analysis_type">
                            <option value="exptypes">Experiment Typen (exptypes.tsv)</option>
                            <option value="antibodies">Antikörper pro Zelllinie (antibodies.tsv)</option>
                            <option value="chip_rna">RNA-seq & ChIP-seq H3K27me3 (chip_rna_seq.tsv)</option>
                        </select>
                    </div>
                    <input type="submit" value="Analyse starten">
                </fieldset>
            </form>
    """)

    csv_data_raw = None
    if "csv_file" in form:
        file_item = form["csv_file"]
        if file_item.filename:
            csv_data_raw = file_item.value.decode('utf-8')

    analysis_type = form.getvalue("analysis_type")

    if csv_data_raw:
        data = parse_csv_content(csv_data_raw)
        result_tsv = ""
        filename = "result.tsv"

        if analysis_type == "exptypes":
            result_tsv = get_exptypes_tsv(data)
            filename = "exptypes.tsv"
        elif analysis_type == "antibodies":
            result_tsv = get_antibodies_tsv(data)
            filename = "antibodies.tsv"
        elif analysis_type == "chip_rna":
            result_tsv = get_chip_rna_tsv(data)
            filename = "chip_rna_seq.tsv"

        if result_tsv:
            # Download Link via Base64 
            b64 = base64.b64encode(result_tsv.encode()).decode()
            print(
                f'<a href="data:text/tab-separated-values;base64,{b64}" download="{filename}" class="download-btn">⬇ {filename} herunterladen</a>')

            # Tabellenvorschau
            print("<h3>Vorschau der Ergebnisse:</h3><table><thead>")
            lines = result_tsv.strip().splitlines()
            if lines:
                # Header erkennen (nur bei chip_rna vorhanden)
                start_idx = 0
                if analysis_type == "chip_rna":
                    cols = lines[0].split('\t')
                    print("<tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr></thead><tbody>")
                    start_idx = 1
                else:
                    print("<tr><th>Kategorie / Zelllinie</th><th>Wert / Anzahl</th></tr></thead><tbody>")

                for line in lines[start_idx:]:
                    cols = line.split('\t')
                    print("<tr>" + "".join(f"<td>{c}</td>" for c in cols) + "</tr>")
            print("</tbody></table>")
    elif "csv_file" in form:
        print(
            "<div class='status-msg warning'><strong>Hinweis:</strong> Bitte eine gültige ENCODE CSV-Datei auswählen.</div>")

    print("</div></body></html>")


if __name__ == "__main__":
    main()
