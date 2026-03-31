package alignment;

public class Backtracking {

    // parameter
    private final int matchScore;
    private final int mismatchScore;
    private final int gapCost;

    public Backtracking (int matchScore, int mismatchScore, int gapCost) {
        this.matchScore = matchScore;
        this.mismatchScore = mismatchScore;
        this.gapCost = gapCost;
    }

    private int score(char a, char b) {
        return (a == b) ? matchScore : mismatchScore;

        // oder:
        // if (a == b) {
        //    return matchScore;
        // } else {
        //    return mismatchScore;
        // }
    }

    public void alignment(String s1, String s2) {
        int n = s1.length();
        int m = s2.length();

        // score matrix
        int[][] F = new int[n + 1][m + 1];

        // traceback matrix: fuer jede Zelle speichert die Richtung
        // char 'd' = diagonal; 'u' = up; 'l' = left
        char[][] traceback = new char[n + 1][m + 1];

        // 1) Initialisieren

        // up (erste Spalte)
        for (int i = 1; i <= n; i++) {
            F[i][0] = F[i - 1][0] - gapCost;
            traceback[i][0] = 'u';
        }

        // left (erste Zeile)
        for (int j = 1; j <= m; j++) {
            F[0][j] = F[0][j - 1] - gapCost;
            traceback[0][j] = 'l';
        }

        // 2) Global Alignment
        for (int i = 1; i <= n; i++) {
            for (int j = 1; j <= m; j++) {

                // diagonal
                int diagonal = F[i - 1][j - 1] + score(s1.charAt(i - 1), s2.charAt(j - 1));

                // up
                int up = F[i - 1][j] - gapCost;

                // left
                int left = F[i][j - 1] - gapCost;

                // Algorithmus
                int bestScore = diagonal;
                char direction = 'd';

                if (up > bestScore) {
                    bestScore = up;
                    direction = 'u';
                }

                if (left > bestScore) {
                    bestScore = left;
                    direction = 'l';
                }

                F[i][j] = bestScore;
                traceback[i][j] = direction;
            }
        }

            // 3) Backtracking von unten rechts nach (0,0)

        StringBuilder alignedSequence1 = new StringBuilder();
        StringBuilder alignedSequence2 = new StringBuilder();
        int i = n;
        int j = m;

        while (i > 0 || j > 0) {

            char dir = traceback[i][j];

            if (dir == 'd') {
                // diagonal
                alignedSequence1.insert(0, s1.charAt(i - 1));
                alignedSequence2.insert(0, s2.charAt(j - 1));
                i--;
                j--;
            }
            else if (dir == 'u') {
                // up
                alignedSequence1.insert(0, s1.charAt(i - 1));
                alignedSequence2.insert(0, '-');
                i --;
            }
            else {
                // left
                alignedSequence1.insert(0, '-');
                alignedSequence2.insert(0, s2.charAt(j - 1));
                j--;
            }
        }

        System.out.println("Alignment sequence:");
        System.out.println(alignedSequence1);
        System.out.println(alignedSequence2);
        System.out.println("Score: " + F[n][m]);
    }
}
