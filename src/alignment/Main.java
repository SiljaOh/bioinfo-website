package alignment;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class Main {

    private static final Pattern CATH_ID =
            Pattern.compile("[0-9][A-Za-z0-9]{3}[A-Za-z0-9][0-9]{2}");
    /** PDB-ID: 4 Zeichen, typisch 1 Ziffer + 3 alphanumerisch (z.B. 1abc, 2XYZ). Keine generischen Namen wie SeqA/SeqB. */
    private static final Pattern PDB_ID = Pattern.compile("^[0-9][A-Za-z0-9]{3}$");

    private static String normalizeId(String id) {
        if (id == null) return null;
        String t = id.trim();
        Matcher m = CATH_ID.matcher(t);
        if (m.find()) return m.group().toLowerCase(Locale.ROOT);
        String cleaned = t.replaceAll("[^A-Za-z0-9]", "");
        m = CATH_ID.matcher(cleaned);
        if (m.find()) return m.group().toLowerCase(Locale.ROOT);
        return cleaned.isEmpty() ? null : cleaned.toLowerCase(Locale.ROOT);
    }

    private static Map<String, String> readSeqLib(String file) throws IOException {
        Map<String, String> seq = new HashMap<>();
        try (BufferedReader br = new BufferedReader(new FileReader(file))) {
            String line;
            while ((line = br.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty()) continue;
                if (line.startsWith("#") || line.startsWith(";")) continue;
                String[] parts = line.split(":");
                if (parts.length >= 2) {
                    String key = parts[0].trim();
                    if (!key.isEmpty()) seq.put(key, parts[1].trim());
                }
            }
        }
        return seq;
    }

    private static void printAli(String id1Raw, String id2Raw, String a1, String a2, double score) {
        System.out.println(">" + id1Raw + " " + id2Raw + " " + String.format(Locale.US, "%.4f", score));
        System.out.println(id1Raw + ": " + a1);
        System.out.println(id2Raw + ": " + a2);
    }

    private static String htmlEscape(String s) {
        if (s == null) return "";
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;");
    }

    /** Wenn id wie eine PDB-ID aussieht (4 Zeichen), HTML-Links für 3D-Ansicht (RCSB) zurückgeben; sonst "". */
    private static String pdb3dLinks(String id) {
        if (id == null) return "";
        String raw = id.trim();
        if (raw.length() >= 4) {
            String four = raw.substring(0, 4);
            if (PDB_ID.matcher(four).matches()) {
                String up = four.toUpperCase(Locale.ROOT);
                return "<a class=\"ali-3d-link\" href=\"https://www.rcsb.org/3d-view/" + up + "\" target=\"_blank\" rel=\"noopener\">3D-Ansicht " + htmlEscape(four) + "</a>";
            }
        }
        return "";
    }

    /** BLAST-artige HTML-Ausgabe: Karte mit Header, Stats, Legende, Alignment (Match/pos/neg/gap) + optionale SS. */
    private static String formatAlignmentHtml(String id1, String id2, String fullA, String fullB, double score, SubstMatrix mat) {
        int len = fullA.length();
        int len1 = 0, len2 = 0, identities = 0, alignedPairs = 0, positiveSubs = 0, mismatches = 0, gaps = 0;
        for (int k = 0; k < len; k++) {
            char ca = fullA.charAt(k);
            char cb = fullB.charAt(k);
            if (ca != '-') len1++;
            if (cb != '-') len2++;
            if (ca == '-' || cb == '-') {
                gaps++;
            } else {
                alignedPairs++;
                if (ca == cb) identities++;
                else if (mat.score(ca, cb) > 0) positiveSubs++;
                else mismatches++;
            }
        }
        double pctId = alignedPairs > 0 ? 100.0 * identities / alignedPairs : 0;

        StringBuilder sb = new StringBuilder();
        sb.append("<div class=\"ali-card\">");
        sb.append("<div class=\"ali-card-header\"><span class=\"ali-id1\">").append(htmlEscape(id1)).append("</span> <span class=\"ali-vs\">vs</span> <span class=\"ali-id2\">").append(htmlEscape(id2)).append("</span></div>");
        sb.append("<div class=\"ali-stats\">");
        sb.append("<span class=\"ali-stat ali-stat-score\" title=\"Alignment Score\">Score <strong>").append(String.format(Locale.US, "%.2f", score)).append("</strong></span>");
        sb.append("<span class=\"ali-stat ali-stat-len\" title=\"Alignment length\">L&auml;nge <strong>").append(len).append("</strong></span>");
        sb.append("<span class=\"ali-stat ali-stat-id\" title=\"Identit&auml;t\">Identit&auml;t <strong>").append(String.format(Locale.US, "%.1f%%", pctId)).append("</strong> <small>(").append(identities).append("/").append(alignedPairs).append(")</small></span>");
        sb.append("<span class=\"ali-stat ali-stat-pos\" title=\"Positive Substitutionen\">Positive Subst <strong>").append(positiveSubs).append("</strong></span>");
        sb.append("<span class=\"ali-stat ali-stat-seq\">Seq1: ").append(len1).append(" &middot; Seq2: ").append(len2).append("</span>");
        sb.append("</div>");
        sb.append("<div class=\"ali-legend\" aria-hidden=\"true\"><span class=\"ali-legend-item\"><span class=\"ali-legend-dot ali-match\"></span> Match (").append(identities).append(")</span><span class=\"ali-legend-item\"><span class=\"ali-legend-dot ali-pos\"></span> Positive Subst (").append(positiveSubs).append(")</span><span class=\"ali-legend-item\"><span class=\"ali-legend-dot ali-neg\"></span> Mismatch (").append(mismatches).append(")</span><span class=\"ali-legend-item\"><span class=\"ali-legend-dot ali-gap\"></span> Gap (").append(gaps).append(")</span></div>");
        sb.append("<div class=\"ali-seq-wrap\"><table class=\"ali-table\">");

        final int chunk = 60;
        for (int start = 0; start < len; start += chunk) {
            int end = Math.min(start + chunk, len);
            StringBuilder line1 = new StringBuilder();
            StringBuilder line2 = new StringBuilder();
            StringBuilder mid = new StringBuilder();
            for (int k = start; k < end; k++) {
                char ca = fullA.charAt(k);
                char cb = fullB.charAt(k);
                String c1 = htmlEscape(String.valueOf(ca));
                String c2 = htmlEscape(String.valueOf(cb));
                String cls1, cls2;
                String midChar;
                if (ca == '-' || cb == '-') {
                    cls1 = cls2 = "ali-gap";
                    midChar = " ";
                } else if (ca == cb) {
                    cls1 = cls2 = "ali-match";
                    midChar = "|";
                } else if (mat.score(ca, cb) > 0) {
                    cls1 = cls2 = "ali-pos";
                    midChar = " ";
                } else {
                    cls1 = cls2 = "ali-neg";
                    midChar = " ";
                }
                line1.append("<span class=\"").append(cls1).append("\">").append(c1).append("</span>");
                line2.append("<span class=\"").append(cls2).append("\">").append(c2).append("</span>");
                mid.append("<span class=\"ali-mid-char\">").append(midChar).append("</span>");
            }
            int posEnd = end;
            sb.append("<tr><td class=\"ali-linenum\">").append(start + 1).append("</td><td class=\"ali-seq\">").append(line1).append(" <span class=\"ali-pos-end\">").append(posEnd).append("</span></td></tr>");
            sb.append("<tr><td></td><td class=\"ali-mid\">").append(mid).append("</td></tr>");
            sb.append("<tr><td></td><td class=\"ali-seq\">").append(line2).append(" <span class=\"ali-pos-end\">").append(posEnd).append("</span></td></tr>");
        }
        sb.append("</table></div></div>");
        return sb.toString();
    }

    /** Sekundärstruktur-Zeile mit H/E/C-Farben als Spans. */
    private static String formatSsHtml(String ss) {
        if (ss == null || ss.isEmpty()) return "";
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < ss.length(); i++) {
            char c = ss.charAt(i);
            String cls = "ss-c";
            if (c == 'H' || c == 'h') cls = "ss-h";
            else if (c == 'E' || c == 'e' || c == 'B') cls = "ss-e";
            sb.append("<span class=\"").append(cls).append("\">").append(htmlEscape(String.valueOf(c))).append("</span>");
        }
        return sb.toString();
    }

    /** Mittlere Zeile: | = Match (gleicher Zustand H/E/C), · = Mismatch, Leerzeichen = Gap. B wird wie E gewertet. */
    private static char normSs(char c) {
        c = Character.toUpperCase(c);
        return (c == 'B') ? 'E' : c;
    }

    private static String formatSsMidHtml(String ss1, String ss2) {
        if (ss1 == null || ss2 == null || ss1.length() != ss2.length()) return "";
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < ss1.length(); i++) {
            char c1 = ss1.charAt(i);
            char c2 = ss2.charAt(i);
            boolean gap = (c1 == '-' || c2 == '-');
            boolean match = !gap && normSs(c1) == normSs(c2);
            if (gap) {
                sb.append("<span class=\"ss-mid-gap\"> </span>");
            } else if (match) {
                sb.append("<span class=\"ss-mid-match\">|</span>");
            } else {
                sb.append("<span class=\"ss-mid-mismatch\">·</span>");
            }
        }
        return sb.toString();
    }

    private static String help() {
        return "Usage: java -jar alignment.jar [--go <gapopen>] [--ge <gapextend>]\n"
                + "       [--dpmatrices <dir>] [--check]\n"
                + "       [--levitt <file>] [--seqlib-ss <file>] [--ss-weight <0..1>]\n"
                + "       --pairs <pairfile> --seqlib <seqlibfile> -m <matrixname>\n"
                + "       --mode <local|global|freeshift> [--nw]\n"
                + "       --format <scores|ali|html>\n"
                + "Options:\n"
                + "  --pairs <pairfile>     path to pairs file\n"
                + "  --seqlib <seqlibfile>  path to sequence library file\n"
                + "  -m <matrixname>        path to substitution matrix file\n"
                + "  --levitt <file>        Levitt SS matrix (H/E/C) for secondary-structure-aided alignment\n"
                + "  --seqlib-ss <file>     per-sequence SS (id:HHEECC...), same IDs as seqlib\n"
                + "  --ss-weight <0..1>     weight for SS score (default 0.3)\n"
                + "  --go <gapopen>         gap open penalty (default -12)\n"
                + "  --ge <gapextend>       gap extend penalty (default -1)\n"
                + "  --mode <local|global|freeshift>\n"
                + "  --nw                   use NW/SW algorithms (linear gaps)\n"
                + "  --format <scores|ali|html>  output format\n"
                + "  --dpmatrices <directory>    output dynamic programming matrices\n"
                + "  --check                 calculate checkscores for all alignments\n";
    }

    public static void main(String[] args) throws Exception {
        String mode = "global";
        String format = "scores";
        String pairsFile = null;
        String seqlibFile = null;
        String matrixFile = null;
        boolean nw = false;
        long go = -12;
        long ge = -1;
        String dpmatricesDir = null;
        boolean check = false;
        String levittFile = null;
        String seqlibSsFile = null;
        double ssWeight = 0.3;

        for (int i = 0; i < args.length; i++) {
            String a = args[i];
            if (a.equals("--mode") && i + 1 < args.length) {
                mode = args[++i].trim().toLowerCase(Locale.ROOT);
            } else if (a.equals("--format") && i + 1 < args.length) {
                format = args[++i].trim().toLowerCase(Locale.ROOT);
            } else if (a.equals("--pairs") && i + 1 < args.length) {
                pairsFile = args[++i];
            } else if (a.equals("--seqlib") && i + 1 < args.length) {
                seqlibFile = args[++i];
            } else if (a.equals("-m") && i + 1 < args.length) {
                matrixFile = args[++i];
            } else if (a.equals("--nw")) {
                nw = true;
            } else if (a.equals("--go") && i + 1 < args.length) {
                go = Long.parseLong(args[++i]);
            } else if (a.equals("--ge") && i + 1 < args.length) {
                ge = Long.parseLong(args[++i]);
            } else if (a.equals("--dpmatrices") && i + 1 < args.length) {
                dpmatricesDir = args[++i];
            } else if (a.equals("--check")) {
                check = true;
            } else if (a.equals("--levitt") && i + 1 < args.length) {
                levittFile = args[++i];
            } else if (a.equals("--seqlib-ss") && i + 1 < args.length) {
                seqlibSsFile = args[++i];
            } else if (a.equals("--ss-weight") && i + 1 < args.length) {
                ssWeight = Double.parseDouble(args[++i]);
            }
        }

        if (pairsFile == null || seqlibFile == null || matrixFile == null) {
            System.out.print(help());
            return;
        }
        if (!mode.equals("global") && !mode.equals("local") && !mode.equals("freeshift")) {
            System.out.print(help());
            return;
        }
        if (!format.equals("scores") && !format.equals("ali") && !format.equals("html")) {
            System.out.print(help());
            return;
        }

        SubstMatrix mat = SubstMatrix.load(Path.of(matrixFile));
        int scale = mat.getScoreScale();

        alignment.SsMatrix levitt = null;
        java.util.Map<String, String> ssLib = new java.util.HashMap<>();
        if (levittFile != null) {
            try {
                levitt = alignment.SsMatrix.load(Path.of(levittFile));
            } catch (Exception e) {
                System.err.println("Warning: could not load Levitt matrix: " + e.getMessage());
            }
        }
        if (seqlibSsFile != null) {
            ssLib = readSeqLib(seqlibSsFile);
        }
        if (ssWeight <= 0 || ssWeight > 1) ssWeight = 0.3;

        if (nw) {
            // Needleman-Wunsch / Smith-Waterman (lineare Gaps: nur ge verwendet)
            Map<String, String> sequences = readSeqLib(seqlibFile);
            long goScaled = go * scale;
            long geScaled = ge * scale;
            GlobalAlignment ga = new GlobalAlignment(mat, goScaled, geScaled);
            LocalAlignment la = new LocalAlignment(mat, goScaled, geScaled);
            FreeShiftAlignment fa = new FreeShiftAlignment(mat, goScaled, geScaled);

            try (BufferedReader br = new BufferedReader(new FileReader(pairsFile))) {
                String line;
                while ((line = br.readLine()) != null) {
                    line = line.trim();
                    if (line.isEmpty()) continue;
                    String[] p = line.split("\\s+");
                    if (p.length < 2) continue;
                    String id1Raw = p[0];
                    String id2Raw = p[1];
                    String s1 = sequences.get(id1Raw);
                    String s2 = sequences.get(id2Raw);
                    if (s1 == null || s2 == null) continue;

                    long scoreScaled;
                    String[] ali = null;
                    if (mode.equals("global")) {
                        scoreScaled = ga.computeScore(s1, s2);
                        if (format.equals("ali") || format.equals("html")) ali = ga.alignment(s1, s2);
                    } else if (mode.equals("local")) {
                        scoreScaled = la.computeScore(s1, s2);
                        if (format.equals("ali") || format.equals("html")) ali = la.alignment(s1, s2);
                    } else {
                        scoreScaled = fa.computeScore(s1, s2);
                        if (format.equals("ali") || format.equals("html")) ali = fa.alignment(s1, s2);
                    }

                    double score = scoreScaled / (double) scale;
                    if (format.equals("scores")) {
                        System.out.printf(Locale.US, "%s %s %.4f%n", id1Raw, id2Raw, score);
                    } else if (ali != null && ali.length == 2) {
                        printAli(id1Raw, id2Raw, ali[0], ali[1], score);
                        if (format.equals("html")) {
                            System.out.printf(Locale.US, "<p>%s %s %.4f</p>%n", id1Raw, id2Raw, score);
                        }
                    }
                }
            }
        } else {
            // Gotoh (Standard, affine Gaps)
            AlignmentTool.SeqLib lib = AlignmentTool.SeqLib.load(Paths.get(seqlibFile));
            List<AlignmentTool.Pair> pairs = AlignmentTool.readPairs(Paths.get(pairsFile));
            long goScaled = go * scale;
            long geScaled = ge * scale;
            AlignmentTool.Mode gotohMode = mode.equals("local") ? AlignmentTool.Mode.LOCAL
                    : mode.equals("freeshift") ? AlignmentTool.Mode.FREESHIFT : AlignmentTool.Mode.GLOBAL;

            for (AlignmentTool.Pair p : pairs) {
                String s1 = lib.get(p.id1);
                String s2 = lib.get(p.id2);
                if (s1 == null || s2 == null)
                    throw new IllegalArgumentException("Unknown id: " + p.id1 + " or " + p.id2);

                Path dpPath = dpmatricesDir != null ? Paths.get(dpmatricesDir) : null;
                String dpPrefix = dpmatricesDir != null ? (p.id1 + "_" + p.id2).replaceAll("[^A-Za-z0-9_-]", "_") : null;
                String ss1 = ssLib.get(p.id1);
                String ss2 = ssLib.get(p.id2);
                boolean useSS = (levitt != null && ss1 != null && ss2 != null && ss1.length() == s1.length() && ss2.length() == s2.length());
                AlignmentTool.GotohResult res = AlignmentTool.gotohAlign(s1, s2, mat, goScaled, geScaled, gotohMode, dpPath, dpPrefix,
                        useSS ? ss1 : null, useSS ? ss2 : null, levitt, useSS ? ssWeight : 0.0);
                double score = (double) res.score / scale;

                if (check) {
                    long cs = AlignmentTool.checkscore(res.fullAlignedA, res.fullAlignedB, mat, goScaled, geScaled);
                    if (cs != res.score)
                        System.err.println("checkscore mismatch " + p.id1 + " " + p.id2 + " computed=" + res.score + " checkscore=" + cs);
                }

                if (format.equals("scores")) {
                    System.out.printf(Locale.US, "%s %s %.4f%n", p.id1, p.id2, score);
                } else if (format.equals("html")) {
                    if (p.id1.equals(pairs.get(0).id1) && p.id2.equals(pairs.get(0).id2)) {
                        System.out.println("<!DOCTYPE html><html><head><meta charset=\"utf-8\"><title>Alignment</title>");
                        System.out.println("<style>.ali-match{color:#0d6b5c;font-weight:bold;} .ali-pos{color:#1a5fb4;} .ali-neg{color:#c01c28;} .ali-gap{color:#9a9996;}</style></head><body>");
                        System.out.println("<p><a href=\"../alignment.html\">← Zurück zur Alignment-Seite</a></p>");
                    }
                    System.out.println(formatAlignmentHtml(p.id1, p.id2, res.fullAlignedA, res.fullAlignedB, score, mat));
                    if (res.fullAlignedSS1 != null && res.fullAlignedSS2 != null) {
                        System.out.println("<div class=\"ali-ss-block\"><div class=\"ali-ss-title\">Sekund&auml;rstruktur (aligned)</div>");
                        System.out.println("<p class=\"ali-ss-expl\">Derselbe Pfad wie das Aminos&auml;ure-Alignment direkt dar&uuml;ber &ndash; hier nur die Zust&auml;nde H/E/C pro Position. Wo eine L&uuml;cke im Alignment ist, steht <code>-</code>.</p>");
                        System.out.println("<div class=\"ali-ss-legend\"><span class=\"ss-legend-item\"><span class=\"ss-h\">H</span> Helix</span><span class=\"ss-legend-item\"><span class=\"ss-e\">E</span> Strang</span><span class=\"ss-legend-item\"><span class=\"ss-c\">C</span> Coil</span><span class=\"ss-legend-item\"><span class=\"ss-mid-match\">|</span> Match</span><span class=\"ss-legend-item\"><span class=\"ss-mid-mismatch\">·</span> Mismatch</span></div>");
                        System.out.println("<div class=\"ali-ss-lines\"><div class=\"ali-ss-line\">" + formatSsHtml(res.fullAlignedSS1) + "</div>");
                        System.out.println("<div class=\"ali-ss-mid\">" + formatSsMidHtml(res.fullAlignedSS1, res.fullAlignedSS2) + "</div>");
                        System.out.println("<div class=\"ali-ss-line\">" + formatSsHtml(res.fullAlignedSS2) + "</div></div></div>");
                    }
                    String link1 = pdb3dLinks(p.id1);
                    String link2 = pdb3dLinks(p.id2);
                    if (!link1.isEmpty() || !link2.isEmpty()) {
                        System.out.println("<div class=\"ali-3d-block\"><span class=\"ali-3d-title\">3D-Darstellung (RCSB PDB)</span> ");
                        if (!link1.isEmpty()) System.out.print(link1);
                        if (!link1.isEmpty() && !link2.isEmpty()) System.out.print(" <span class=\"ali-3d-sep\">|</span> ");
                        if (!link2.isEmpty()) System.out.print(link2);
                        System.out.println("</div>");
                    }
                    if (p == pairs.get(pairs.size() - 1)) {
                        System.out.println("</body></html>");
                    }
                } else {
                    printAli(p.id1, p.id2, res.fullAlignedA, res.fullAlignedB, score);
                    if (res.fullAlignedSS1 != null && res.fullAlignedSS2 != null) {
                        System.out.println(p.id1 + "_ss: " + res.fullAlignedSS1);
                        System.out.println(p.id2 + "_ss: " + res.fullAlignedSS2);
                    }
                }
            }
        }
    }
}
