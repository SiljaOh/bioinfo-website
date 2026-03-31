#!/usr/bin/python3
import re
import urllib.request
import sys
from mycgi import Form  # Nutzt deine Klasse aus mycgi.py


# --- LOGIK VON PSSCAN.PY (angepasst für Web-Strings) ---

def parse_fasta_content(content):
    sequences = {}
    current_header = None
    current_seq = []
    # .splitlines() statt Dateischleife für Web-Input
    for line in content.splitlines():
        line = line.strip()
        if not line: continue
        if line.startswith(">"):
            if current_header:
                sequences[current_header] = "".join(current_seq)
            current_header = line[1:]
            current_seq = []
        else:
            current_seq.append(line)
    if current_header:
        sequences[current_header] = "".join(current_seq)
    return sequences


def prosite_to_regex(pattern):
    regex = pattern.replace("<","^").replace(">","$")
    #{ABC} -> [^ABC]
    regex = re.sub(r'\{([A-Za-z]+)\}', r'[^\1]', regex)
    # 'x' --> '.'
    regex = regex.replace("x", ".")
    #remove -
    regex = regex.replace("-", "")
    # (n) or (n, m) -> {n} or {n, m}
    regex = re.sub(r'\((\d+(?:,\d+)?)\)', r'{\1}', regex)

    return regex



def pattern_from_web(prosite_id):
    url = "https://ftp.expasy.org/databases/prosite/prosite.dat"
    try:
        with urllib.request.urlopen(url) as response:
            found = False
            for line in response:
                line = line.decode('utf-8').rstrip('\n')
                if line.startswith("AC") and prosite_id in line:
                    found = True
                if found and line.startswith("PA"):
                    return line[2:].strip().rstrip('.')
    except Exception:
        return None
    return None


# --- HAUPTPROGRAMM ---

def main():
    # Instanz deiner Form-Klasse erstellen
    form = Form()

    # HTTP Header senden
    print("Content-Type: text/html; charset=utf-8\n")

    # HTML Grundgerüst mit modernem CSS
    print("""
        <!DOCTYPE html>
        <html lang="de">
        <head>
            <meta charset="UTF-8">
            <title>Prosite Pattern Scanner | BioInformatics Tool</title>
            <style>
                :root {
                    --primary-blue: #2c3e50;
                    --accent-blue: #3498db;
                    --science-green: #27ae60;
                    --light-bg: #f4f7f6;
                    --white: #ffffff;
                    --border-color: #dcdde1;
                }

                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background-color: var(--light-bg);
                    color: var(--primary-blue);
                    margin: 0;
                    padding: 40px;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                }

                .container {
                    background: var(--white);
                    padding: 30px;
                    border-radius: 12px;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                    max-width: 900px;
                    width: 100%;
                }

                h1 {
                    color: var(--primary-blue);
                    border-bottom: 3px solid var(--science-green);
                    padding-bottom: 10px;
                    margin-top: 0;
                    font-weight: 600;
                    letter-spacing: -0.5px;
                }

                fieldset {
                    border: 1px solid var(--border-color);
                    border-radius: 8px;
                    padding: 20px;
                    margin-bottom: 25px;
                    background-color: #fafafa;
                }

                legend {
                    font-weight: bold;
                    color: var(--accent-blue);
                    padding: 0 10px;
                }

                .input-group {
                    margin-bottom: 15px;
                }

                label {
                    display: block;
                    font-weight: 600;
                    margin-bottom: 5px;
                }

                input[type="text"], input[type="file"] {
                    width: 100%;
                    padding: 10px;
                    border: 1px solid var(--border-color);
                    border-radius: 5px;
                    box-sizing: border-box;
                    margin-bottom: 10px;
                }

                input[type="submit"] {
                    background-color: var(--science-green);
                    color: white;
                    border: none;
                    padding: 12px 25px;
                    border-radius: 5px;
                    cursor: pointer;
                    font-weight: bold;
                    transition: background 0.3s ease;
                    font-size: 1rem;
                }

                input[type="submit"]:hover {
                    background-color: #219150;
                }

                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 20px;
                    background: white;
                    overflow: hidden;
                    border-radius: 8px;
                }

                th {
                    background-color: var(--primary-blue);
                    color: white;
                    text-align: left;
                    padding: 12px;
                    font-weight: 500;
                }

                td {
                    padding: 12px;
                    border-bottom: 1px solid #eee;
                }

                tr:hover {
                    background-color: #f1f9f5;
                }

                code {
                    background: #eef2f3;
                    padding: 2px 6px;
                    border-radius: 4px;
                    color: #c0392b;
                    font-family: 'Courier New', Courier, monospace;
                }

                .status-msg {
                    padding: 15px;
                    border-radius: 5px;
                    margin: 15px 0;
                }
                .error { background: #fadbd8; color: #a93226; border-left: 5px solid #a93226; }
                .warning { background: #fef9e7; color: #9a7d0a; border-left: 5px solid #f1c40f; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>PROSITE Pattern Scanner</h1>
                <form method="post" enctype="multipart/form-data">
                    <fieldset>
                        <legend>Analyse-Konfiguration</legend>

                        <div class="input-group">
                            <label>1. FASTA Datei hochladen</label>
                            <input type="file" name="fasta_file">
                        </div>

                        <div class="input-group">
                            <label>2. Pattern definieren</label>
                            <div style="display: flex; gap: 10px; align-items: center;">
                                <input type="text" name="pattern" placeholder="z.B. [ST]-x-[RK]" style="flex: 2;">
                                <span style="font-style: italic; color: #7f8c8d;">oder ID:</span>
                                <input type="text" name="web_id" placeholder="PS00001" style="flex: 1;">
                            </div>
                        </div>

                        <input type="submit" value="Sequenzen analysieren">
                    </fieldset>
                </form>
        """)

    # Daten-Abruf (Logik bleibt gleich)
    fasta_data = None
    if "fasta_file" in form:
        file_item = form["fasta_file"]
        if file_item.filename:
            fasta_data = file_item.value.decode('utf-8')

    user_pattern = form.getvalue("pattern")
    web_id = form.getvalue("web_id")

    if fasta_data:
        current_pattern = user_pattern if user_pattern else (pattern_from_web(web_id) if web_id else None)

        if current_pattern:
            regex_str = prosite_to_regex(current_pattern)
            sequences = parse_fasta_content(fasta_data)

            print(f"<div style='margin-top:40px;'>")
            print(f"<h3>Analyse-Ergebnisse für Pattern: <code>{current_pattern}</code></h3>")
            print("<table>")
            print("<thead><tr><th>Header</th><th>Position</th><th>Match-Sequenz</th></tr></thead><tbody>")

            search_regex = f"(?=({regex_str}))"
            found_hits = False

            for header, seq in sequences.items():
                for match in re.finditer(search_regex, seq):
                    found_hits = True
                    start_pos = match.start() + 1
                    matched_substring = match.group(1)
                    print(
                        f"<tr><td><b>{header}</b></td><td>{start_pos}</td><td><code>{matched_substring}</code></td></tr>")

            if not found_hits:
                print(
                    "<tr><td colspan='3' style='text-align:center;'>Keine Übereinstimmungen in den Sequenzen gefunden.</td></tr>")

            print("</tbody></table></div>")
        else:
            print(
                "<div class='status-msg error'><strong>Fehler:</strong> Bitte geben Sie ein gültiges Pattern oder eine Prosite-ID an.</div>")
    elif "fasta_file" in form:
        print(
            "<div class='status-msg warning'><strong>Hinweis:</strong> Bitte wählen Sie eine FASTA-Datei zum Hochladen aus.</div>")

    print("</div></body></html>")


if __name__ == "__main__":
    main()
