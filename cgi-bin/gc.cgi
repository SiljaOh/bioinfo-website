#!/usr/bin/env python3

import cgi
import subprocess
import os

print("Content-Type: text/html")
print()

print("<html><body>")

form = cgi.FieldStorage()

if "fasta" not in form:
    print("<h1>GC Content Rechner</h1>")
    print("""
    <form method="post" enctype="multipart/form-data">
        <p>FASTA-Datei hochladen:</p>
        <input type="file" name="fasta">
        <br><br>
        <input type="submit" value="Berechnen">
    </form>
    """)
else:
    fileitem = form["fasta"]

    upload_dir = "/home/f/fiocco/public_html/uploads"
    filepath = os.path.join(upload_dir, "input.fasta")

    with open(filepath, "wb") as f:
        while True:
            chunk = fileitem.file.read(8192)
            if not chunk:
                break
            f.write(chunk)

    result = subprocess.check_output(
        ["python3", "/home/f/fiocco/public_html/cgi-bin/gc.py", filepath],
        universal_newlines=True
    )

    lines = result.strip().splitlines()

    print("<h1>Ergebnis</h1>")
    print("<table border='1'>")
    print("<tr><th>ID</th><th>GC Content (%)</th></tr>")
    print(f"<tr><td>{lines[0]}</td><td>{lines[1]}</td></tr>")
    print("</table>")
    print("<br><a href='gc.cgi'>Neue Datei hochladen</a>")

print("</body></html>")
