package alignment;

import java.nio.file.Path;

public class Benchmark {

    public static void main(String[] args) throws Exception {

        // Matrix-Datei: optional als args[0], sonst ein Default
        String matrixFile = (args.length > 0) ? args[0] : "matrices/BLOSUM62.quasar";

        SubstMatrix mat = SubstMatrix.load(Path.of(matrixFile));

        // DP Aligner im Matrix-Modus
        GlobalAlignment dp = new GlobalAlignment(mat, -12, -1);

        // Rekursions-Referenz (nur zum Vergleich, nicht für große Sequenzen!)
        Recursion rec = new Recursion(3, -2, 4);

        String s1 = "ACGTACGT";
        String s2 = "ACGTCGTA";

        int N = 10000;

        long start = System.currentTimeMillis();
        for (int i = 0; i < N; i++) {
            rec.calculateScore(s1, s2);
        }
        long end = System.currentTimeMillis();
        System.out.println("Recursion time ms: " + (end - start));

        start = System.currentTimeMillis();
        for (int i = 0; i < N; i++) {
            dp.computeScore(s1, s2);
        }
        end = System.currentTimeMillis();
        System.out.println("DP time ms: " + (end - start));
    }
}