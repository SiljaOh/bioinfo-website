#!/usr/bin/env python3
import sys
import argparse
import urllib.parse
import urllib.request
import urllib.error
import cgi
import html
import os
import cgitb
import re

cgitb.enable()

def fetch_genome_data(organisms):
    if not organisms:
        return "ERROR: Bitte mindestens einen Organismus angeben."

    patterns = []
    for org in organisms:
        try:
            patterns.append(re.compile(org, re.IGNORECASE))
        except re.error as e:
            return f"ERROR: Ungültiger Suchbegriff '{org}' (RegEx-Fehler: {e})."

    url = "https://ftp.ncbi.nlm.nih.gov/genomes/GENOME_REPORTS/prokaryotes.txt"
    results = []

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as response:
            for line_bytes in response:
                try:
                    line = line_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    continue

                if line.startswith('#'):
                    continue

                columns = line.split('\t')
                
                if len(columns) < 16:
                    continue

                matched_name = columns[0].strip()
                length = columns[6].strip()
                status = columns[15].strip()

                if status == "Complete Genome":
                    for pattern in patterns:
                        if pattern.search(matched_name):
                            results.append(f"{matched_name}\t{length}")
                            break

    except urllib.error.URLError as e:
        return f"ERROR: Netzwerkfehler beim Abrufen der NCBI-Daten ({e.reason})."
    except Exception as e:
        return f"ERROR: Unerwarteter Systemfehler ({str(e)})."

    if not results:
        return "INFO: Keine 'Complete Genomes' für diese Suchbegriffe gefunden."
    
    return "Organism Name\tLength\n" + "-"*50 + "\n" + "\n".join(results)

def print_website(org_input, result=None):
    org_safe = html.escape(org_input) if org_input else ""
    
    print("""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>Prokaryotes Genome Search</title>
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
.field-group input{
 padding:12px 14px; border:1px solid var(--border); border-radius:12px;
 font-family:"DM Sans",sans-serif; outline: none; transition: border-color 0.2s;
}
.field-group input:focus { border-color: var(--bio-teal); }

button{
 padding:12px 18px; border:0; border-radius:12px;
 background: linear-gradient(135deg, var(--bio-green), var(--bio-teal));
 color:#fff; font-weight:600; cursor:pointer; transition: opacity 0.2s;
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
<span class="icon">G</span>
Prokaryotes Genome Search
</h2>

<div class="desc-block">
Durchsucht den aktuellen NCBI Prokaryoten-Report nach spezifizierten Bakterien.<br>
Gibt den vollständigen Genomnamen und die Länge für <strong>Complete Genomes</strong> zurück.
</div>

<div class="form-card">

<form method="get">

<div class="field-group">
<label for="organism">Organismus / RegEx</label>
<input type="text" id="organism" name="organism" placeholder="z.B. Escherichia coli, Bacillus subtilis" value=""" + f'"{org_safe}"' + """>
</div>

<button type="submit">Genom-Daten abrufen</button>

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
            
            safe_tsv = urllib.parse.quote(result)
            filename = "genome_results.tsv"
            print(f'<a href="data:text/plain;charset=utf-8,{safe_tsv}" download="{filename}" class="download-btn">&#11015; Ergebnisse als .tsv herunterladen</a>')

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
        raw_input = form.getfirst("organism", "")
        
        if not raw_input.strip():
            print_website("")
            return
            
        org_list = [x.strip() for x in raw_input.split(',')]
        org_list = [x for x in org_list if x]

        sys.argv = [sys.argv[0], "--organism"] + org_list

    parser = argparse.ArgumentParser(description="Fetch Complete Genome data from NCBI")
    parser.add_argument('-o', '--organism', dest='organism', nargs='+', required=True, metavar='organism', help='Organism name(s) or regex')

    args = parser.parse_args()

    combined_result = fetch_genome_data(args.organism)

    if is_cgi:
        print_website(raw_input if is_cgi else ", ".join(args.organism), combined_result)
    else:
        print(combined_result)

if __name__ == "__main__":
    main()
