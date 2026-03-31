package alignment;

public class GlobalAlignment {

    private final SubstMatrix mat;      // null => Pen&Paper Modus
    private final long match;
    private final long mismatch;
    private final long gap;             // positive Penalty pro Position

    // Pen&Paper (match/mismatch/gap)
    public GlobalAlignment(int match, int mismatch, int gap) {
        this.mat = null;
        this.match = match;
        this.mismatch = mismatch;
        this.gap = Math.abs((long) gap);
    }

    // Matrix Modus (Server: -m, --go, --ge)
    // Für NW verwenden wir lineare Gapkosten => ge als Penalty pro Position, go wird ignoriert
    public GlobalAlignment(SubstMatrix mat, long go, long ge) {
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

    public long computeScore(String a, String b) {
        int n = a.length();
        int m = b.length();

        long[][] F = new long[n + 1][m + 1];

        for (int i = 1; i <= n; i++) F[i][0] = F[i - 1][0] - gap;
        for (int j = 1; j <= m; j++) F[0][j] = F[0][j - 1] - gap;

        for (int i = 1; i <= n; i++) {
            for (int j = 1; j <= m; j++) {
                long diag = F[i - 1][j - 1] + score(a.charAt(i - 1), b.charAt(j - 1));
                long up   = F[i - 1][j] - gap;
                long left = F[i][j - 1] - gap;
                F[i][j] = Math.max(diag, Math.max(up, left));
            }
        }
        return F[n][m];
    }

    public String[] alignment(String a, String b) {
        int n = a.length();
        int m = b.length();

        long[][] F = new long[n + 1][m + 1];
        char[][] tb = new char[n + 1][m + 1];

        for (int i = 1; i <= n; i++) { F[i][0] = F[i - 1][0] - gap; tb[i][0] = 'U'; }
        for (int j = 1; j <= m; j++) { F[0][j] = F[0][j - 1] - gap; tb[0][j] = 'L'; }

        for (int i = 1; i <= n; i++) {
            for (int j = 1; j <= m; j++) {
                long diag = F[i - 1][j - 1] + score(a.charAt(i - 1), b.charAt(j - 1));
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

        StringBuilder a1 = new StringBuilder();
        StringBuilder a2 = new StringBuilder();
        int i = n, j = m;

        while (i > 0 || j > 0) {
            char dir = tb[i][j];
            if (i > 0 && j > 0 && dir == 'D') {
                a1.append(a.charAt(i - 1));
                a2.append(b.charAt(j - 1));
                i--; j--;
            } else if (i > 0 && (j == 0 || dir == 'U')) {
                a1.append(a.charAt(i - 1));
                a2.append('-');
                i--;
            } else {
                a1.append('-');
                a2.append(b.charAt(j - 1));
                j--;
            }
        }

        return new String[]{ a1.reverse().toString(), a2.reverse().toString() };
    }
}