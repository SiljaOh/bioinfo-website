package alignment;

public class CheckScore {

    static long checkscore(String alignedA, String alignedB,
                           int match, int mismatch, int gap) {

        if (alignedA.length() != alignedB.length()) {
            throw new IllegalArgumentException(
                    "Alignment strings must have equal length."
            );
        }

        long score = 0;

        for (int i = 0; i < alignedA.length(); i++) {

            char a = alignedA.charAt(i);
            char b = alignedB.charAt(i);

            // zwei Lücken gleichzeitig sind nicht erlaubt
            if (a == '-' && b == '-') {
                throw new IllegalArgumentException(
                        "Invalid alignment: two gaps at position " + i
                );
            }

            // Gap
            if (a == '-' || b == '-') {
                score -= gap;
            }

            // Match / Mismatch
            else if (a == b) {
                score += match;
            }
            else {
                score += mismatch;
            }
        }

        return score;
    }
}