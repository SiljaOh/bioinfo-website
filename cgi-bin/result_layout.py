# -*- coding: utf-8 -*-
"""Gemeinsames Layout fuer Ergebnis-Seiten (Alignment, Validation): Header + Nav + Container."""
import cgi

def escape(s):
    if s is None:
        return ""
    return cgi.escape(str(s))

# CSS inkl. Alignment-Farben (Matches, Sekundaerstruktur) – moderner Stil wie alignment/validation
RESULT_CSS = """
:root { --bg: #f0f4f3; --surface: #fff; --text: #0f2926; --text-muted: #4a6560; --accent: #0d6b5c; --accent-light: #d4ede8; --border: #c5e0db; --radius: 12px; --radius-sm: 8px; --shadow: 0 2px 12px rgba(13,107,92,0.08); --font: "DM Sans", system-ui, sans-serif; }
* { box-sizing: border-box; }
body { margin: 0; font-family: var(--font); font-size: 1rem; line-height: 1.55; color: var(--text); background: var(--bg); min-height: 100vh; }
.container { max-width: 880px; margin: 0 auto; padding: 0 1.25rem; }
header { background: linear-gradient(135deg, var(--accent) 0%, #0a5449 100%); color: #fff; padding: 1rem 0; box-shadow: 0 4px 20px rgba(13,107,92,0.2); }
header .container { display: flex; align-items: center; justify-content: space-between; }
.logo { font-weight: 700; text-decoration: none; color: #fff; font-size: 1.1rem; }
nav a { color: rgba(255,255,255,0.9); text-decoration: none; font-weight: 500; margin-left: 1.5rem; font-size: 0.95rem; }
nav a:hover { color: #fff; }
main { padding: 2rem 0 3rem; }
.result-content { background: var(--surface); border-radius: var(--radius); padding: 1.5rem; margin-top: 1rem; border: 1px solid var(--border); box-shadow: var(--shadow); }
/* ========== Alignment HTML: Karten, Farben, Legende, SS ========== */
.ali-card { background: linear-gradient(180deg, #fff 0%, #f8fbfa 100%); border: 1px solid var(--border); border-radius: 14px; margin: 1.5rem 0; overflow: hidden; box-shadow: 0 4px 20px rgba(13,107,92,0.08); }
.ali-card-header { background: linear-gradient(135deg, var(--accent) 0%, #0a5449 100%); color: #fff; padding: 0.75rem 1rem; font-weight: 700; font-size: 1.05rem; }
.ali-card-header .ali-id1, .ali-card-header .ali-id2 { font-family: Consolas, monospace; letter-spacing: 0.02em; }
.ali-card-header .ali-vs { opacity: 0.9; font-weight: 500; margin: 0 0.35em; font-size: 0.9em; }
.ali-stats { display: flex; flex-wrap: wrap; gap: 0.5rem; padding: 0.75rem 1rem; background: rgba(13,107,92,0.06); border-bottom: 1px solid var(--border); }
.ali-stat { display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.3rem 0.6rem; border-radius: 8px; font-size: 0.85rem; }
.ali-stat strong { font-weight: 700; }
.ali-stat-score { background: linear-gradient(135deg, #0d6b5c 0%, #0a5449 100%); color: #fff; }
.ali-stat-len { background: #e8f4f2; color: #0a5449; }
.ali-stat-id { background: #d4ede8; color: #065a4d; }
.ali-stat-pos { background: #cce5f0; color: #1a5fb4; }
.ali-stat-seq { background: #f0f4f3; color: var(--text-muted); }
.ali-stat small { font-size: 0.8em; opacity: 0.9; }
.ali-legend { display: flex; flex-wrap: wrap; gap: 1rem; padding: 0.5rem 1rem; font-size: 0.8rem; color: var(--text-muted); border-bottom: 1px solid var(--border); }
.ali-legend-item { display: inline-flex; align-items: center; gap: 0.35rem; }
.ali-legend-dot { display: inline-block; width: 12px; height: 12px; border-radius: 3px; }
.ali-legend-dot.ali-match { background: #0d6b5c; }
.ali-legend-dot.ali-pos { background: #1a5fb4; }
.ali-legend-dot.ali-neg { background: #c01c28; }
.ali-legend-dot.ali-gap { background: #9a9996; }
.ali-seq-wrap { padding: 1rem; overflow-x: auto; }
.ali-table { border-collapse: collapse; font-family: Consolas, "Liberation Mono", monospace; font-size: 15px; line-height: 1.5; width: 100%; }
.ali-table td { vertical-align: top; padding: 0.15rem 0; }
.ali-linenum { color: var(--text-muted); font-size: 0.85em; padding-right: 0.75rem; user-select: none; min-width: 2.5em; }
/* Gleiche Breite pro Zeichen, damit Seq-Zeile, Match-Striche (|) und Seq-Zeile spaltenweise bündig sind */
.ali-table .ali-seq span:not(.ali-pos-end),
.ali-table .ali-mid span.ali-mid-char { display: inline-block; min-width: 1.2ch; width: 1.2ch; text-align: center; box-sizing: border-box; letter-spacing: 0; }
.ali-seq { letter-spacing: 0; }
.ali-mid { letter-spacing: 0; color: var(--text-muted); font-size: 15px; }
.ali-pos-end { color: var(--text-muted); font-size: 0.85em; margin-left: 0.25rem; }
.ali-match { color: #0d6b5c; font-weight: bold; background: rgba(13,107,92,0.12); padding: 0 1px; border-radius: 2px; }
.ali-pos { color: #1a5fb4; font-weight: 600; background: rgba(26,95,180,0.1); padding: 0 1px; border-radius: 2px; }
.ali-neg { color: #c01c28; font-weight: 600; background: rgba(192,28,40,0.12); padding: 0 1px; border-radius: 2px; }
.ali-gap { color: #7a7875; background: rgba(0,0,0,0.05); padding: 0 1px; }
.ali-block { font-family: Consolas, monospace; font-size: 14px; margin: 1em 0; max-width: 100%; overflow-x: auto; }
/* Sekundärstruktur: H = Helix, E = Strang, C = Coil */
.ali-ss-block { margin-top: 1rem; padding: 1rem; background: linear-gradient(180deg, #fafbfc 0%, #f0f4f3 100%); border: 1px solid var(--border); border-radius: 10px; max-width: 100%; overflow-x: auto; }
.ali-ss-title { position: relative; display: inline-flex; align-items: center; gap: 0.45rem; font-weight: 700; font-size: 0.9rem; color: var(--accent); margin-bottom: 0.25rem; padding-right: 0.1rem; }
.ali-ss-expl { margin: 0 0 0.5rem; font-size: 0.82rem; color: var(--text-muted); line-height: 1.45; }
.ali-ss-expl code { background: rgba(0,0,0,0.06); padding: 0.1rem 0.35rem; border-radius: 4px; font-size: 0.9em; }
.ali-ss-title::after { content: "i"; display: inline-flex; align-items: center; justify-content: center; width: 1.1rem; height: 1.1rem; border-radius: 999px; background: var(--accent-light); color: var(--accent); font-size: 0.72rem; font-weight: 700; border: 1px solid rgba(13,107,92,0.18); cursor: help; flex: 0 0 auto; }
.ali-ss-title::before { content: "Zeigt die auf den finalen Alignment-Pfad projizierte Sekundärstruktur beider Sequenzen. H = Helix, E = Strang, C = Coil. Gleiche Zustände wie H/H oder E/E werden über die Levitt-Matrix bevorzugt, ungleiche Zustände wie H/E schwächer bewertet. Das SS-Gewicht steuert, wie stark dieser Zusatzscore den gemeinsamen Alignment-Pfad beeinflusst. '-' markiert eine normale Alignment-Lücke."; position: absolute; left: 0; top: calc(100% + 10px); width: min(420px, 82vw); padding: 0.7rem 0.85rem; border-radius: 8px; background: #10201d; color: #f5fbfa; font-size: 0.74rem; line-height: 1.5; font-weight: 500; box-shadow: 0 10px 24px rgba(0,0,0,0.22); opacity: 0; pointer-events: none; transition: opacity 0.16s ease, transform 0.16s ease; transform: translateY(-2px); z-index: 40; }
.ali-ss-title:hover::before { opacity: 1; transform: translateY(0); }
.ali-ss-legend { display: flex; flex-wrap: wrap; gap: 1rem; margin-bottom: 0.5rem; font-size: 0.8rem; color: var(--text-muted); }
.ss-legend-item { display: inline-flex; align-items: center; gap: 0.35rem; }
.ali-ss-lines { display: block; max-width: 100%; font-family: Consolas, monospace; font-size: 13px; line-height: 1.55; overflow-x: auto; padding-bottom: 0.2rem; }
/* Gleiche Breite pro Zeichen, damit Zeile 1 (SS), Zeile 2 (|/·) und Zeile 3 (SS) spaltenweise bündig sind */
.ali-ss-lines .ali-ss-line span,
.ali-ss-lines .ali-ss-mid span { display: inline-block; min-width: 1.25ch; width: 1.25ch; text-align: center; box-sizing: border-box; }
.ali-ss-line { margin-bottom: 0.1rem; white-space: nowrap; width: max-content; min-width: 100%; letter-spacing: 0; }
.ali-ss-mid { white-space: nowrap; width: max-content; min-width: 100%; letter-spacing: 0; line-height: 1.4; margin-bottom: 0.25rem; }
.ss-mid-match { color: #0d6b5c; font-weight: bold; }
.ss-mid-mismatch { color: #c01c28; }
.ss-mid-gap { color: #9a9996; }
.ss-h { color: #fff; background: #e74c3c; font-weight: bold; padding: 0; border-radius: 2px; }
.ss-e { color: #fff; background: #3498db; font-weight: bold; padding: 0; border-radius: 2px; }
.ss-c { color: #7f8c8d; background: #ecf0f1; padding: 0; border-radius: 2px; }
@media (max-width: 760px) { .ali-ss-lines { font-size: 12px; letter-spacing: 0.02em; } }
.ss-score-box { margin: 1rem 0 1.25rem; background: linear-gradient(135deg, #edf5f4 0%, #e0f0ee 100%); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
.ss-score-box summary { list-style: none; cursor: pointer; padding: 0.95rem 1.1rem; font-weight: 700; color: var(--accent); font-size: 1rem; display: flex; align-items: center; gap: 0.55rem; }
.ss-score-box summary::-webkit-details-marker { display: none; }
.ss-score-box summary::before { content: "+"; display: inline-flex; align-items: center; justify-content: center; width: 1.15rem; height: 1.15rem; border-radius: 999px; background: rgba(13,107,92,0.14); color: var(--accent); font-size: 0.95rem; font-weight: 700; flex: 0 0 auto; }
.ss-score-box[open] summary::before { content: "-"; }
.ss-score-body { padding: 0 1.1rem 1rem; border-top: 1px solid rgba(13,107,92,0.12); }
.ss-score-box p { margin: 0.45rem 0; color: var(--text); font-size: 0.93rem; line-height: 1.55; }
.ss-score-box code { background: rgba(255,255,255,0.9); border: 1px solid var(--border); border-radius: 6px; padding: 0.12rem 0.38rem; }
.ss-score-formula { margin: 0.7rem 0 !important; }
.ss-feature-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.7rem; margin-top: 0.9rem; }
.ss-feature-item { background: rgba(255,255,255,0.72); border: 1px solid var(--border); border-radius: 10px; padding: 0.75rem 0.85rem; font-size: 0.9rem; line-height: 1.5; color: var(--text); }
.ali-compare-details { margin: 1rem 0; border: 1px solid var(--border); border-radius: var(--radius-sm); overflow: hidden; background: var(--surface); }
.ali-compare-details summary { padding: 0.65rem 1rem; font-weight: 600; cursor: pointer; list-style: none; background: rgba(13,107,92,0.06); }
.ali-compare-details summary::-webkit-details-marker { display: none; }
.ali-compare-body { padding: 1rem; border-top: 1px solid var(--border); }
.ss-feature-item strong { display: block; margin-bottom: 0.18rem; color: var(--accent); }
.ss-levitt-box { margin-top: 0.9rem; background: rgba(255,255,255,0.8); border: 1px solid var(--border); border-radius: 10px; padding: 0.8rem; overflow-x: auto; }
.ss-levitt-title { font-size: 0.9rem; font-weight: 700; color: var(--accent); margin-bottom: 0.5rem; }
.ss-levitt-table { border-collapse: collapse; font-size: 0.88rem; min-width: 220px; }
.ss-levitt-table th, .ss-levitt-table td { border: 1px solid var(--border); padding: 0.45rem 0.65rem; text-align: center; }
.ss-levitt-table th { background: #f7fbfa; color: var(--accent); }
.ss-levitt-pos { background: rgba(13,107,92,0.14); color: #065a4d; font-weight: 700; }
.ss-levitt-neg { background: rgba(192,28,40,0.12); color: #8f1821; font-weight: 700; }
.ss-levitt-neutral { background: rgba(0,0,0,0.04); color: var(--text-muted); font-weight: 600; }
.ss-score-meta { display: flex; flex-wrap: wrap; gap: 0.55rem; margin-top: 0.7rem; }
.ss-score-chip { display: inline-flex; align-items: center; padding: 0.3rem 0.65rem; border-radius: 999px; background: rgba(13,107,92,0.12); color: #065a4d; font-size: 0.82rem; font-weight: 600; }
@media (max-width: 760px) { .ss-feature-list { grid-template-columns: 1fr; } }
/* 3D-Links */
.ali-3d-block { margin-top: 1rem; padding: 0.75rem 1rem; background: #1a1d23; color: #e6e8eb; border-radius: 10px; font-size: 0.9rem; }
.ali-3d-title { font-weight: 600; margin-right: 0.5rem; }
.ali-3d-sep { opacity: 0.5; margin: 0 0.35rem; }
.ali-3d-link { display: inline-block; padding: 0.35rem 0.75rem; background: linear-gradient(135deg, #0d6b5c 0%, #0a5449 100%); color: #fff !important; border-radius: 6px; font-weight: 600; text-decoration: none; margin-right: 0.5rem; transition: transform 0.15s, box-shadow 0.15s; }
.ali-3d-link:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(13,107,92,0.4); }
pre { background: #1a1d23; color: #e6e8eb; padding: 1rem; overflow: auto; border-radius: 6px; font-size: 0.9rem; }
/* DP-Matrizen (Fixed Point): Erklaerung + Karten */
.heatmaps { margin-top: 2.5rem; padding-top: 1.5rem; border-top: 2px solid var(--accent-light); }
.heatmaps-title { font-size: 1.25rem; color: var(--accent); margin: 0 0 1rem; padding-bottom: 0.5rem; border-bottom: 2px solid var(--accent-light); }
.heatmaps-fixedpoint-expl { background: linear-gradient(135deg, #edf5f4 0%, #e0f0ee 100%); border: 1px solid var(--border); border-radius: 12px; padding: 1.25rem 1.5rem; margin-bottom: 1rem; }
.heatmaps-fixedpoint-expl p { margin: 0.5rem 0; font-size: 0.95rem; line-height: 1.6; }
.dp-formula { margin: 0.75rem 0 !important; font-size: 1rem; }
.dp-formula code { background: #fff; padding: 0.4rem 0.75rem; border-radius: 6px; border: 1px solid var(--border); display: inline-block; }
.dp-expl-title { font-size: 1rem; color: var(--accent); margin: 0 0 0.5rem; }
.heatmaps-intro { background: linear-gradient(135deg, #f0f9f7 0%, #e8f6f3 100%); border: 1px solid var(--border); border-radius: 12px; padding: 1.25rem 1.5rem; margin-bottom: 1.5rem; }
.heatmaps-intro p { margin: 0.6rem 0; font-size: 0.95rem; line-height: 1.6; }
.heatmaps-intro p:first-child { margin-top: 0; }
.heatmaps-intro code { background: rgba(13,107,92,0.12); padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.9em; }
.dp-legend-item { display: inline-flex; align-items: center; gap: 0.4rem; margin-right: 0.75rem; font-size: 0.9rem; }
.dp-legend-low { display: inline-block; width: 20px; height: 14px; background: linear-gradient(135deg, #283593 0%, #5c6bc0 100%); border-radius: 3px; }
.dp-legend-high { display: inline-block; width: 20px; height: 14px; background: linear-gradient(135deg, #f9a825 0%, #fff59d 100%); border-radius: 3px; }
.dp-legend-dark { display: inline-block; width: 20px; height: 14px; background: linear-gradient(90deg, #2c3e50, #7f8c8d); border-radius: 3px; }
.dp-legend-light { display: inline-block; width: 20px; height: 14px; background: linear-gradient(90deg, #95a5a6, #ecf0f1); border-radius: 3px; }
.dp-card { background: #fff; border: 1px solid var(--border); border-radius: 14px; padding: 1.25rem; margin-bottom: 1.5rem; box-shadow: 0 4px 16px rgba(13,107,92,0.08); overflow: hidden; }
.dp-card-title { font-size: 1.05rem; color: var(--accent); margin: 0 0 0.35rem; font-weight: 700; font-family: Consolas, monospace; }
.dp-card-desc { font-size: 0.85rem; color: var(--text-muted); margin: 0 0 1rem; }
.dp-card-img-wrap { background: #1a1d23; border-radius: 10px; padding: 1rem; text-align: center; }
.dp-card-img-wrap img { max-width: 100%; height: auto; border-radius: 6px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); display: block; margin: 0 auto; }
.heatmaps h3 { margin-top: 1.5rem; }
.heatmaps img { max-width: 100%; height: auto; border: 1px solid var(--border); border-radius: 6px; }
/* DP-Bereich anklickbar ein-/ausblendbar */
.dp-top-preview { display: grid; grid-template-columns: minmax(0, 1fr) 220px; gap: 1rem; align-items: center; margin: 0 0 1.25rem; padding: 1rem 1.1rem; background: linear-gradient(135deg, #edf5f4 0%, #e0f0ee 100%); border: 1px solid var(--border); border-radius: 14px; box-shadow: 0 4px 16px rgba(13,107,92,0.08); }
.dp-top-preview h3 { margin: 0 0 0.35rem; color: var(--accent); font-size: 1rem; }
.dp-top-preview p { margin: 0; color: var(--text-muted); font-size: 0.9rem; }
.dp-top-actions { display: flex; flex-wrap: wrap; gap: 0.6rem; margin-top: 0.85rem; }
.dp-jump-btn { display: inline-flex; align-items: center; gap: 0.45rem; padding: 0.55rem 0.95rem; font-family: inherit; font-size: 0.88rem; font-weight: 700; color: #fff; background: linear-gradient(135deg, var(--accent) 0%, #0a5449 100%); border: none; border-radius: 8px; cursor: pointer; box-shadow: 0 2px 8px rgba(13,107,92,0.25); }
.dp-jump-btn:hover { filter: brightness(0.97); }
.dp-preview-note { font-size: 0.8rem !important; }
.dp-preview-thumb { background: #1a1d23; border-radius: 10px; padding: 0.5rem; min-height: 120px; display: flex; align-items: center; justify-content: center; }
.dp-preview-thumb img { max-width: 100%; max-height: 150px; border-radius: 6px; display: block; }
.dp-section { margin-top: 2rem; padding-top: 1rem; border-top: 2px solid var(--accent-light); }
.dp-toggle-btn { display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.6rem 1.2rem; font-family: inherit; font-size: 1rem; font-weight: 600; color: var(--accent); background: var(--accent-light); border: 2px solid var(--accent); border-radius: var(--radius-sm); cursor: pointer; transition: background 0.2s, color 0.2s; }
.dp-toggle-btn:hover { background: var(--accent); color: #fff; }
.dp-toggle-btn .arrow { display: inline-block; transition: transform 0.2s; }
.dp-section.expanded .dp-toggle-btn .arrow { transform: rotate(90deg); }
.dp-section .dp-content { display: none; margin-top: 1rem; }
.dp-section.expanded .dp-content { display: block; }
.dp-view-tabs { display: flex; gap: 0.5rem; margin-bottom: 0.75rem; font-size: 0.85rem; }
.dp-view-tabs button { padding: 0.3rem 0.75rem; border: 1px solid var(--border); border-radius: 6px; background: #fff; cursor: pointer; font-family: inherit; }
.dp-view-tabs button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.dp-matrix-raw { font-size: 0.75rem; line-height: 1.3; max-height: 20em; overflow: auto; white-space: pre; margin-top: 0.5rem; }
.dp-view-details { margin: 0.75rem 0; border: 1px solid var(--border); border-radius: var(--radius-sm); overflow: hidden; }
.dp-view-details summary { padding: 0.5rem 0.85rem; font-weight: 600; cursor: pointer; list-style: none; background: rgba(13,107,92,0.06); font-size: 0.9rem; }
.dp-view-details summary::-webkit-details-marker { display: none; }
.dp-matrix-raw-wrap { padding: 0.75rem; border-top: 1px solid var(--border); overflow: auto; max-height: 24em; }
.dp-matrix-table { border-collapse: collapse; font-size: 0.7rem; font-family: Consolas, monospace; }
.dp-matrix-table td { border: 1px solid var(--border); padding: 0.2rem 0.4rem; min-width: 2.5em; text-align: right; background: var(--surface); }
.dp-path-cell { background: rgba(220, 40, 40, 0.2) !important; font-weight: 700; color: #8b2020; }
@media (max-width: 760px) { .dp-top-preview { grid-template-columns: 1fr; } }
/* Zwei-Spalten: Alignment + Sekundärstruktur links, JSmol rechts */
.result-two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; align-items: start; margin-bottom: 1rem; }
@media (max-width: 900px) { .result-two-col { grid-template-columns: 1fr; } }
.result-align-col { min-width: 0; }
.result-jsmol-col { position: sticky; top: 1rem; }
/* JSmol: eingeklappt (zu), erst beim Klick aufklappen – Alignment bleibt immer sichtbar */
.jsmol-toggle-section { margin-top: 2rem; padding-top: 1rem; border-top: 2px solid var(--accent-light); }
.jsmol-toggle-btn { display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.6rem 1.2rem; font-family: inherit; font-size: 1rem; font-weight: 600; color: var(--accent); background: var(--accent-light); border: 2px solid var(--accent); border-radius: var(--radius-sm); cursor: pointer; }
.jsmol-toggle-btn:hover { background: var(--accent); color: #fff; }
.jsmol-toggle-btn .arrow { display: inline-block; transition: transform 0.2s; }
.jsmol-toggle-section.expanded .jsmol-toggle-btn .arrow { transform: rotate(90deg); }
.jsmol-toggle-content { display: none; margin-top: 1rem; }
.jsmol-toggle-section.expanded .jsmol-toggle-content { display: block; }
.jsmol-ss-section { padding: 1.25rem; background: linear-gradient(180deg, #edf5f4 0%, #e0f0ee 100%); border: 1px solid var(--border); border-radius: var(--radius); max-width: 100%; }
.jsmol-embed-small { width: 280px !important; max-width: 100% !important; height: 260px !important; min-height: 200px; box-sizing: border-box; }
.jsmol-embed-small canvas { max-width: 280px !important; max-height: 260px !important; }
.jsmol-ss-section h3 { font-size: 1.05rem; color: var(--accent); margin: 0 0 0.75rem; }
.jsmol-ss-section .jsmol-lead { font-size: 0.95rem; color: var(--text); margin-bottom: 0.75rem; line-height: 1.5; }
.jsmol-ss-section .jsmol-legend { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-bottom: 1rem; font-size: 0.85rem; }
.jsmol-legend-item { display: inline-flex; align-items: center; gap: 0.35rem; }
.jsmol-legend-item span { display: inline-block; width: 14px; height: 14px; border-radius: 3px; }
.jsmol-legend-item .jmol-h { background: #e74c3c; }
.jsmol-legend-item .jmol-e { background: #f1c40f; }
.jsmol-legend-item .jmol-c { background: #95a5a6; }
#jsmol_ss_container { width: 380px; max-width: 100%; height: 380px; min-height: 320px; max-height: 380px; background: #1a1d23; border-radius: 10px; padding: 0.5rem; overflow: hidden; box-sizing: border-box; }
#jsmol_ss_container canvas { max-width: 100% !important; max-height: 380px !important; }
.result-align-col { flex-shrink: 0; }
.validate-box { background: var(--bg); padding: 1rem; margin-top: 1.5rem; border-radius: var(--radius); border: 1px solid var(--border); }
.btn { display: inline-block; padding: 0.5rem 1rem; font-family: inherit; font-weight: 600; border: none; border-radius: var(--radius-sm); cursor: pointer; background: var(--accent); color: #fff; font-size: 0.9rem; text-decoration: none; box-shadow: 0 2px 6px rgba(13,107,92,0.25); }
.btn:hover { background: #094d43; }
.val-table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.9em; }
.val-table th, .val-table td { border: 1px solid var(--border); padding: 6px 10px; text-align: left; }
.val-table th { background: var(--accent); color: #fff; }
.val-table tr:nth-child(even) { background: var(--bg); }
.bar-wrap { width: 60px; height: 0.75em; background: var(--border); border-radius: 3px; overflow: hidden; display: inline-block; vertical-align: middle; margin-right: 6px; }
.bar { display: block; height: 100%; background: var(--accent); border-radius: 2px; min-width: 2px; }
.summary { display: flex; gap: 2rem; margin: 1rem 0; flex-wrap: wrap; }
.summary-item { background: var(--bg); padding: 0.75rem 1.25rem; border-radius: 8px; }
.summary-item strong { display: block; font-size: 1.5rem; color: var(--accent); }
pre.raw { background: #1a1d23; color: #e6e8eb; padding: 1rem; overflow-x: auto; font-size: 0.85em; border-radius: 6px; }
p.error { color: #c53030; font-weight: 500; }
"""

def print_result_start(title, back_url, back_label):
    print("Content-Type: text/html; charset=utf-8")
    print()
    print("<!DOCTYPE html><html lang=\"de\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">")
    print("<title>" + escape(title) + "</title>")
    print("<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\"><link href=\"https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap\" rel=\"stylesheet\">")
    print("<style>" + RESULT_CSS + "</style></head><body>")
    print("<header><div class=\"container\">")
    print("<a href=\"../index.html\" class=\"logo\">Alignment &amp; Validation</a>")
    print("<nav><a href=\"../alignment.html\">Alignment</a><a href=\"../validation.html\">Validation</a><a href=\"../tuning.html\">Parameter-Tuning</a><a href=\"../index.html\">Start</a></nav>")
    print("</div></header>")
    print("<main class=\"container\">")
    print("<p><a href=\"" + escape(back_url) + "\" class=\"btn\">&#8592; " + escape(back_label) + "</a></p>")
    print("<div class=\"result-content\">")

def print_result_end():
    print("</div></main></body></html>")

def extract_jar_body(html_out):
    """Extrahiert den Inhalt zwischen <body> und </body> aus JAR-HTML. Entfernt den ersten Absatz mit Zurück-Link (Layout liefert eigenen)."""
    if not html_out:
        return ""
    s = html_out
    start = s.find("<body>")
    if start >= 0:
        start = start + 6
    else:
        start = 0
    end = s.find("</body>")
    if end < 0:
        end = len(s)
    body = s[start:end].strip()
    # Ersten <p>...</p> mit nur einem Zurück-Link entfernen (Layout hat eigenen Button)
    if body.startswith("<p>") and "</p>" in body:
        first_p_end = body.index("</p>") + 4
        first_p = body[:first_p_end]
        if "alignment.html" in first_p or "validation.html" in first_p or "Zurück" in first_p or "Zur&uuml;ck" in first_p or "&#8592;" in first_p:
            body = body[first_p_end:].lstrip()
    return body
