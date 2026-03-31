package alignment;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;


public class ValidateAli {

    static class AlignmentBlock {
        String header;       // full header line including ">"
        String headerScore;  // score part after ">" (e.g. "some_header 33.9000")
        String line1;        // id: aligned_seq (candidate, seq1)
        String line2;        // id: aligned_seq (candidate, seq2)
        String line3;        // id: aligned_seq (reference, seq1)
        String line4;        // id: aligned_seq (reference, seq2)
    }


    private static String extractSequence(String line) {
        int colon = line.indexOf(':');
        if (colon < 0) return line.trim().replace("\r", "");
        return line.substring(colon + 1).trim().replace("\r", "");
    }

    
    private static Set<Long> alignedPairs(String a1, String a2) {
        if (a1.length() != a2.length())
            throw new IllegalArgumentException("Alignment lines must have same length");
        Set<Long> pairs = new HashSet<>();
        int i1 = 0, i2 = 0;
        for (int c = 0; c < a1.length(); c++) {
            char c1 = a1.charAt(c);
            char c2 = a2.charAt(c);
            if (c1 != '-' && c2 != '-') {
                pairs.add(((long) i1 << 32) | (i2 & 0xFFFFFFFFL));
                i1++;
                i2++;
            } else if (c1 != '-') {
                i1++;
            } else if (c2 != '-') {
                i2++;
            }
        }
        return pairs;
    }

    /**
     * Build list of (seq1_index, seq2_index) in order for mean shift computation.
     */
    private static List<int[]> alignedPairsList(String a1, String a2) {
        if (a1.length() != a2.length())
            throw new IllegalArgumentException("Alignment lines must have same length");
        List<int[]> list = new ArrayList<>();
        int i1 = 0, i2 = 0;
        for (int c = 0; c < a1.length(); c++) {
            char c1 = a1.charAt(c);
            char c2 = a2.charAt(c);
            if (c1 != '-' && c2 != '-') {
                list.add(new int[]{i1, i2});
                i1++;
                i2++;
            } else if (c1 != '-') {
                i1++;
            } else if (c2 != '-') {
                i2++;
            }
        }
        return list;
    }

    /** Sensitivity = |ref ∩ cand| / |ref| */
    private static double sensitivity(Set<Long> ref, Set<Long> cand) {
        if (ref.isEmpty()) return 0.0;
        int tp = 0;
        for (Long p : ref) if (cand.contains(p)) tp++;
        return (double) tp / ref.size();
    }

    /** Specificity = |ref ∩ cand| / |cand| */
    private static double specificity(Set<Long> ref, Set<Long> cand) {
        if (cand.isEmpty()) return 0.0;
        int tp = 0;
        for (Long p : cand) if (ref.contains(p)) tp++;
        return (double) tp / cand.size();
    }

    /** Coverage (Folie 35f): target residues aligned in BOTH ref and cand / target residues aligned in candidate. */
    private static double coverage(Set<Long> ref, Set<Long> cand) {
        if (cand.isEmpty()) return 1.0;
        Set<Integer> refTarget = new HashSet<>();
        Set<Integer> candTarget = new HashSet<>();
        for (Long p : ref) refTarget.add((int) (p & 0xFFFFFFFFL));
        for (Long p : cand) candTarget.add((int) (p & 0xFFFFFFFFL));
        int inBoth = 0;
        for (Integer j : candTarget) if (refTarget.contains(j)) inBoth++;
        return (double) inBoth / candTarget.size();
    }

    /**
     * Mean shift error (template = seq1, target = seq2).
     * For each (i,j) in reference, find (i,j') in candidate; shift = |j - j'|. Return mean.
     */
    private static double meanShiftError(List<int[]> refList, List<int[]> candList) {
        if (refList.isEmpty()) return 0.0;
        // Build map: seq1_index -> seq2_index for candidate
        int maxI = 0;
        for (int[] p : refList) if (p[0] > maxI) maxI = p[0];
        for (int[] p : candList) if (p[0] > maxI) maxI = p[0];
        int[] candJ = new int[maxI + 1];
        for (int i = 0; i <= maxI; i++) candJ[i] = -1;
        for (int[] p : candList) {
            if (p[0] <= maxI) candJ[p[0]] = p[1];
        }
        long sum = 0;
        int count = 0;
        for (int[] p : refList) {
            int i = p[0], jRef = p[1];
            if (i <= maxI && candJ[i] >= 0) {
                sum += Math.abs(jRef - candJ[i]);
                count++;
            }
        }
        return count == 0 ? 0.0 : (double) sum / count;
    }

    /**
     * Inverse mean shift error (template = seq2, target = seq1).
     * For each (i,j) in reference, find (i',j) in candidate; shift = |i - i'|. Return mean.
     */
    private static double inverseMeanShiftError(List<int[]> refList, List<int[]> candList) {
        if (refList.isEmpty()) return 0.0;
        int maxJ = 0;
        for (int[] p : refList) if (p[1] > maxJ) maxJ = p[1];
        for (int[] p : candList) if (p[1] > maxJ) maxJ = p[1];
        int[] candI = new int[maxJ + 1];
        for (int j = 0; j <= maxJ; j++) candI[j] = -1;
        for (int[] p : candList) {
            if (p[1] <= maxJ) candI[p[1]] = p[0];
        }
        long sum = 0;
        int count = 0;
        for (int[] p : refList) {
            int iRef = p[0], j = p[1];
            if (j <= maxJ && candI[j] >= 0) {
                sum += Math.abs(iRef - candI[j]);
                count++;
            }
        }
        return count == 0 ? 0.0 : (double) sum / count;
    }

    public static void main(String[] args) throws IOException {
        String inputFile = null;
        for (int i = 0; i < args.length; i++) {
            if (args[i].equals("-f") && i + 1 < args.length) {
                inputFile = args[++i];
                break;
            }
        }
        if (inputFile == null) {
            System.out.println("Usage: java -jar validateAli.jar -f <alignment-pairs>");
            return;
        }

        List<AlignmentBlock> blocks = new ArrayList<>();
        try (BufferedReader br = new BufferedReader(new FileReader(inputFile))) {
            String header = null;
            String line1 = null, line2 = null;
            String line;
            while ((line = br.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty()) continue;
                if (line.startsWith(">")) {
                    if (header != null && line1 != null && line2 != null) {
                        // previous block missing line3, line4 - skip or incomplete; we need 5 lines
                    }
                    header = line;
                    line1 = null;
                    line2 = null;
                    continue;
                }
                if (line1 == null) {
                    line1 = line;
                    continue;
                }
                if (line2 == null) {
                    line2 = line;
                    continue;
                }
                String line3 = line;
                String line4 = br.readLine();
                if (line4 != null) line4 = line4.trim();
                if (line4 == null || line4.isEmpty()) {
                    // incomplete block, skip
                    header = null;
                    line1 = null;
                    line2 = null;
                    continue;
                }
                AlignmentBlock b = new AlignmentBlock();
                b.header = header;
                b.headerScore = header.substring(1).trim(); // without ">"
                b.line1 = line1;
                b.line2 = line2;
                b.line3 = line3;
                b.line4 = line4;
                blocks.add(b);
                header = null;
                line1 = null;
                line2 = null;
            }
        }

        for (AlignmentBlock b : blocks) {
            String s1Cand = extractSequence(b.line1);
            String s2Cand = extractSequence(b.line2);
            String s1Ref = extractSequence(b.line3);
            String s2Ref = extractSequence(b.line4);

            Set<Long> refPairs = alignedPairs(s1Ref, s2Ref);
            Set<Long> candPairs = alignedPairs(s1Cand, s2Cand);
            List<int[]> refList = alignedPairsList(s1Ref, s2Ref);
            List<int[]> candList = alignedPairsList(s1Cand, s2Cand);

            double sens = sensitivity(refPairs, candPairs);
            double spec = specificity(refPairs, candPairs);
            double cov = coverage(refPairs, candPairs);
            double mse = meanShiftError(refList, candList);           // 4. Mean shift error
            double invMse = inverseMeanShiftError(refList, candList);  // 5. Inverse mean shift error

            // Spec order: sens, spec, cov, then invMSE (4.), MSE (5.) — Server wertet so
            System.out.printf(Locale.US, ">%s %.4f %.4f %.4f %.4f %.4f%n",
                    b.headerScore, sens, spec, cov, invMse, mse);
            System.out.println(b.line1);
            System.out.println(b.line2);
            System.out.println(b.line3);
            System.out.println(b.line4);
        }
    }
}
