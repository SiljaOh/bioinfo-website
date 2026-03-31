# -*- coding: utf-8 -*-
# Gemeinsames Layout für CGI-Seiten (wie Index Gruppe 17)
# Verwendung: print_page_start("Titel"); print_main_start(); ... Inhalt ...; print_main_end(); print_page_end()

import html as html_module

def _esc(s):
    return html_module.escape(str(s))

# CSS wie Index (gekürzt auf relevante Teile)
STYLE = """
:root {
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
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "DM Sans", system-ui, sans-serif;
  background: var(--bio-deep);
  color: var(--text);
  line-height: 1.6;
  min-height: 100vh;
}
body::before {
  content: "";
  position: fixed;
  inset: 0;
  background:
    linear-gradient(180deg, rgba(13,107,92,0.06) 0%, transparent 40%),
    radial-gradient(ellipse 80% 50% at 50% -20%, rgba(42,157,143,0.15), transparent),
    repeating-linear-gradient(0deg, transparent, transparent 32px, rgba(13,107,92,0.03) 32px, rgba(13,107,92,0.03) 33px),
    repeating-linear-gradient(90deg, transparent, transparent 32px, rgba(13,107,92,0.03) 32px, rgba(13,107,92,0.03) 33px);
  pointer-events: none;
  z-index: 0;
}
.header {
  position: relative;
  background: linear-gradient(160deg, var(--bio-deep) 0%, var(--bio-dark) 40%, var(--bio-green) 100%);
  color: #fff;
  padding: 28px 24px 36px;
  text-align: center;
}
.header-inner { position: relative; z-index: 1; }
.header h1 { margin: 0 0 4px 0; font-size: 1.35rem; font-weight: 700; }
.header p { margin: 0; font-size: 0.95rem; opacity: 0.9; }
.main {
  position: relative;
  z-index: 1;
  max-width: 1050px;
  margin: -24px auto 0;
  padding: 0 20px 56px;
}
.main-panel {
  background: linear-gradient(180deg, rgba(255,255,255,0.97) 0%, rgba(248,252,251,0.98) 100%);
  border-radius: 20px;
  padding: 28px 32px 36px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.25), 0 0 0 1px rgba(255,255,255,0.1) inset;
  backdrop-filter: blur(8px);
}
.main-panel h1 { margin: 0 0 12px 0; font-size: 1.25rem; color: var(--bio-dark); }
.main-panel h2 { margin: 18px 0 8px 0; font-size: 1.1rem; color: var(--bio-green); }
.main-panel .card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 16px 20px;
  margin: 14px 0;
}
.main-panel label { font-weight: 700; display: block; margin-top: 10px; }
.main-panel input[type=text], .main-panel input[type=number], .main-panel input[type=file] {
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid var(--border);
  margin-top: 6px;
  background: #fff;
  max-width: 100%;
}
.main-panel button {
  margin-top: 14px;
  padding: 10px 16px;
  border-radius: 10px;
  border: 0;
  background: var(--bio-green);
  color: #fff;
  cursor: pointer;
  font-weight: 700;
}
.main-panel button:hover { filter: brightness(1.05); }
.main-panel pre {
  background: #f8faf9;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px;
  overflow: auto;
  margin: 10px 0;
  font-size: 0.9rem;
}
.main-panel table { border-collapse: collapse; width: 100%; margin: 10px 0; }
.main-panel th, .main-panel td { border: 1px solid var(--border); padding: 10px; text-align: left; }
.main-panel th { background: var(--bio-green-pale); color: var(--bio-dark); }
.main-panel .hint, .main-panel .small { color: var(--text-muted); font-size: 0.9rem; margin: 6px 0; }
.main-panel a { color: var(--bio-green); text-decoration: none; font-weight: 500; }
.main-panel a:hover { text-decoration: underline; }
.main-panel .back { margin-bottom: 16px; }
footer {
  position: relative;
  z-index: 1;
  background: linear-gradient(180deg, var(--bio-dark) 0%, var(--bio-deep) 100%);
  color: rgba(255,255,255,0.88);
  padding: 20px 24px;
  font-size: 0.9rem;
  text-align: center;
  border-top: 1px solid rgba(13,107,92,0.4);
}
footer a { color: #9ae6d9; text-decoration: none; }
footer a:hover { text-decoration: underline; }
"""

HEADER_HTML = """<header class="header">
  <div class="header-inner">
    <h1>Programmierpraktikum Bioinformatik</h1>
    <p>Gruppe 17</p>
  </div>
</header>"""

FOOTER_HTML = """<footer>
  <a href="../index.html">Startseite</a> &nbsp;&middot;&nbsp;
  <a href="../alignment.html">Alignment</a> &nbsp;
  <a href="../validation.html">Validation</a> &nbsp;
  <a href="../correlations.html">HOMSTRAD Correlations</a> &nbsp;
  <a href="../tuning.html">Parameter Tuning</a> &nbsp;
  <a href="../gor.html">GOR</a>
</footer>"""


def print_page_start(title):
    print("Content-Type: text/html; charset=utf-8\n")
    print("""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{}</style>
</head>
<body>
{}""".format(_esc(title), STYLE, HEADER_HTML))


def print_main_start():
    print("""<main class="main">
  <div class="main-panel">""")


def print_main_end():
    print("""  </div>
</main>""")


def print_page_end():
    print(FOOTER_HTML)
    print("</body></html>")
