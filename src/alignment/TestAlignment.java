package alignment;

public class TestAlignment {

    public static void main(String[] args) {

        // 1) Recursion Test
        Recursion rec = new Recursion(3, -2, 4);

        String r1 = "AC";
        String r2 = "A";

        int recursionScore = rec.calculateScore(r1, r2);
        System.out.println("Recursion score (AC vs A): " + recursionScore);

        // 2) Dynamic Programming Test
        String s1 = "TATAAT";
        String s2 = "TTACGTAAGG";

        GlobalAlignment aligner = new GlobalAlignment(3, -2, 4);
        double score = aligner.computeScore(s1, s2);

        // 3) Backtracking Test --> Alignment
        Backtracking bt = new Backtracking(3, -2, 4);
        bt.alignment(s1, s2);

        // 4) Local alignment
        LocalAlignment la = new LocalAlignment(3, -2, 4);
        la.alignment("TATAAT", "TTACGTAAGG");

        System.out.println("DP Score: " + score);
    }
}