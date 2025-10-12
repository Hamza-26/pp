
import json, pprint, sys, importlib.util, runpy

QB_PATH = "./data/QuestionBank.json"
QG_PATH = "./pythons/QuestionGenerator.py"

def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

def run_once(gen, family_id):
    inst = gen.generate(family_id)
    row = {
        "family": family_id,
        "variant": inst.get("variant_id"),
        "question_prompt": inst["views"].get("question"),
        "question_answer": inst["answers"].get("question"),
        "derived": inst.get("derived", {}),
        "all_views": inst["views"],
        "all_answers": inst["answers"]
    }
    return row

def main():
    QG = load_module(QG_PATH, "QuestionGenerator")
    gen = QG.QuestionGenerator(QB_PATH, seed=2025)

    families = ['LEQ.solve.special.linear', 'QF.int_roots.scaled', 'QF2.formula.two_real', 'QF2.formula.double_root', 'QF2.formula.no_real', 'QF.sqrt.ax2_minus_B']

    results = []
    for fid in families:
        for _ in range(2):
            results.append(run_once(gen, fid))

    # Light sanity checks
    for r in results:
        fam = r["family"]
        d = r["derived"]
        if fam == "LEQ.solve.special.linear":
            assert d.get("coeff_x") == 0, "special.linear must have 0x on one side"

    print("\n=== SAMPLE PROMPTS & ANSWERS (updated) ===")
    for r in results:
        print(f"[{r['family']}] variant={r['variant']}")
        print("  prompt:", r["question_prompt"])
        print("  answer:", r["question_answer"])
        print()

    with open("./data/test_output.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()
