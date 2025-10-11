import sys; sys.path.append("/mnt/data")

from QuestionGenerator import QuestionGenerator

def demo_family(qg, family_id, preset_id, views_and_answers):
    inst = qg.create_instance(family_id, preset_id=preset_id)
    rid = inst["instance_id"]
    print(f"\n=== Family: {family_id} | Preset: {preset_id} ===")
    for view, answer in views_and_answers:
        rendered = qg.render(rid, view)
        print(f"\nView: {view}")
        print("Prompt:", rendered["prompt"])
        print("UI:", rendered["ui"])
        result = qg.grade(rid, view, answer)
        print("Answer:", answer, "=>", result)

def main():
    qg = QuestionGenerator("././data/QuestionBank.json", rng_seed=123) #file path might change.... 

    # 1) Factorization track
    demo_family(qg, "QF.int_roots.scaled", "QF-FAC-1", [
        ("standard_form", [1, -5, 6]),
        ("sum_product_or_ac", [2, 3]),
        ("write_factors", [1, 2, 3]),
        ("question", [2, 3])
    ])

    # 2) No real
    demo_family(qg, "QF2.formula.no_real", "QF-NR-1", [
        ("coeffs", [1, 2, 5]),
        ("disc_value", -16),
        ("disc_class", "NEG"),
        ("no_real_conclusion", "NO_REAL_SOLUTIONS")
    ])

    # 3) Double root
    demo_family(qg, "QF2.formula.double_root", "QF-DR-1", [
        ("over_2a", 3),
        ("question", [3, 3])
    ])

    # 4) Two real
    demo_family(qg, "QF2.formula.two_real", "QF-TR-3", [
        ("sqrt_disc_exact", abs(2*( -1 - 5 ))),  # sqrtD = abs(a*(r1-r2)) = abs(2*(-6)) = 12
        ("over_2a", [-1, 5]),
        ("question", [-1, 5])
    ])

if __name__ == "__main__":
    main()
