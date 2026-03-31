package alignment;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

/**
 * Levitt-style 3x3 secondary structure substitution matrix (H=helix, E=sheet, C=coil).
 * Format: ROWINDEX/COLINDEX (e.g. HEC), MATRIX lines.
 */
public class SsMatrix {
    private final Map<Character, Integer> idx = new HashMap<>();
    private final long[][] sc;

    public SsMatrix(long[][] scores, String rowIndex) {
        this.sc = scores;
        for (int i = 0; i < rowIndex.length(); i++) {
            idx.put(Character.toUpperCase(rowIndex.charAt(i)), i);
        }
    }

    public long score(char c1, char c2) {
        Integer i1 = idx.get(Character.toUpperCase(c1));
        Integer i2 = idx.get(Character.toUpperCase(c2));
        if (i1 == null || i2 == null) return 0;
        return sc[i1][i2];
    }

    public static SsMatrix load(Path p) throws IOException {
        String row = null;
        int rowCount = 0;
        long[][] matrix = null;
        try (BufferedReader br = Files.newBufferedReader(p, StandardCharsets.UTF_8)) {
            String line;
            int r = 0;
            while ((line = br.readLine()) != null) {
                String t = line.trim();
                if (t.isEmpty() || t.startsWith("#") || t.startsWith(";")) continue;
                if (t.startsWith("ROWINDEX")) {
                    String[] s = t.split("\\s+");
                    if (s.length > 1) row = s[1].trim();
                } else if (t.startsWith("COLINDEX")) {
                    // optional, same as ROWINDEX for 3x3
                    if (row == null) {
                        String[] s = t.split("\\s+");
                        if (s.length > 1) row = s[1].trim();
                    }
                } else if (t.startsWith("MATRIX")) {
                    String rest = t.substring(6).trim();
                    if (rest.isEmpty()) continue;
                    String[] nums = rest.split("\\s+");
                    if (matrix == null && row != null) {
                        matrix = new long[row.length()][row.length()];
                    }
                    if (matrix != null && r < matrix.length) {
                        for (int c = 0; c < nums.length && c < matrix[r].length; c++) {
                            matrix[r][c] = Math.round(Double.parseDouble(nums[c]));
                        }
                        r++;
                    }
                }
            }
        }
        if (row == null || matrix == null) throw new IOException("SsMatrix: missing ROWINDEX or MATRIX in " + p);
        return new SsMatrix(matrix, row);
    }
}
