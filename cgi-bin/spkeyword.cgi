#!/usr/bin/env python3
import cgi
import html
import shlex

SWISSPROT_PATH = "/mnt/extstud/praktikum/bioprakt/Data/swissprot45.dat"


def norm_kw(s: str) -> str:
    s = s.strip()
    s = " ".join(s.split())
    s = s.rstrip(".;")
    s = s.lower()
    return s


def parse_ac_line(line: str):
    content = line[5:].strip()
    parts = [p.strip() for p in content.split(";")]
    return [p for p in parts if p]


def parse_kw_line(line: str):
    content = line[5:].strip()
    parts = [norm_kw(p) for p in content.split(";")]
    return [p for p in parts if p]


def spkeyword(path: str, query_kws):
    hits = set()
    entry_acs = set()
    entry_kws = set()
    in_entry = False

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n")

            if line.startswith("ID"):
                in_entry = True
                entry_acs.clear()
                entry_kws.clear()
                continue

            if not in_entry:
                continue

            if line.startswith("AC   "):
                for ac in parse_ac_line(line):
                    entry_acs.add(ac)
                continue

            if line.startswith("KW   "):
                for kw in parse_kw_line(line):
                    entry_kws.add(kw)
                continue

            if line.startswith("//"):
                if entry_kws.intersection(query_kws):
                    hits.update(entry_acs)
                in_entry = False
                entry_acs.clear()
                entry_kws.clear()

    return sorted(hits)


# ---------------- CGI OUTPUT ----------------

print("Content-Type: text/html; charset=utf-8")
print()

form = cgi.FieldStorage()
kw_text = form.getfirst("keyword", "").strip()


print("""
<html>
<head>
<meta charset="utf-8">
<title>SwissProt Keyword</title>
<style>
:root {
  --tum-blue-dark: #003359;
}
body {
  font-family: Arial, Helvetica, sans-serif;
  color: var(--tum-blue-dark);
}
a {
  color: var(--tum-blue-dark);
}
</style>
</head>
<body>
""")
print("<h1>SwissProt Keyword (Aufgabe 6)</h1>")

print("<form method='get'>")
print("<label>Keywords (Leerzeichen getrennt, Phrasen in Anführungszeichen):</label> ")
print("<input name='keyword' size='60' value='" + html.escape(kw_text) + "'>")
print("<button type='submit'>Suchen</button>")
print("</form>")

if kw_text:
    query_kws = {norm_kw(k) for k in shlex.split(kw_text) if k.strip()}
    hits = spkeyword(SWISSPROT_PATH, query_kws)

    print("<h2>Treffer</h2>")
    print("<p>Anzahl: " + str(len(hits)) + "</p>")
    print("<pre>")
    for ac in hits:
        print(html.escape(ac))
    print("</pre>")

print("<p><a href='../index.html'>Zurück zur Startseite</a></p>")
print("</body></html>")
