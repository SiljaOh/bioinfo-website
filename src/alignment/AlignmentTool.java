package alignment;

import java.awt.image.BufferedImage;
import java.awt.Graphics2D;
import java.awt.Color;
import java.awt.Font;
import javax.imageio.ImageIO;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/*
commandline Alignment Tool für Pairwise Alignments von Proteinsequenzen
Sequenzen aus einer seqlib lädt, Paare aus pairs-Datei lädt, eine Substitutionsmatrix lädt
Gotoh berechnet pro Paar ein Alignment(affine Gaps)
Ausgabe: Score v Score + Alignment
 */

public class AlignmentTool{

    enum Mode { GLOBAL, LOCAL, FREESHIFT } //erlaubte Werte für -- Mode
    enum Format { SCORES, ALI } // erlaubte Werte für -- format


    private static final long NEG_INF = Long.MIN_VALUE / 4; // Use long everywhere to avoid overflow. /4 gibt puffer für zustände die "unmöglich" sind

    public static void main(String[] args) throws Exception {
        //Argumente parsen
        Args a = Args.parse(args);
        if (a == null) {
            System.out.println(Args.help());
            return;
        }
        //Daten einlesen, baut map, SubstMatrix.load : liest SUbstitutionsmatirx und baut Scoring-Objekt
        SeqLib lib = SeqLib.load(a.seqlibPath);
        SubstMatrix mat = SubstMatrix.load(a.matrixPath);
        int scale = mat.getScoreScale();
        long goScaled = a.go * scale; //damit Dezimalwerte auf long WErte
        long geScaled = a.ge * scale;

        List<Pair> pairs = readPairs(a.pairsPath);

        //über alle Paare iterieren, Alignment rechnen, Output bauen
        StringBuilder out = new StringBuilder();
        for (Pair p : pairs) {
            String s1 = lib.get(p.id1);
            String s2 = lib.get(p.id2);
            if (s1 == null || s2 == null) {
                throw new IllegalArgumentException("Pair references unknown id: " + p.id1 + " or " + p.id2);
            }

            GotohResult res = gotohAlign(s1, s2, mat, goScaled, geScaled, a.mode);
            //Ausgabe-Format scores
            if (a.format == Format.SCORES) {
                out.append(p.id1).append(" ").append(p.id2).append(" ")
                        .append(String.format(Locale.US, "%.4f", (double) res.score / scale))
                        .append("\n");
            } else {
                //Ausgabe-Format ali
                String fullA = res.fullAlignedA;
                String fullB = res.fullAlignedB;
                out.append(">").append(p.id1).append(" ").append(p.id2).append(" ")
                        .append(String.format(Locale.US, "%.4f", (double) res.score / scale))
                        .append("\n");
                out.append(p.id1).append(": ").append(fullA).append("\n");
                out.append(p.id2).append(": ").append(fullB).append("\n");

                // Kein #checkscore in Ausgabe – Server erwartet nur Header + 2 Sequenzzeilen
            }
        }

        System.out.print(out);
    }


    static class GotohResult {
        final long score;
        final String alignedA;
        final String alignedB;
        final String fullAlignedA;
        final String fullAlignedB;
        /** When SS-aided alignment was used: aligned secondary structure (same length as fullAlignedA/B). */
        final String fullAlignedSS1;
        final String fullAlignedSS2;

        GotohResult(long score, String alignedA, String alignedB, String fullAlignedA, String fullAlignedB) {
            this(score, alignedA, alignedB, fullAlignedA, fullAlignedB, null, null);
        }
        GotohResult(long score, String alignedA, String alignedB, String fullAlignedA, String fullAlignedB, String fullAlignedSS1, String fullAlignedSS2) {
            this.score = score;
            this.alignedA = alignedA;
            this.alignedB = alignedB;
            this.fullAlignedA = fullAlignedA;
            this.fullAlignedB = fullAlignedB;
            this.fullAlignedSS1 = fullAlignedSS1;
            this.fullAlignedSS2 = fullAlignedSS2;
        }
    }

    // Trace codes for backtracking
    // M: came from diag of (M/Ix/Iy), or from ZERO (local)
    private static final byte TM_FROM_M  = 1;
    private static final byte TM_FROM_IX = 2;
    private static final byte TM_FROM_IY = 3;
    private static final byte TM_FROM_0  = 4; // local reset

    // Ix: came from M (open), Ix (extend), Iy (open new gap in B), or ZERO (local)
    private static final byte TX_FROM_M  = 1;
    private static final byte TX_FROM_IX = 2;
    private static final byte TX_FROM_0  = 3;
    private static final byte TX_FROM_IY = 4;

    // Iy: came from M (open), Iy (extend), Ix (open new gap in A), or ZERO (local)
    private static final byte TY_FROM_M  = 1;
    private static final byte TY_FROM_IY = 2;
    private static final byte TY_FROM_0  = 3;
    private static final byte TY_FROM_IX = 4;

    // Zustands-IDs für Backtracking
    private static final int ST_M  = 0;
    private static final int ST_IX = 1;
    private static final int ST_IY = 2;


    static GotohResult gotohAlign(String A, String B, SubstMatrix mat, long go, long ge, Mode mode) {
        return gotohAlign(A, B, mat, go, ge, mode, null, null, null, null, null, 0.0);
    }

    static GotohResult gotohAlign(String A, String B, SubstMatrix mat, long go, long ge, Mode mode, Path dpMatricesDir, String filePrefix) {
        return gotohAlign(A, B, mat, go, ge, mode, dpMatricesDir, filePrefix, null, null, null, 0.0);
    }

    /**
     * Optional: ss1/ss2 = secondary structure strings (H/E/C per residue, same length as A/B).
     * levitt != null and ssWeight > 0 → combined score = seq_score + ssWeight * scale * levitt.score(ss1[i],ss2[j]).
     */
    static GotohResult gotohAlign(String A, String B, SubstMatrix mat, long go, long ge, Mode mode, Path dpMatricesDir, String filePrefix, String ss1, String ss2, SsMatrix levitt, double ssWeight) {
        int n = A.length();
        int m = B.length();
        boolean useSS = (levitt != null && ssWeight > 0 && ss1 != null && ss2 != null && ss1.length() == n && ss2.length() == m);
        int seqScale = mat.getScoreScale();
        long ssScale = useSS ? (long) (ssWeight * seqScale) : 0;

        char[] a = (" " + A).toCharArray();
        char[] b = (" " + B).toCharArray();

        //Matrizen anlegen
        long[][] M  = new long[n + 1][m + 1];
        long[][] Ix = new long[n + 1][m + 1];
        long[][] Iy = new long[n + 1][m + 1];

        byte[][] tM  = new byte[n + 1][m + 1];
        byte[][] tIx = new byte[n + 1][m + 1];
        byte[][] tIy = new byte[n + 1][m + 1];

        // Initialisierung
        initMatrices(M, Ix, Iy, tM, tIx, tIy, n, m, go, ge, mode);

        // Fill-loop und bestScore Tracking
        long bestScore = (mode == Mode.LOCAL) ? 0 : NEG_INF;
        int bestI = 0, bestJ = 0, bestState = ST_M;

        for (int i = 1; i <= n; i++) {
            for (int j = 1; j <= m; j++) {

                // Ix (gap in B): (i-1,j) -> (i,j). Open from M or Iy, extend from Ix.
                long fromM_open = safeAdd(M[i - 1][j], go + ge);
                long fromX_ext  = safeAdd(Ix[i - 1][j], ge);
                long fromY_open = safeAdd(Iy[i - 1][j], go + ge);

                long ixVal = fromM_open;
                byte ixTrace = TX_FROM_M;
                if (fromX_ext > ixVal) { ixVal = fromX_ext; ixTrace = TX_FROM_IX; }
                if (fromY_open > ixVal) { ixVal = fromY_open; ixTrace = TX_FROM_IY; }

                // Iy (gap in A): (i,j-1) -> (i,j). Open from M or Ix, extend from Iy.
                long fromM_openY = safeAdd(M[i][j - 1], go + ge);
                long fromY_ext   = safeAdd(Iy[i][j - 1], ge);
                long fromX_open  = safeAdd(Ix[i][j - 1], go + ge);

                long iyVal = fromM_openY;
                byte iyTrace = TY_FROM_M;
                if (fromY_ext > iyVal) { iyVal = fromY_ext; iyTrace = TY_FROM_IY; }
                if (fromX_open > iyVal) { iyVal = fromX_open; iyTrace = TY_FROM_IX; }

                // M (match/mismatch): (i-1,j-1) -> (i,j)
                long diagM  = M[i - 1][j - 1];
                long diagIx = Ix[i - 1][j - 1];
                long diagIy = Iy[i - 1][j - 1];

                long bestDiag = diagM;
                byte mTrace = TM_FROM_M;
                if (diagIx > bestDiag) { bestDiag = diagIx; mTrace = TM_FROM_IX; }
                if (diagIy > bestDiag) { bestDiag = diagIy; mTrace = TM_FROM_IY; }

                long sub = mat.score(a[i], b[j]);
                if (useSS) sub += ssScale * levitt.score(ss1.charAt(i - 1), ss2.charAt(j - 1));
                long mVal = safeAdd(bestDiag, sub);

                // Local-Mode Anpassung(Reset auf 0)(wie smith-waterman Prinzip negative Scores auf 0)
                if (mode == Mode.LOCAL) {
                    // allow reset to 0
                    if (ixVal < 0) { ixVal = 0; ixTrace = TX_FROM_0; }
                    if (iyVal < 0) { iyVal = 0; iyTrace = TY_FROM_0; }
                    if (mVal  < 0) { mVal  = 0; mTrace  = TM_FROM_0; }
                }
                //Werte speichern
                Ix[i][j] = ixVal; tIx[i][j] = ixTrace;
                Iy[i][j] = iyVal; tIy[i][j] = iyTrace;
                M[i][j]  = mVal;  tM[i][j]  = mTrace;

                // Track best for local, or for freeshift we handle after fill.
                if (mode == Mode.LOCAL) {
                    // best anywhere across all 3
                    if (M[i][j] > bestScore) { bestScore = M[i][j]; bestI = i; bestJ = j; bestState = ST_M; }
                    if (Ix[i][j] > bestScore){ bestScore = Ix[i][j]; bestI = i; bestJ = j; bestState = ST_IX; }
                    if (Iy[i][j] > bestScore){ bestScore = Iy[i][j]; bestI = i; bestJ = j; bestState = ST_IY; }
                }
            }
        }

        // GLOBAL nach dem fill wählen wo ich starte
        int startI, startJ, startState;
        long finalScore;

        if (mode == Mode.GLOBAL) {
            startI = n; startJ = m;
            long sM = M[n][m], sX = Ix[n][m], sY = Iy[n][m];
            if (sM >= sX && sM >= sY) { finalScore = sM; startState = ST_M; }
            else if (sX >= sY)        { finalScore = sX; startState = ST_IX; }
            else                      { finalScore = sY; startState = ST_IY; }
        } else if (mode == Mode.LOCAL) {
            startI = bestI; startJ = bestJ; startState = bestState; finalScore = bestScore;
        } else { // FREESHIFT (semi-global): best on last row or last column (across states)
            long best = NEG_INF;
            int bi = n, bj = m, bs = ST_M;

            // last row: i=n, j=0..m
            for (int j = 0; j <= m; j++) {
                if (M[n][j]  > best) { best = M[n][j];  bi = n; bj = j; bs = ST_M; }
                if (Ix[n][j] > best) { best = Ix[n][j]; bi = n; bj = j; bs = ST_IX; }
                if (Iy[n][j] > best) { best = Iy[n][j]; bi = n; bj = j; bs = ST_IY; }
            }
            // last col: j=m, i=0..n
            for (int i = 0; i <= n; i++) {
                if (M[i][m]  > best) { best = M[i][m];  bi = i; bj = m; bs = ST_M; }
                if (Ix[i][m] > best) { best = Ix[i][m]; bi = i; bj = m; bs = ST_IX; }
                if (Iy[i][m] > best) { best = Iy[i][m]; bi = i; bj = m; bs = ST_IY; }
            }

            startI = bi; startJ = bj; startState = bs; finalScore = best;
        }

        // Backtrack (+ aligned SS when useSS), collect path for DP heatmap
        List<int[]> path = new ArrayList<>();
        StringBuilder alA = new StringBuilder();
        StringBuilder alB = new StringBuilder();
        StringBuilder alSS1 = useSS ? new StringBuilder() : null;
        StringBuilder alSS2 = useSS ? new StringBuilder() : null;
        int i = startI, j = startJ, st = startState;

        while (i > 0 || j > 0) {
            path.add(new int[]{ i, j });
            if (mode == Mode.LOCAL) {
                if (st == ST_M && tM[i][j] == TM_FROM_0) break;
                if (st == ST_IX && tIx[i][j] == TX_FROM_0) break;
                if (st == ST_IY && tIy[i][j] == TY_FROM_0) break;
            }
            if (st == ST_M && (i <= 0 || j <= 0)) break;
            if (st == ST_IX && i <= 0) break;
            if (st == ST_IY && j <= 0) break;

            if (st == ST_M) {
                byte tr = tM[i][j];
                alA.append(a[i]);
                alB.append(b[j]);
                if (useSS) { alSS1.append(ss1.charAt(i - 1)); alSS2.append(ss2.charAt(j - 1)); }
                i--; j--;
                if (tr == TM_FROM_M) st = ST_M;
                else if (tr == TM_FROM_IX) st = ST_IX;
                else if (tr == TM_FROM_IY) st = ST_IY;
                else break; // local reset
            } else if (st == ST_IX) {
                byte tr = tIx[i][j];
                alA.append(a[i]);
                alB.append('-');
                if (useSS) { alSS1.append(ss1.charAt(i - 1)); alSS2.append('-'); }
                i--;
                if (tr == TX_FROM_M) st = ST_M;
                else if (tr == TX_FROM_IX) st = ST_IX;
                else if (tr == TX_FROM_IY) st = ST_IY;
                else break;
            } else { // ST_IY
                byte tr = tIy[i][j];
                alA.append('-');
                alB.append(b[j]);
                if (useSS) { alSS1.append('-'); alSS2.append(ss2.charAt(j - 1)); }
                j--;
                if (tr == TY_FROM_M) st = ST_M;
                else if (tr == TY_FROM_IY) st = ST_IY;
                else if (tr == TY_FROM_IX) st = ST_IX;
                else break;
            }

            // Safety (shouldn't happen, but avoids infinite loop if traces are broken)
            if (i < 0 || j < 0) break;
        }
        if (i >= 0 && j >= 0) path.add(new int[]{ i, j });
        Collections.reverse(path);

        String alignedA = alA.reverse().toString();
        String alignedB = alB.reverse().toString();
        String alignedSS1 = useSS ? alSS1.reverse().toString() : null;
        String alignedSS2 = useSS ? alSS2.reverse().toString() : null;

        String fullA = alignedA;
        String fullB = alignedB;
        String fullSS1 = alignedSS1;
        String fullSS2 = alignedSS2;
        if ((mode == Mode.LOCAL || mode == Mode.FREESHIFT) && (i > 0 || j > 0 || startI < n || startJ < m)) {
            int endI = Math.max(0, i);
            int endJ = Math.max(0, j);
            int si = Math.min(startI, n);
            int sj = Math.min(startJ, m);
            int suffixGapsA = Math.max(0, m - sj);
            int suffixGapsB = Math.max(0, n - si);
            String prefixA = A.substring(0, endI) + "-".repeat(endJ);
            String prefixB = "-".repeat(endI) + B.substring(0, endJ);
            String suffixA = A.substring(si, n) + "-".repeat(suffixGapsA);
            String suffixB = "-".repeat(suffixGapsB) + B.substring(sj, m);
            fullA = prefixA + alignedA + suffixA;
            fullB = prefixB + alignedB + suffixB;
            if (useSS) {
                String pSS1 = ss1.substring(0, endI) + "-".repeat(endJ);
                String pSS2 = "-".repeat(endI) + ss2.substring(0, endJ);
                String sSS1 = ss1.substring(si, n) + "-".repeat(suffixGapsA);
                String sSS2 = ss2.substring(sj, m) + "-".repeat(suffixGapsB);
                fullSS1 = pSS1 + alignedSS1 + sSS1;
                fullSS2 = pSS2 + alignedSS2 + sSS2;
            }
        }

        if (dpMatricesDir != null && filePrefix != null) {
            try {
                writeDpMatrices(dpMatricesDir, filePrefix, M, Ix, Iy, n, m, path);
            } catch (IOException e) {
                System.err.println("Warning: could not write DP matrices: " + e.getMessage());
            }
        }

        return new GotohResult(finalScore, alignedA, alignedB, fullA, fullB, fullSS1, fullSS2);
    }

    private static void initMatrices(
            long[][] M, long[][] Ix, long[][] Iy,
            byte[][] tM, byte[][] tIx, byte[][] tIy,
            int n, int m, long go, long ge, Mode mode
    ) {
        // Fill with NEG_INF by default
        for (int i = 0; i <= n; i++) {
            Arrays.fill(M[i], NEG_INF);
            Arrays.fill(Ix[i], NEG_INF);
            Arrays.fill(Iy[i], NEG_INF);
        }

        if (mode == Mode.GLOBAL) {
            M[0][0] = 0;
            Ix[0][0] = Iy[0][0] = NEG_INF;

            // first column: align A[1..i] with gaps in B => Ix valid
            for (int i = 1; i <= n; i++) {
                Ix[i][0] = go + (long) i * ge;
                tIx[i][0] = (i == 1) ? TX_FROM_M : TX_FROM_IX; // not used much at borders
                // M[i][0], Iy[i][0] stay NEG_INF
            }
            // first row: align B[1..j] with gaps in A => Iy valid
            for (int j = 1; j <= m; j++) {
                Iy[0][j] = go + (long) j * ge;
                tIy[0][j] = (j == 1) ? TY_FROM_M : TY_FROM_IY;
                // M[0][j], Ix[0][j] stay NEG_INF
            }
        }
        else if (mode == Mode.LOCAL) {
            // local: allow start anywhere -> 0 baseline
            for (int i = 0; i <= n; i++) {
                M[i][0] = 0; Ix[i][0] = 0; Iy[i][0] = 0;
                tM[i][0] = TM_FROM_0; tIx[i][0] = TX_FROM_0; tIy[i][0] = TY_FROM_0;
            }
            for (int j = 0; j <= m; j++) {
                M[0][j] = 0; Ix[0][j] = 0; Iy[0][j] = 0;
                tM[0][j] = TM_FROM_0; tIx[0][j] = TX_FROM_0; tIy[0][j] = TY_FROM_0;
            }
        }
        else { // FREESHIFT (semi-global): free end gaps and free start shifts (common variant)
            // Make starts along borders free (0) so you can "shift" without penalty.
            for (int i = 0; i <= n; i++) {
                M[i][0] = 0;
                Ix[i][0] = 0;
                Iy[i][0] = NEG_INF;
                tM[i][0] = TM_FROM_0;
                tIx[i][0] = TX_FROM_0;
            }
            for (int j = 0; j <= m; j++) {
                M[0][j] = 0;
                Iy[0][j] = 0;
                Ix[0][j] = NEG_INF;
                tM[0][j] = TM_FROM_0;
                tIy[0][j] = TY_FROM_0;
            }
            // Note: This variant is often "good enough" for course freeshift.
            // If your reference scores differ, adjust init + where you take the max at the end.
        }
    }

    // NEG_INF + irgendwas = NEG_INF
    private static long safeAdd(long x, long y) {
        if (x <= NEG_INF / 2) return NEG_INF;
        // We don't expect overflow with realistic scores, but keep it safe-ish:
        long r = x + y;
        // If overflow happens, clamp (very unlikely here)
        if (((x ^ r) & (y ^ r)) < 0) {
            return (r < 0) ? Long.MIN_VALUE / 2 : Long.MAX_VALUE / 2;
        }
        return r;
    }


    /** Schreibt M, Ix, Iy als Textdateien, M als Heatmap-PNG (mit Trace-back) und optional path-Datei für Zahlen-Ansicht. */
    private static void writeDpMatrices(Path dir, String prefix, long[][] M, long[][] Ix, long[][] Iy, int n, int m, List<int[]> path) throws IOException {
        Files.createDirectories(dir);
        String safe = prefix.replaceAll("[^A-Za-z0-9_-]", "_");
        writeMatrixText(dir.resolve(safe + "_M.txt"), M, n, m);
        writeMatrixText(dir.resolve(safe + "_Ix.txt"), Ix, n, m);
        writeMatrixText(dir.resolve(safe + "_Iy.txt"), Iy, n, m);
        writeMatrixPng(dir.resolve(safe + "_M.png"), M, n, m, path);
        if (path != null && !path.isEmpty()) {
            try (Writer w = Files.newBufferedWriter(dir.resolve(safe + "_path.txt"), StandardCharsets.UTF_8)) {
                for (int[] pt : path) {
                    w.write(pt[0] + "\t" + pt[1] + "\n");
                }
            }
        }
    }

    private static void writeMatrixText(Path p, long[][] M, int n, int m) throws IOException {
        try (Writer w = Files.newBufferedWriter(p, StandardCharsets.UTF_8)) {
            for (int i = 0; i <= n; i++) {
                for (int j = 0; j <= m; j++) {
                    if (j > 0) w.write("\t");
                    long v = M[i][j];
                    w.write(v <= NEG_INF / 2 ? "-inf" : String.valueOf(v));
                }
                w.write("\n");
            }
        }
    }

    /** Heatmap: jede Zelle als Block, Achsen, Farbskala; optional Trace-back-Pfad (rot) eingezeichnet. */
    private static void writeMatrixPng(Path p, long[][] M, int n, int m, List<int[]> path) throws IOException {
        long minVal = Long.MAX_VALUE, maxVal = Long.MIN_VALUE;
        for (int i = 0; i <= n; i++) {
            for (int j = 0; j <= m; j++) {
                long v = M[i][j];
                if (v > NEG_INF / 2) {
                    if (v < minVal) minVal = v;
                    if (v > maxVal) maxVal = v;
                }
            }
        }
        if (minVal == Long.MAX_VALUE) minVal = maxVal = 0;
        long range = Math.max(1, maxVal - minVal);

        final int cellSize = 6;
        final int marginLeft = 32;
        final int marginRight = 52;
        final int marginTop = 24;
        final int marginBottom = 28;
        int matrixW = (m + 1) * cellSize;
        int matrixH = (n + 1) * cellSize;
        int totalW = marginLeft + matrixW + marginRight;
        int totalH = marginTop + matrixH + marginBottom;

        BufferedImage img = new BufferedImage(totalW, totalH, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = img.createGraphics();
        g.setColor(Color.WHITE);
        g.fillRect(0, 0, totalW, totalH);

        for (int i = 0; i <= n; i++) {
            for (int j = 0; j <= m; j++) {
                long v = M[i][j];
                double t;
                if (v <= NEG_INF / 2) {
                    t = 0;
                    g.setColor(new Color(40, 40, 80));
                } else {
                    t = (double) (v - minVal) / range;
                    int r = (int) (t * 255);
                    int gb = (int) ((1 - t) * 255);
                    g.setColor(new Color(r, 128 + (int)(t * 127), Math.max(0, gb)));
                }
                int x = marginLeft + j * cellSize;
                int y = marginTop + i * cellSize;
                g.fillRect(x, y, cellSize, cellSize);
            }
        }

        g.setColor(Color.DARK_GRAY);
        g.setFont(new Font("SansSerif", Font.PLAIN, 10));
        int tickStepY = Math.max(1, (n + 1) / 12);
        for (int i = 0; i <= n; i += tickStepY) {
            String lab = String.valueOf(i);
            int y = marginTop + i * cellSize + cellSize / 2 + 4;
            int x = Math.max(2, marginLeft - 6 * lab.length());
            g.drawString(lab, x, y);
        }
        int tickStepX = Math.max(1, (m + 1) / 12);
        for (int j = 0; j <= m; j += tickStepX) {
            String lab = String.valueOf(j);
            int x = marginLeft + j * cellSize + cellSize / 2 - 3 * lab.length();
            if (x < marginLeft) x = marginLeft;
            g.drawString(lab, x, marginTop + matrixH + 16);
        }
        g.drawString("i (Seq1)", 4, marginTop + matrixH / 2 + 4);
        g.drawString("j (Seq2)", marginLeft + matrixW / 2 - 20, totalH - 6);

        int barX = marginLeft + matrixW + 8;
        int barW = 12;
        int barH = matrixH;
        for (int dy = 0; dy < barH; dy++) {
            double t = 1 - (double) dy / barH;
            int r = (int) (t * 255);
            int gb = (int) ((1 - t) * 255);
            g.setColor(new Color(r, 128 + (int)(t * 127), Math.max(0, gb)));
            g.fillRect(barX, marginTop + dy, barW, 1);
        }
        g.setColor(Color.BLACK);
        g.drawRect(barX, marginTop, barW, barH);
        g.setFont(new Font("SansSerif", Font.PLAIN, 9));
        g.drawString(String.valueOf(maxVal), barX + barW + 2, marginTop + 10);
        g.drawString(String.valueOf(minVal), barX + barW + 2, marginTop + barH - 2);

        // Trace-back-Pfad einzeichnen (rot, Zellmittelpunkte verbunden)
        if (path != null && path.size() > 1) {
            g.setColor(new Color(220, 40, 40));
            g.setStroke(new java.awt.BasicStroke(1.5f));
            int cx0 = marginLeft + path.get(0)[1] * cellSize + cellSize / 2;
            int cy0 = marginTop + path.get(0)[0] * cellSize + cellSize / 2;
            for (int idx = 1; idx < path.size(); idx++) {
                int[] pt = path.get(idx);
                int cx = marginLeft + pt[1] * cellSize + cellSize / 2;
                int cy = marginTop + pt[0] * cellSize + cellSize / 2;
                g.drawLine(cx0, cy0, cx, cy);
                cx0 = cx;
                cy0 = cy;
            }
        }

        g.dispose();
        ImageIO.write(img, "png", p.toFile());
    }

    //score eines gegebenen Alignments nachrechnen, unabhängig von DP prüfen: ist Score consistent
    static long checkscore(String alignedA, String alignedB, SubstMatrix mat, long go, long ge) {
        if (alignedA.length() != alignedB.length()) {
            throw new IllegalArgumentException("Alignment strings must have equal length.");
        }
        long score = 0;

        boolean inGapA = false; // currently in a run where A has '-' (gap in A)
        boolean inGapB = false; // currently in a run where B has '-' (gap in B)

        for (int k = 0; k < alignedA.length(); k++) {
            char ca = alignedA.charAt(k);
            char cb = alignedB.charAt(k);

            if (ca == '-' && cb == '-') {
                throw new IllegalArgumentException("Invalid alignment: both positions are gaps at k=" + k);
            }

            if (ca == '-') {
                // gap in A (align '-' with B char)
                if (!inGapA) score += (go + ge);
                else score += ge;
                inGapA = true;
                inGapB = false;
            } else if (cb == '-') {
                // gap in B (align A char with '-')
                if (!inGapB) score += (go + ge);
                else score += ge;
                inGapB = true;
                inGapA = false;
            } else {
                // match/mismatch
                score += mat.score(ca, cb);
                inGapA = false;
                inGapB = false;
            }
        }

        return score;
    }


    static class Pair {
        final String id1, id2;
        Pair(String id1, String id2) { this.id1 = id1; this.id2 = id2; }
    }

    static List<Pair> readPairs(Path p) throws IOException {
        List<String> lines = Files.readAllLines(p, StandardCharsets.UTF_8);
        List<Pair> res = new ArrayList<>();
        for (String line : lines) {
            line = line.trim();
            if (line.isEmpty() || line.startsWith("#")) continue;
            String[] tok = line.split("\\s+");
            if (tok.length < 2) continue;
            res.add(new Pair(tok[0], tok[1]));
        }
        return res;
    }

    static class SeqLib {
        private final Map<String, String> idToSeq = new HashMap<>();

        static SeqLib load(Path p) throws IOException {
            SeqLib lib = new SeqLib();
            List<String> lines = Files.readAllLines(p, StandardCharsets.UTF_8);
            for (String line : lines) {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("#")) continue;
                int idx = line.indexOf(':');
                if (idx < 1) continue;
                String id = line.substring(0, idx).trim();
                String seq = line.substring(idx + 1).trim();
                lib.idToSeq.put(id, seq);
            }
            return lib;
        }

        String get(String id) { return idToSeq.get(id); }
    }

    static class Args {
        Path pairsPath;
        Path seqlibPath;
        Path matrixPath;

        long go = -12;
        long ge = -1;

        Mode mode = Mode.GLOBAL;
        Format format = Format.ALI;

        static Args parse(String[] args) {
            Args a = new Args();
            for (int i = 0; i < args.length; i++) {
                String s = args[i];

                switch (s) {
                    case "--pairs":
                        a.pairsPath = Paths.get(requireNext(args, ++i, "--pairs"));
                        break;
                    case "--seqlib":
                        a.seqlibPath = Paths.get(requireNext(args, ++i, "--seqlib"));
                        break;
                    case "-m":
                        a.matrixPath = Paths.get(requireNext(args, ++i, "-m"));
                        break;
                    case "--go":
                        a.go = Long.parseLong(requireNext(args, ++i, "--go"));
                        break;
                    case "--ge":
                        a.ge = Long.parseLong(requireNext(args, ++i, "--ge"));
                        break;
                    case "--mode":
                        String md = requireNext(args, ++i, "--mode").toLowerCase(Locale.ROOT);
                        if (md.equals("global")) a.mode = Mode.GLOBAL;
                        else if (md.equals("local")) a.mode = Mode.LOCAL;
                        else if (md.equals("freeshift")) a.mode = Mode.FREESHIFT;
                        else return null;
                        break;
                    case "--format":
                        String f = requireNext(args, ++i, "--format").toLowerCase(Locale.ROOT);
                        if (f.equals("scores")) a.format = Format.SCORES;
                        else if (f.equals("ali")) a.format = Format.ALI;
                        else return null;
                        break;
                    case "-h":
                    case "--help":
                        return null;
                    default:
                        // ignore unknown flags in this minimal tester OR fail:
                        // return null;
                        break;
                }
            }

            if (a.pairsPath == null || a.seqlibPath == null || a.matrixPath == null) return null;
            return a;
        }

        static String requireNext(String[] args, int i, String flag) {
            if (i >= args.length) throw new IllegalArgumentException("Missing value for " + flag);
            return args[i];
        }

        static String help() {
            return ""
                    + "Usage:\n"
                    + "  java AlignmentTool --pairs <pairs> --seqlib <seqlib> -m <matrix> [--go -12] [--ge -1]\n"
                    + "                   [--mode global|local|freeshift] [--format scores|ali]\n"
                    + "\n"
                    + "Input formats:\n"
                    + "  seqlib:  id:SEQUENCE   (one per line)\n"
                    + "  pairs:   id1 id2 [ignored...]\n"
                    + "\n"
                    + "Gap model:\n"
                    + "  Gap(k) = go + k*ge  (first gap char costs go+ge)\n";
        }
    }
}


