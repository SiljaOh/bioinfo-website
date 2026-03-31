#!/usr/bin/env python3
import sys
import argparse
import urllib.parse
import cgi
import html
import os
import cgitb
import re

cgitb.enable()

def count_sequences(fasta_text, sequences):
    results = []
    lines = fasta_text.strip().splitlines()
    genome_parts = []
    current_seq = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if current_seq:
                genome_parts.append("".join(current_seq).upper())
                current_seq = []
        else:
            current_seq.append(line)
    if current_seq:
        genome_parts.append("".join(current_seq).upper())

    for s in sequences:
        s = s.upper()
        if not re.match(r"^[ACGTUN]+$", s):
            results.append(f"{s}: Ungültige Sequenz")
            continue
            
        length = len(s)
        count = 0
        for part in genome_parts:
            for i in range(len(part) - length + 1):
                if part[i:i + length] == s:
                    count += 1
        results.append(f"{s}: {count}")
        
    return "\n".join(results)

def print_website(genome_input, seq_input, result=None):
    genome_safe = html.escape(genome_input[:1000]) if genome_input else ""
    seq_safe = html.escape(seq_input) if seq_input else ""
    
    print("""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>Sequence Frequency Search</title>
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

.field-group{ display:flex; flex-direction:column; gap:8px; margin-bottom:16px; }
.field-group label{ font-weight:600; }
.field-group textarea, .field-group input{
 padding:12px 14px; border:1px solid var(--border); border-radius:12px;
 font-family:"DM Sans",sans-serif; outline: none; transition: border-color 0.2s;
}
.field-group textarea:focus, .field-group input:focus { border-color: var(--bio-teal); }

.field-group input[type="file"]{
 background:var(--bio-green-pale); cursor:pointer;
}

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
 padding: 22px; margin-top: 24px; overflow-x: auto;
 font-family: "JetBrains Mono", monospace; font-size: 0.9em; line-height: 1.5; white-space: pre;
}

.error-card {
 background: #fdf0ef; color: #c0392b; border: 1px solid #fadbd8;
 border-radius: 16px; padding: 22px; margin-top: 24px; font-weight: 500;
}
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
<span class="icon">S</span>
Sequence Frequency Search
</h2>

<div class="desc-block">
Zählt die Häufigkeit von DNA-Sequenzen in einer Genom-Datei (auch überlappend).
</div>

<div class="form-card">

<form method="post" enctype="multipart/form-data">

<div class="field-group">
<label for="genome_file">Genom-Datei hochladen</label>
<input type="file" id="genome_file" name="genome_file" accept=".fasta,.fa,.txt">
</div>

<div class="field-group">
<label for="sequences">Sequenz(en)</label>
<input type="text" id="sequences" name="sequences" placeholder="z.B. ATCG, GGG" value=""" + f'"{seq_safe}"' + """>
</div>

<button type="submit">Häufigkeit zählen</button>

</form>

</div>
""")

    if result:
        print(f'<div class="result-card">{html.escape(result)}</div>')

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
        genome_input = ""
        
        if "genome_file" in form and form["genome_file"].filename:
            genome_input = form["genome_file"].file.read().decode('utf-8', errors='replace').strip()
        
        seq_input = form.getfirst("sequences", "").strip()
        
        if not genome_input or not seq_input:
            print_website(genome_input, None)
            return
            
        seq_list = [x.strip() for x in seq_input.split(',')]
        seq_list = [x for x in seq_list if x]

        result = count_sequences(genome_input, seq_list)
        print_website(genome_input, result)
        
    else:
        parser = argparse.ArgumentParser()
        parser.add_argument('--sequence', nargs='+', required=True)
        parser.add_argument('--genome', type=argparse.FileType('r'), required=True)
        args = parser.parse_args()
        
        genome_text = args.genome.read()
        print(count_sequences(genome_text, args.sequence))

if __name__ == "__main__":
    main()
