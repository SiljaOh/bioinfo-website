package alignment;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

public class SubstMatrix {

    final Map<Character, Integer> idx = new HashMap<>();
    final long[][] sc;
    final int scale;

    public SubstMatrix(long[][] sc, Map<Character, Integer> idx, int scale) {
        this.sc = sc;
        this.idx.putAll(idx);
        this.scale = scale;
    }

    public int getScoreScale() { return scale; }

    public long score(char a, char b) {
        Integer ia = idx.get(Character.toUpperCase(a));
        Integer ib = idx.get(Character.toUpperCase(b));
        if (ia == null || ib == null) {
            throw new IllegalArgumentException("Unknown residue: '" + a + "' or '" + b + "'");
        }
        return sc[ia][ib];
    }

    public static SubstMatrix load(Path p) throws IOException {
        String row = null;
        String col = null;
        List<double[]> tri = new ArrayList<>();

        try (BufferedReader br = Files.newBufferedReader(p, StandardCharsets.UTF_8)) {
            for (String line; (line = br.readLine()) != null; ) {
                String t = line.trim();
                if (t.isEmpty() || t.startsWith("#") || t.startsWith(";") || t.startsWith("//")) continue;

                if (t.startsWith("ROWINDEX")) {
                    String[] s = t.split("\\s+");
                    if (s.length > 1) row = s[1].trim();
                } else if (t.startsWith("COLINDEX")) {
                    String[] s = t.split("\\s+");
                    if (s.length > 1) col = s[1].trim();
                } else if (t.startsWith("MATRIX")) {
                    String rest = t.substring("MATRIX".length()).trim();
                    if (rest.isEmpty()) continue;
                    String[] nums = rest.split("\\s+");
                    double[] r = new double[nums.length];
                    for (int i = 0; i < nums.length; i++) r[i] = Double.parseDouble(nums[i]);
                    tri.add(r);
                }
            }
        }

        if (row == null || col == null) throw new IllegalArgumentException("Matrix missing ROWINDEX/COLINDEX: " + p);
        if (row.length() != col.length()) throw new IllegalArgumentException("ROWINDEX/COLINDEX length mismatch.");
        int n = row.length();
        if (tri.size() < n) throw new IllegalArgumentException("Matrix incomplete: expected " + n + " MATRIX rows, got " + tri.size());

        Map<Character, Integer> idx = new HashMap<>();
        for (int i = 0; i < n; i++) idx.put(Character.toUpperCase(row.charAt(i)), i);

        boolean dec = false;
        outer:
        for (int r = 0; r < n; r++) {
            double[] rr = tri.get(r);
            for (int c = 0; c <= r && c < rr.length; c++) {
                if (Math.abs(rr[c] - Math.round(rr[c])) > 1e-9) {
                    dec = true;
                    break outer;
                }
            }
        }
        int scale = dec ? 10 : 1;

        long[][] sc = new long[n][n];
        for (int r = 0; r < n; r++) {
            double[] rr = tri.get(r);
            if (rr.length < r + 1) throw new IllegalArgumentException("MATRIX row " + r + " too short.");
            for (int c = 0; c <= r; c++) {
                long v = (scale == 10) ? Math.round(rr[c] * 10) : Math.round(rr[c]);
                sc[r][c] = v;
                sc[c][r] = v;
            }
        }

        return new SubstMatrix(sc, idx, scale);
    }
}