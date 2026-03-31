#!/usr/bin/env python3
import cgi
import tempfile
import os
import sys

print("Content-Type: text/html\n")

form = cgi.FieldStorage()

# Wenn noch nichts hochgeladen wurde → Formular anzeigen
if "organism" not in form or "features" not in form:
    print("""
    <html>
    <body>
    <h2>Aufgabe 10 – genome2orf</h2>
    <form method="post" enctype="multipart/form-data">
        <p>Organism (FASTA):<br>
        <input type="file" name="organism" required></p>

        <p>Features (Feature Table):<br>
        <input type="file" name="features" required></p>

        <input type="submit" value="Start">
    </form>
    </body>
    </html>
    """)
    sys.exit()

# Dateien holen
org_file = form["organism"]
feat_file = form["features"]

# Temporär speichern
with tempfile.NamedTemporaryFile(delete=False) as f1:
    f1.write(org_file.file.read())
    org_path = f1.name

with tempfile.NamedTemporaryFile(delete=False) as f2:
    f2.write(feat_file.file.read())
    feat_path = f2.name

print("<html><body><pre>")

try:
    # HIER rufst du deine eigentliche Funktion auf
    # Beispiel: run_genome2orf(org_path, feat_path)

    print("Dateien erfolgreich hochgeladen.")
    print("Organism tmp:", org_path)
    print("Features tmp:", feat_path)
    print("\nHier deine genome2orf-Ausgabe einfügen...")

except Exception as e:
    print("Fehler:", e)

finally:
    os.unlink(org_path)
    os.unlink(feat_path)

print("</pre></body></html>")
