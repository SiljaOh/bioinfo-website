package alignment;

public class LocalAlignment {

    private final SubstMatrix mat;      // null => Pen&Paper
    private final long match;
    private final long mismatch;
    private final long gap;

    public LocalAlignment(int matchScore, int mismatchScore, int gapCost) {
        this.mat = null;
        this.match = matchScore;
        this.mismatch = mismatchScore;
        this.gap = Math.abs((long) gapCost);
    }

    public LocalAlignment(SubstMatrix mat, long go, long ge) {
        if (mat == null) throw new IllegalArgumentException("SubstMatrix must not be null");
        this.mat = mat;
        this.match = 0;
        this.mismatch = 0;
        this.gap = Math.abs(ge);
    }

    private long score(char a, char b) {
        if (mat != null) return mat.score(a, b);
        return (a == b) ? match : mismatch;
    }

    public long computeScore(String s1, String s2) {
        int n = s1.length();
        int m = s2.length();

        long[][] F = new long[n + 1][m + 1];
        long best = 0;

        for (int i = 1; i <= n; i++) {
            for (int j = 1; j <= m; j++) {
                long diag = F[i - 1][j - 1] + score(s1.charAt(i - 1), s2.charAt(j - 1));
                long up   = F[i - 1][j] - gap;
                long left = F[i][j - 1] - gap;

                long val = Math.max(0, Math.max(diag, Math.max(up, left)));
                F[i][j] = val;
                if (val > best) best = val;
            }
        }
        return best;
    }

    public String[] alignment(String s1, String s2) {
        int n = s1.length();
        int m = s2.length();

        long[][] F = new long[n + 1][m + 1];
        char[][] tb = new char[n + 1][m + 1];

        long best = 0;
        int bi = 0, bj = 0;

        for (int i = 1; i <= n; i++) {
            for (int j = 1; j <= m; j++) {
                long diag = F[i - 1][j - 1] + score(s1.charAt(i - 1), s2.charAt(j - 1));
                long up   = F[i - 1][j] - gap;
                long left = F[i][j - 1] - gap;

                long val = Math.max(0, Math.max(diag, Math.max(up, left)));
                F[i][j] = val;

                if (val == 0) tb[i][j] = 'S';
                else if (val == diag) tb[i][j] = 'D';
                else if (val == up)   tb[i][j] = 'U';
                else                  tb[i][j] = 'L';

                if (val > best) { best = val; bi = i; bj = j; }
            }
        }

        StringBuilder a1 = new StringBuilder();
        StringBuilder a2 = new StringBuilder();

        int i = bi, j = bj;
        while (i > 0 && j > 0 && F[i][j] > 0) {
            char dir = tb[i][j];
            if (dir == 'D') {
                a1.append(s1.charAt(i - 1));
                a2.append(s2.charAt(j - 1));
                i--; j--;
            } else if (dir == 'U') {
                a1.append(s1.charAt(i - 1));
                a2.append('-');
                i--;
            } else if (dir == 'L') {
                a1.append('-');
                a2.append(s2.charAt(j - 1));
                j--;
            } else break;
        }
        int startI = i;
        int startJ = j;

        // Spec: output complete sequences (prefix + local + suffix), not only the local segment
        StringBuilder full1 = new StringBuilder();
        StringBuilder full2 = new StringBuilder();
        for (int k = 0; k < startI; k++) { full1.append(s1.charAt(k)); full2.append('-'); }
        for (int k = 0; k < startJ; k++) { full1.append('-'); full2.append(s2.charAt(k)); }
        full1.append(a1.reverse());
        full2.append(a2.reverse());
        for (int k = bi; k < n; k++) { full1.append(s1.charAt(k)); full2.append('-'); }
        for (int k = bj; k < m; k++) { full1.append('-'); full2.append(s2.charAt(k)); }

        return new String[]{ full1.toString(), full2.toString() };
    }
}