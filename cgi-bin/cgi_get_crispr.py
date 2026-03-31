#!/usr/bin/env python3
import sys
import argparse
import urllib.parse
import cgi
import html
import os
import cgitb

cgitb.enable()

def find_crispr_sites(fasta_text):
    results = []
    lines = fasta_text.strip().splitlines()
    header = ""
    genome_parts = []
    
    def process_sequence(hdr, parts):
        crispr_length = 23
        genome_sequence = "".join(parts).upper()
        found = []
        
        for i in range(len(genome_sequence) - 22):
            crispr = genome_sequence[i:i + crispr_length]
            if crispr[21:23] == "GG":
                found.append(f"{hdr}\t{i + 1}\n{crispr}")
        return found

    for line in lines:
        line = line.strip()
        if not line: 
            continue
            
        if line.startswith(">"):
            if header != "" or genome_parts:
                results.extend(process_sequence(header or ">Unnamed_Sequence", genome_parts))
            header = line
            genome_parts = []
        else:
            genome_parts.append(line)
            
    if header != "" or genome_parts:
        results.extend(process_sequence(header or ">Unnamed_Sequence", genome_parts))
        
    if not results:
        return "INFO: Keine potenziellen CRISPR-Zielsequenzen (NGG-Motiv) gefunden."
        
    return "\n".join(results)

def print_website(fasta_input, result=None):
    preview_text = fasta_input if len(fasta_input) < 2000 else fasta_input[:2000] + "\n... [Text gekürzt für die Anzeige] ..."
    fasta_safe = html.escape(preview_text) if preview_text else ""
    
    print("""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>CRISPR/Cas9 Target Search</title>
<meta name="viewport" content="width=device-width, initial-scale=1">

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">

<style>
:root{
 --bio-green: #0d6b5c;
 --bio-green-light: #d4ede8;
 --bio-green-pale: #e8f6f3;
 --bio-teal: #2a9d8f;
 --bio-dark: #0f2926;
 --bio-deep: #0a1f1c;
 --text: #1a2e2a;
 --text-muted: #4a6560;
 --card-bg: #ffffff;
 --border: #c5e0db;
}

*{box-sizing:border-box}

body{
 margin:0;
 font-family:"DM Sans",system-ui,sans-serif;
 background: radial-gradient(circle at top right, #11594d, var(--bio-deep) 60%);
 color:var(--text);
 line-height:1.6;
 min-height:100vh;
}

body::before {
 content: ""; position: fixed; inset: 0;
 background:
  linear-gradient(180deg, rgba(13,107,92,0.06) 0%, transparent 40%),
  repeating-linear-gradient(0deg, transparent, transparent 32px, rgba(13,107,92,0.03) 32px, rgba(13,107,92,0.03) 33px),
  repeating-linear-gradient(90deg, transparent, transparent 32px, rgba(13,107,92,0.03) 32px, rgba(13,107,92,0.03) 33px);
 pointer-events: none; z-index: 0;
}

.header{
 color:#fff;
 padding:40px 24px 48px;
 text-align:center;
 position: relative; z-index: 1;
}

.header h1{ margin:0; font-size:1.6rem; }
.header h2{ margin-top:20px; font-size:1.2rem; }

.main{
 max-width:920px;
 margin:-24px auto 0;
 padding:0 20px 56px;
 position: relative; z-index: 1;
}

.main-panel{
 background: linear-gradient(180deg, #ffffff 0%, #f8fcfb 100%);
 border-radius:20px;
 padding:36px 32px 40px;
 box-shadow:0 20px 60px rgba(0,0,0,0.25);
}

.page-links{ margin-bottom:20px; }
.page-links a{ color:var(--bio-green); text-decoration:none; font-weight:600; }

.section-title{
 font-size:1.1rem; font-weight:700; color:var(--bio-green);
 margin-bottom:18px; display:flex; align-items:center; gap:12px;
}

.section-title .icon{
 width:36px; height:36px; border-radius:10px;
 background: linear-gradient(135deg, var(--bio-green), var(--bio-teal));
 color:#fff; display:flex; align-items:center; justify-content:center; font-weight:bold;
}

.desc-block{
 background: linear-gradient(135deg, var(--bio-green-pale), var(--bio-green-light));
 border-radius:14px; padding:16px 20px; margin-bottom:20px; border:1px solid var(--border);
}

.form-card{ background:#fff; border:1px solid var(--border); border-radius:16px; padding:22px; }

.field-group{ display:flex; flex-direction:column; gap:8px; margin-bottom:10px; }
.field-group label{ font-weight:600; }

.field-group input[type="file"]{
 padding:12px 14px; border:2px dashed var(--border); border-radius:12px;
 font-family:"DM Sans",sans-serif; background:var(--bio-green-pale); cursor:pointer;
 outline: none; transition: border-color 0.2s;
}
.field-group input[type="file"]:hover, .field-group input[type="file"]:focus {
 border-color: var(--bio-teal);
}

.or-divider {
 text-align: center; font-weight: 700; color: var(--bio-teal); margin: 15px 0; font-size: 0.9em;
}

.field-group textarea{
 padding:14px 16px; border:1px solid var(--border); border-radius:12px;
 font-family:"JetBrains Mono", monospace; outline: none; transition: border-color 0.2s;
 resize: vertical; font-size: 0.9em;
}
.field-group textarea:focus { border-color: var(--bio-teal); }

button{
 padding:14px 22px; border:0; border-radius:12px; margin-top: 10px;
 background: linear-gradient(135deg, var(--bio-green), var(--bio-teal));
 color:#fff; font-weight:600; cursor:pointer; transition: opacity 0.2s; font-size: 1em;
 width: 100%;
}
button:hover { opacity: 0.9; }

.back-link{ margin-top:24px; }
.back-link a{ color:var(--bio-green); text-decoration:none; font-weight:600; }

footer{
 background: linear-gradient(180deg, var(--bio-dark), var(--bio-deep));
 color:#fff; padding:24px; text-align:center; position: relative; z-index: 1;
}

.result-card {
 background: #fff; border: 1px solid var(--border); border-radius: 16px;
 padding: 22px; margin-top: 24px; overflow-x: auto; max-height: 500px;
 font-family: "JetBrains Mono", monospace; font-size: 0.9em; line-height: 1.5; white-space: pre;
}

.error-card {
 background: #fdf0ef; color: #c0392b; border: 1px solid #fadbd8;
 border-radius: 16px; padding: 22px; margin-top: 24px; font-weight: 500;
}

.info-card {
 background: #eef5fb; color: #1a4d7a; border: 1px solid #c5dcf1;
 border-radius: 16px; padding: 22px; margin-top: 24px; font-weight: 500;
}

.download-btn {
 display: inline-block; margin-top: 16px; padding: 12px 18px; border-radius: 12px;
 background: linear-gradient(135deg, var(--bio-green), var(--bio-teal));
 color: #fff; font-weight: 600; text-decoration: none; transition: opacity 0.2s;
}
.download-btn:hover { opacity: 0.9; }
</style>
</head>

<body>

<header class="header">
<h1>Programmierpraktikum Bioinformatik</h1>
<h2>Gruppe 17</h2>
</header>

<main class="main">
<div class="main-panel">

<div class="page-links">
<a href="https://bioclient1.bio.ifi.lmu.de/~fiocco/index.html">Startseite</a> |
<a href="../git_guide.html">Git Anleitung</a> |
<a href="../faq.html">FAQ</a> |
<a href="../about.html"> &Uuml;ber uns</a>
</div>

<section>

<h2 class="section-title">
<span class="icon">C</span>
CRISPR/Cas9 Target Search
</h2>

<div class="desc-block">
Durchsucht DNA-Sequenzen nach potenziellen CRISPR/Cas9-Zielstellen.<br>
Gefunden werden alle 23&nbsp;bp langen Abschnitte, die mit dem PAM-Motiv <strong>NGG</strong> enden.
</div>

<div class="form-card">

<form method="post" enctype="multipart/form-data">

<div class="field-group">
<label for="fasta_file">Option 1: FASTA-Datei hochladen</label>
<input type="file" id="fasta_file" name="fasta_file" accept=".fasta,.fa,.txt">
</div>

<div class="or-divider">&ndash; ODER &ndash;</div>

<div class="field-group">
<label for="fasta">Option 2: Sequenz als Text einfügen</label>
<textarea id="fasta" name="fasta" rows="6" placeholder=">Sequence_1&#10;ATGCTAGCTAGCTAGCTGATCGATCGTAGCTAGCTAG...">""" + fasta_safe + """</textarea>
</div>

<button type="submit">CRISPR-Zielsequenzen suchen</button>

</form>

</div>
""")

    if result:
        if result.startswith("ERROR:"):
            error_msg = result.replace("ERROR:", "").strip()
            print(f'<div class="error-card"><strong>Fehler:</strong> {html.escape(error_msg)}</div>')
        elif result.startswith("INFO:"):
            info_msg = result.replace("INFO:", "").strip()
            print(f'<div class="info-card"><strong>Hinweis:</strong> {html.escape(info_msg)}</div>')
        else:
            print(f'<div class="result-card">{html.escape(result)}</div>')
            
            safe_txt = urllib.parse.quote(result)
            filename = "crispr_targets.txt"
            print(f'<a href="data:text/plain;charset=utf-8,{safe_txt}" download="{filename}" class="download-btn">&#11015; Ergebnisse als .txt herunterladen</a>')

    print("""
<p class="back-link">
<a href="https://bioclient1.bio.ifi.lmu.de/~fiocco/index.html"> &larr; Zur&uuml;ck zur Startseite</a>
</p>

</section>

</div>
</main>

<footer>
Programmierpraktikum Bioinformatik | Gruppe 17 | Wintersemester 2025/2026
</footer>

</body>
</html>
""")

def main():
    is_cgi = os.environ.get("GATEWAY_INTERFACE") is not None

    if is_cgi:
        print("Content-Type: text/html; charset=utf-8")
        print()
        
        form = cgi.FieldStorage()
        fasta_input = ""
        
        if "fasta_file" in form and form["fasta_file"].filename:
            file_item = form["fasta_file"]
            fasta_input = file_item.file.read().decode('utf-8', errors='replace').strip()
        else:
            fasta_input = form.getfirst("fasta", "").strip()
        
        if not fasta_input:
            print_website("")
            return
            
        result = find_crispr_sites(fasta_input)
        print_website(fasta_input, result)
        
    else:
        parser = argparse.ArgumentParser(description="Find CRISPR/Cas9 targets in FASTA")
        parser.add_argument('--fasta', type=argparse.FileType('r'), required=True, help="FASTA file to read")
        args = parser.parse_args()
        
        fasta_text = args.fasta.read()
        print(find_crispr_sites(fasta_text))

if __name__ == "__main__":
    main()
