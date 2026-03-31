package alignment;

public class FreeShiftAlignment {

    private final SubstMatrix mat;   // null => Pen&Paper
    private final long match;
    private final long mismatch;
    private final long gap;

    public FreeShiftAlignment(int matchScore, int mismatchScore, int gapCost) {
        this.mat = null;
        this.match = matchScore;
        this.mismatch = mismatchScore;
        this.gap = Math.abs((long) gapCost);
    }

    public FreeShiftAlignment(SubstMatrix mat, long go, long ge) {
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

        for (int i = 0; i <= n; i++) F[i][0] = 0;
        for (int j = 0; j <= m; j++) F[0][j] = 0;

        for (int i = 1; i <= n; i++) {
            for (int j = 1; j <= m; j++) {
                long diag = F[i - 1][j - 1] + score(s1.charAt(i - 1), s2.charAt(j - 1));
                long up   = F[i - 1][j] - gap;
                long left = F[i][j - 1] - gap;
                F[i][j] = Math.max(diag, Math.max(up, left));
            }
        }

        long best = Long.MIN_VALUE;
        for (int i = 0; i <= n; i++) best = Math.max(best, F[i][m]);
        for (int j = 0; j <= m; j++) best = Math.max(best, F[n][j]);

        return best;
    }

    public String[] alignment(String s1, String s2) {
        int n = s1.length();
        int m = s2.length();

        long[][] F = new long[n + 1][m + 1];
        char[][] tb = new char[n + 1][m + 1];

        for (int i = 0; i <= n; i++) { F[i][0] = 0; tb[i][0] = 'S'; }
        for (int j = 0; j <= m; j++) { F[0][j] = 0; tb[0][j] = 'S'; }

        for (int i = 1; i <= n; i++) {
            for (int j = 1; j <= m; j++) {
                long diag = F[i - 1][j - 1] + score(s1.charAt(i - 1), s2.charAt(j - 1));
                long up   = F[i - 1][j] - gap;
                long left = F[i][j - 1] - gap;

                long best = diag;
                char dir = 'D';
                if (up > best)   { best = up; dir = 'U'; }
                if (left > best) { best = left; dir = 'L'; }

                F[i][j] = best;
                tb[i][j] = dir;
            }
        }

        long best = Long.MIN_VALUE;
        int si = n, sj = m;

        for (int i = 0; i <= n; i++) if (F[i][m] > best) { best = F[i][m]; si = i; sj = m; }
        for (int j = 0; j <= m; j++) if (F[n][j] > best) { best = F[n][j]; si = n; sj = j; }

        StringBuilder a1 = new StringBuilder();
        StringBuilder a2 = new StringBuilder();

        int i = si, j = sj;

        for (int jj = m; jj > sj; jj--) { a1.append('-'); a2.append(s2.charAt(jj - 1)); }
        for (int ii = n; ii > si; ii--) { a1.append(s1.charAt(ii - 1)); a2.append('-'); }

        while (i > 0 && j > 0) {
            char dir = tb[i][j];
            if (dir == 'D') { a1.append(s1.charAt(i - 1)); a2.append(s2.charAt(j - 1)); i--; j--; }
            else if (dir == 'U') { a1.append(s1.charAt(i - 1)); a2.append('-'); i--; }
            else { a1.append('-'); a2.append(s2.charAt(j - 1)); j--; }
        }

        while (i > 0) { a1.append(s1.charAt(i - 1)); a2.append('-'); i--; }
        while (j > 0) { a1.append('-'); a2.append(s2.charAt(j - 1)); j--; }

        return new String[]{ a1.reverse().toString(), a2.reverse().toString() };
    }
}