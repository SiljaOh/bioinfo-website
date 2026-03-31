package alignment;

public class Recursion {

    // parameter (gleich wir beim Global Alignment)
    private final int matchScore;
    private final int mismatchScore;
    private final int gapCost;

    public Recursion(int matchScore, int mismatchScore, int gapCost) {
        this.matchScore = matchScore;
        this.mismatchScore = mismatchScore;
        this.gapCost = gapCost;
    }

    private int score(char a, char b) {
        if (a == b) {
            return matchScore;
        }
        else {
            return mismatchScore;
        }
    }

    public int calculateScore(String s1, String s2) {
        return rec(s1, s2, s1.length(), s2.length());
    }

    // Recursion Needleman-Wunsch
    private int rec(String s1, String s2, int i, int j) {

        // base case
        if (i == 0) {
            return -j * gapCost;
        }
        if (j == 0) {
            return -i * gapCost;
        }

        // Fall 1 : diagonal
        int diagonal = rec(s1, s2, i-1, j-1)
                + score(s1.charAt(i -1), s2.charAt(j - 1));

        // Fall 2 : von oben
        int up = rec(s1, s2, i -1, j) - gapCost;

        // Fall 3 : von links
        int left = rec(s1, s2, i, j-1)  - gapCost;

        return Math.max(diagonal, Math.max(up, left));

    }
}
