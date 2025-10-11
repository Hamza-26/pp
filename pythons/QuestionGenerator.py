
import json, random, uuid, re, math
from typing import Any, Dict, List, Optional, Tuple

class QuestionGenerator:
    def __init__(self, bank_path: str, rng_seed: Optional[int] = None):
        with open(bank_path, "r") as f:
            self.bank = json.load(f)
        self.instances: Dict[str, Dict[str, Any]] = {}
        self.rng = random.Random(rng_seed)

    # --------- Instance lifecycle ---------
    def create_instance(self, family_id: str, forced: Dict[str, Any] = None, preset_id: str = None) -> Dict[str, Any]:
        fam = self.bank["families"][family_id]
        params_spec = fam.get("params", {})
        params = {}

        # Choose preset if requested
        if preset_id:
            preset = next((p for p in fam.get("presets", []) if p.get("id") == preset_id), None)
            if not preset:
                raise ValueError(f"Preset {preset_id} not found for {family_id}")
            params = dict(preset["params"])
        else:
            # Sample params from ranges
            for name, spec in params_spec.items():
                if "int" in spec:
                    lo, hi = spec["int"]
                    params[name] = self.rng.randint(lo, hi)
                else:
                    raise ValueError(f"Unsupported param spec for {name}: {spec}")

        # Apply forced overrides
        if forced:
            params.update(forced)

        # SPECIAL CASE HANDLING by family naming (optional, keeps JSON simple)
        # Ensure the discriminant condition if applicable by resampling a few times.
        def ensure_disc_condition_ok(params) -> bool:
            # compute derived to check
            derived = self._compute_derive(fam, params)
            # Detect expected sign from family_id
            fid = family_id.lower()
            if ".no_real" in fid:
                return (derived.get("disc") is not None) and (derived["disc"] < 0)
            if ".double_root" in fid:
                # For double_root family we actually derive disc = 0 from a,r
                return (abs(derived.get("disc", 0)) == 0)
            if ".two_real" in fid:
                # For rational roots parametrization, disc > 0 always if r1 != r2
                # But ensure not equal roots
                if "r1" in params and "r2" in params:
                    return params["r1"] != params["r2"]
                return (derived.get("disc") is None) or (derived["disc"] > 0)
            return True

        attempts = 0
        while attempts < 100 and not ensure_disc_condition_ok(params):
            # re-sample
            for name, spec in params_spec.items():
                if "int" in spec and (forced is None or name not in forced):
                    lo, hi = spec["int"]
                    params[name] = self.rng.randint(lo, hi)
            attempts += 1

        derived = self._compute_derive(fam, params)

        instance_id = str(uuid.uuid4())
        self.instances[instance_id] = {
            "family": family_id,
            "params": params,
            "derived": derived
        }
        return {"instance_id": instance_id, "family": family_id, "params": params, "derived": derived}

    def _compute_derive(self, fam: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        derive = fam.get("derive", {})
        values = dict(params)  # start with params in scope
        out = {}
        unresolved = dict(derive)
        guard = 0
        while unresolved and guard < 100:
            to_delete = []
            for k, expr in unresolved.items():
                try:
                    val = self._safe_eval(expr, {**values, **out})
                    out[k] = val
                    to_delete.append(k)
                except Exception:
                    pass
            for k in to_delete:
                unresolved.pop(k, None)
            guard += 1
        return out

    # very small safe evaluator for arithmetic expressions over provided names
    def _safe_eval(self, expr: Any, scope: Dict[str, Any]) -> Any:
        if isinstance(expr, (int, float)):
            return expr
        if isinstance(expr, str):
            allowed_names = {k: v for k, v in scope.items()}
            allowed_names.update({"abs": abs, "math": math})
            code = compile(expr, "<expr>", "eval")
            for name in code.co_names:
                if name not in allowed_names:
                    raise ValueError(f"Unsafe name in expression: {name}")
            return eval(code, {"__builtins__": {}}, allowed_names)
        raise ValueError("Unsupported derive expression type")

    # --------- Rendering ---------
    def render(self, instance_id: str, view: str = "question") -> Dict[str, Any]:
        inst = self.instances[instance_id]
        fam = self.bank["families"][inst["family"]]
        views = fam.get("views", {})
        if view not in views:
            raise KeyError(f"View '{view}' not found for family {inst['family']}")
        v = views[view]
        prompt = self._render_template(v.get("prompt",""), inst)
        ui = v.get("ui", {})
        return {"prompt": prompt, "ui": ui}

    def _render_template(self, template: str, inst: Dict[str, Any]) -> str:
        def repl(m):
            key = m.group(1).strip()
            # look in params first then derived
            if key in inst["params"]:
                return str(inst["params"][key])
            if key in inst["derived"]:
                return str(inst["derived"][key])
            return "{{" + key + "}}"
        return re.sub(r"\{\{([^\}]+)\}\}", repl, template)

    # --------- Grading ---------
    def grade(self, instance_id: str, view: str, student_answer: Any, tolerance: float = 1e-9) -> Dict[str, Any]:
        inst = self.instances[instance_id]
        fam = self.bank["families"][inst["family"]]
        answer_spec = fam["views"][view]["answer"]
        ans_type = answer_spec["type"]

        # helper getters
        def get_value(key: str):
            if key in inst["params"]: return inst["params"][key]
            if key in inst["derived"]: return inst["derived"][key]
            # support expressions
            return self._safe_eval(key, {**inst["params"], **inst["derived"]})

        def cmp_num(a, b):
            try:
                return abs(float(a) - float(b)) <= tolerance
            except Exception:
                return False

        # evaluate expected(s)
        if ans_type == "numeric":
            expected = get_value(answer_spec["of"])
            correct = cmp_num(student_answer, expected)
            return {"correct": correct, "expected": expected}

        if ans_type == "numeric_expr":
            expected = self._safe_eval(answer_spec["of"], {**inst["params"], **inst["derived"]})
            correct = cmp_num(student_answer, expected)
            return {"correct": correct, "expected": expected}

        if ans_type == "tuple_int":
            expected = [get_value(k) for k in answer_spec["of"]]
            correct = isinstance(student_answer, (list, tuple)) and all(int(student_answer[i]) == int(expected[i]) for i in range(len(expected)))
            return {"correct": correct, "expected": expected}

        if ans_type in ("tuple_int_expr",):
            expected = [self._safe_eval(k, {**inst["params"], **inst["derived"]}) for k in answer_spec["of"]]
            correct = isinstance(student_answer, (list, tuple)) and all(int(student_answer[i]) == int(expected[i]) for i in range(len(expected)))
            return {"correct": correct, "expected": expected}

        if ans_type in ("pair_unordered_int", "set_numeric", "roots_set"):
            expected = [get_value(k) for k in answer_spec["of"]]
            try:
                exp = sorted([float(x) for x in expected])
                got = sorted([float(x) for x in student_answer])
                correct = len(exp) == len(got) and all(abs(exp[i]-got[i]) <= tolerance for i in range(len(exp)))
            except Exception:
                correct = False
            return {"correct": correct, "expected": expected}

        if ans_type == "multiset_numeric":
            # handle duplicates; compare sorted lists with tolerance
            expected = [get_value(k) for k in answer_spec["of"]]
            try:
                exp = sorted([float(x) for x in expected])
                got = sorted([float(x) for x in student_answer])
                correct = len(exp) == len(got) and all(abs(exp[i]-got[i]) <= tolerance for i in range(len(exp)))
            except Exception:
                correct = False
            return {"correct": correct, "expected": expected}

        if ans_type == "one_of":
            allowed = answer_spec["of"]
            if isinstance(student_answer, str):
                s = student_answer.strip().upper()
                correct = any(s == a.upper() for a in allowed)
            else:
                correct = False
            return {"correct": correct, "expected_any_of": allowed}

        if ans_type == "factor_triplet":
            # student_answer expected as list/tuple [A, r1, r2] or dict with keys
            expected_A = get_value(answer_spec["of"][0])
            expected_r = [get_value(answer_spec["of"][1]), get_value(answer_spec["of"][2])]
            opts = answer_spec.get("options", {})
            allow_swap = bool(opts.get("allow_order_swap", True))
            allow_A_one_blank = bool(opts.get("allow_A_one_equals_blank", True))

            # normalize input
            if isinstance(student_answer, dict):
                sA = student_answer.get("A", student_answer.get("a", None))
                sr1 = student_answer.get("r1", None)
                sr2 = student_answer.get("r2", None)
                student = [sA, sr1, sr2]
            else:
                student = list(student_answer)

            # Treat blank A as 1 if allowed
            sA = student[0]
            if (sA in ("", None)) and allow_A_one_blank:
                sA = 1
            try:
                sA = int(sA)
                sr1 = int(student[1])
                sr2 = int(student[2])
            except Exception:
                return {"correct": False, "expected": {"A": expected_A, "roots": expected_r}}

            roots_exp = sorted([int(expected_r[0]), int(expected_r[1])])
            roots_got = sorted([sr1, sr2]) if allow_swap else [sr1, sr2]

            correct = (int(sA) == int(expected_A)) and (roots_got == (roots_exp if allow_swap else [int(expected_r[0]), int(expected_r[1])]))
            return {"correct": correct, "expected": {"A": expected_A, "roots": expected_r}}

        if ans_type == "ack":
            return {"correct": True}

        raise ValueError(f"Unsupported answer type: {ans_type}")


# Simple manual test if run directly
if __name__ == "__main__":
    qg = QuestionGenerator("../data/QuestionBank.json", rng_seed=42)
    inst = qg.create_instance("QF.int_roots.scaled", preset_id="QF-FAC-1")
    rid = inst["instance_id"]
    print("Instance:", inst)
    print("Render question:", qg.render(rid, "question"))
    print("Grade correct roots:", qg.grade(rid, "question", [2,3]))
    print("Grade wrong roots:", qg.grade(rid, "question", [2,4]))
