# -*- coding: utf-8 -*-
"""
Validierungsmetriken wie in ValidateAli.java:
Sensitivity, Specificity, Mean Shift Error, Inverse Mean Shift Error.
"""

from typing import Set, List, Tuple


def aligned_pairs_set(a1: str, a2: str) -> Set[Tuple[int, int]]:
    """Menge der (seq1_index, seq2_index) für alle aligneden Positionen (kein Gap)."""
    if len(a1) != len(a2):
        raise ValueError("Alignment lines must have same length")
    pairs: Set[Tuple[int, int]] = set()
    i1, i2 = 0, 0
    for c in range(len(a1)):
        c1, c2 = a1[c], a2[c]
        if c1 != "-" and c2 != "-":
            pairs.add((i1, i2))
            i1 += 1
            i2 += 1
        elif c1 != "-":
            i1 += 1
        elif c2 != "-":
            i2 += 1
    return pairs


def aligned_pairs_list(a1: str, a2: str) -> List[Tuple[int, int]]:
    """Liste der (seq1_index, seq2_index) in Reihenfolge für Mean-Shift-Berechnung."""
    if len(a1) != len(a2):
        raise ValueError("Alignment lines must have same length")
    pairs: List[Tuple[int, int]] = []
    i1, i2 = 0, 0
    for c in range(len(a1)):
        c1, c2 = a1[c], a2[c]
        if c1 != "-" and c2 != "-":
            pairs.append((i1, i2))
            i1 += 1
            i2 += 1
        elif c1 != "-":
            i1 += 1
        elif c2 != "-":
            i2 += 1
    return pairs


def sensitivity(ref: Set[Tuple[int, int]], cand: Set[Tuple[int, int]]) -> float:
    """|ref ∩ cand| / |ref|"""
    if not ref:
        return 0.0
    return sum(1 for p in ref if p in cand) / len(ref)


def specificity(ref: Set[Tuple[int, int]], cand: Set[Tuple[int, int]]) -> float:
    """|ref ∩ cand| / |cand|"""
    if not cand:
        return 0.0
    return sum(1 for p in cand if p in ref) / len(cand)


def mean_shift_error(ref_list: List[Tuple[int, int]], cand_list: List[Tuple[int, int]]) -> float:
    """Template = seq1, target = seq2. Für jedes (i,j) in ref: finde j' in cand für i; shift = |j - j'|."""
    if not ref_list:
        return 0.0
    cand_j_by_i: dict = {}
    for i, j in cand_list:
        cand_j_by_i[i] = j
    total = 0
    count = 0
    for i, j_ref in ref_list:
        if i in cand_j_by_i:
            total += abs(j_ref - cand_j_by_i[i])
            count += 1
    return total / count if count else 0.0


def inverse_mean_shift_error(ref_list: List[Tuple[int, int]], cand_list: List[Tuple[int, int]]) -> float:
    """Template = seq2, target = seq1. Für jedes (i,j) in ref: finde i' in cand für j; shift = |i - i'|."""
    if not ref_list:
        return 0.0
    cand_i_by_j: dict = {}
    for i, j in cand_list:
        cand_i_by_j[j] = i
    total = 0
    count = 0
    for i_ref, j in ref_list:
        if j in cand_i_by_j:
            total += abs(i_ref - cand_i_by_j[j])
            count += 1
    return total / count if count else 0.0


def compute_all_metrics(ref_ali1: str, ref_ali2: str, cand_ali1: str, cand_ali2: str) -> dict:
    """Berechnet Sensitivity, Specificity, MSE, invMSE für Kandidat vs Referenz."""
    ref_set = aligned_pairs_set(ref_ali1, ref_ali2)
    cand_set = aligned_pairs_set(cand_ali1, cand_ali2)
    ref_list = aligned_pairs_list(ref_ali1, ref_ali2)
    cand_list = aligned_pairs_list(cand_ali1, cand_ali2)
    return {
        "sensitivity": sensitivity(ref_set, cand_set),
        "specificity": specificity(ref_set, cand_set),
        "mean_shift_error": mean_shift_error(ref_list, cand_list),
        "inverse_mean_shift_error": inverse_mean_shift_error(ref_list, cand_list),
    }
