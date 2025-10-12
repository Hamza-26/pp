
import json, random, re, ast
from typing import Any, Dict, List

QUESTION_BANK_PATH = "/mnt/data/QuestionBank.json"

# ----------------------------- Safe expression evaluator -----------------------------
class SafeEvaluator(ast.NodeVisitor):
    ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
    ALLOWED_UNARYOPS = (ast.UAdd, ast.USub)
    ALLOWED_FUNCS = {"abs": abs}
    
    def __init__(self, env: Dict[str, Any]):
        self.env = env
        self.ALLOWED_NAMES = set(env.keys())
    
    def visit_Module(self, node):
        if len(node.body) != 1 or not isinstance(node.body[0], ast.Expr):
            raise ValueError("Only single expressions are allowed")
        return self.visit(node.body[0].value)
    
    def visit_Expr(self, node):
        return self.visit(node.value)
    
    def visit_Name(self, node):
        if node.id in self.ALLOWED_NAMES:
            return self.env[node.id]
        raise ValueError(f"Name '{node.id}' not allowed")
    
    def visit_Constant(self, node):
        return node.value
    
    def visit_Num(self, node):  # for Python <3.8
        return node.n
    
    def visit_BinOp(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, self.ALLOWED_BINOPS):
            return self._apply_binop(node.op, left, right)
        raise ValueError("Operator not allowed")
    
    def visit_UnaryOp(self, node):
        operand = self.visit(node.operand)
        if isinstance(node.op, self.ALLOWED_UNARYOPS):
            if isinstance(node.op, ast.UAdd): return +operand
            if isinstance(node.op, ast.USub): return -operand
        raise ValueError("Unary operator not allowed")
    
    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id in self.ALLOWED_FUNCS:
            func = self.ALLOWED_FUNCS[node.func.id]
            args = [self.visit(a) for a in node.args]
            if node.keywords:
                raise ValueError("Keywords not allowed")
            return func(*args)
        raise ValueError("Function call not allowed")
    
    def visit_Compare(self, node):
        left = self.visit(node.left)
        result = True
        for op, comparator in zip(node.ops, node.comparators):
            right = self.visit(comparator)
            if isinstance(op, ast.Eq):
                ok = (left == right)
            elif isinstance(op, ast.NotEq):
                ok = (left != right)
            elif isinstance(op, ast.Lt):
                ok = (left < right)
            elif isinstance(op, ast.LtE):
                ok = (left <= right)
            elif isinstance(op, ast.Gt):
                ok = (left > right)
            elif isinstance(op, ast.GtE):
                ok = (left >= right)
            else:
                raise ValueError("Comparison operator not allowed")
            if not ok:
                return False
            left = right
        return True

        if isinstance(node.func, ast.Name) and node.func.id in self.ALLOWED_FUNCS:
            func = self.ALLOWED_FUNCS[node.func.id]
            args = [self.visit(a) for a in node.args]
            if node.keywords:
                raise ValueError("Keywords not allowed")
            return func(*args)
        raise ValueError("Function call not allowed")
    
    def generic_visit(self, node):
        raise ValueError(f"Unsupported expression: {type(node).__name__}")
    
    def _apply_binop(self, op, a, b):
        if isinstance(op, ast.Add): return a + b
        if isinstance(op, ast.Sub): return a - b
        if isinstance(op, ast.Mult): return a * b
        if isinstance(op, ast.Div): return a / b
        if isinstance(op, ast.FloorDiv): return a // b
        if isinstance(op, ast.Mod): return a % b
        if isinstance(op, ast.Pow): return a ** b
        raise ValueError("Unknown binary operator")

def eval_expr(expr: str, env: Dict[str, Any]) -> Any:
    tree = ast.parse(str(expr), mode="exec")
    return SafeEvaluator(env).visit(tree)

# ----------------------------- Sampling helpers -----------------------------
def sample_int(lo: int, hi: int, exclude: List[int] = None, sign: str = None, rng: random.Random = None) -> int:
    rng = rng or random
    exclude = set(exclude or [])
    candidates = list(range(lo, hi + 1))
    if sign == "negative":
        candidates = [x for x in candidates if x < 0]
    elif sign == "positive":
        candidates = [x for x in candidates if x > 0]
    candidates = [x for x in candidates if x not in exclude]
    if not candidates:
        raise ValueError("No candidates available for sampling")
    return rng.choice(candidates)

def sample_from_spec(spec: Dict[str, Any], rng: random.Random = None) -> Any:
    rng = rng or random
    if "choices" in spec:
        return rng.choice(spec["choices"])
    if "int" in spec:
        lo, hi = spec["int"]
        exclude = spec.get("exclude", [])
        sign = spec.get("sign", None)
        return sample_int(lo, hi, exclude, sign, rng)
    raise ValueError(f"Unsupported param spec: {spec}")

# ----------------------------- Templating -----------------------------
PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z_]\w*)\s*\}\}")

def render_template(s: str, env: Dict[str, Any]) -> str:
    def repl(m):
        key = m.group(1)
        v = env.get(key, f"<{key}?>")
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        return str(v)
    return PLACEHOLDER_RE.sub(repl, s)

# ----------------------------- Core generator -----------------------------
class QuestionGenerator:
    def __init__(self, bank_path: str = QUESTION_BANK_PATH, seed: int = None):
        self.bank_path = bank_path
        with open(bank_path, "r") as f:
            self.bank = json.load(f)
        self.rng = random.Random(seed)
    
    def _merge_dicts(self, a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(a or {})
        out.update(b or {})
        return out
    
    def _pick_variant(self, family: Dict[str, Any]) -> Dict[str, Any]:
        variants = family.get("variants")
        if not variants:
            return {"id": None, "views": family.get("views", {}), "params": {}, "derive": {}, "constraints": []}
        return self.rng.choice(variants)
    
    def _sample_params(self, param_specs: Dict[str, Any], pick_order: List[str] = None) -> Dict[str, Any]:
        params = {}
        keys = pick_order or list(param_specs.keys())
        for k in param_specs.keys():
            if k not in keys:
                keys.append(k)
        for name in keys:
            spec = param_specs.get(name)
            if spec is None:
                continue
            params[name] = sample_from_spec(spec, self.rng)
        return params
    
    def _compute_derived(self, derive_map: Dict[str, str], env: Dict[str, Any]) -> Dict[str, Any]:
        out = {}
        for k, expr in (derive_map or {}).items():
            out[k] = eval_expr(expr, env)
            env[k] = out[k]
        return out
    
    def _check_constraints(self, constraints: List[str], env: Dict[str, Any]) -> bool:
        for c in constraints or []:
            val = eval_expr(c, env)
            if not bool(val):
                return False
        return True
    
    def _answers_from_view(self, view_ans: Dict[str, Any], env: Dict[str, Any]):
        if not view_ans:
            return None
        ans_type = view_ans.get("type")
        of = view_ans.get("of")
        if ans_type in ("numeric", "numeric_expr"):
            if isinstance(of, str) and ans_type == "numeric":
                return env[of]
            else:
                return eval_expr(of, env)
        if ans_type in ("tuple_int", "tuple_numeric"):
            return [env[name] for name in of]
        if ans_type in ("pair_unordered_int", "set_numeric", "roots_set"):
            return sorted(set(env[name] for name in of))
        if ans_type in ("multiset_numeric", "roots_multiset"):
            return [env[name] for name in of]
        if ans_type in ("factor_triplet",):
            return [env[name] for name in of]
        if ans_type in ("one_of",):
            if isinstance(of, list) and len(of) == 1:
                return of[0]
            return of
        if ans_type in ("ack",):
            return True
        if isinstance(of, list):
            return [env.get(x, x) for x in of]
        if isinstance(of, str):
            return env.get(of, of)
        return None
    
    def _render_views(self, views: Dict[str, Any], env: Dict[str, Any]):
        rendered = {}
        answers = {}
        for key, v in (views or {}).items():
            prompt = v.get("prompt", "")
            rendered[key] = render_template(prompt, env)
            answers[key] = self._answers_from_view(v.get("answer"), env)
        return rendered, answers
    
    def generate(self, family_id: str, max_attempts: int = 50) -> Dict[str, Any]:
        fam = self.bank["families"].get(family_id)
        if fam is None:
            raise KeyError(f"Family '{family_id}' not found")
        variant = self._pick_variant(fam)
        
        fam_params = fam.get("params", {})
        var_params = variant.get("params", {})
        all_param_specs = self._merge_dicts(fam_params, var_params)
        pick_order = variant.get("pick_order")
        
        fam_derive = fam.get("derive", {})
        var_derive = variant.get("derive", {})
        all_derive = self._merge_dicts(fam_derive, var_derive)
        
        fam_constraints = fam.get("constraints", [])
        var_constraints = variant.get("constraints", [])
        all_constraints = list(fam_constraints) + list(var_constraints)
        
        views = variant.get("views", fam.get("views", {}))
        
        for _ in range(max_attempts):
            env = {}
            params = self._sample_params(all_param_specs, pick_order)
            env.update(params)
            derived = self._compute_derived(all_derive, env)
            if self._check_constraints(all_constraints, env):
                rendered_views, answers = self._render_views(views, env)
                return {
                    "family_id": family_id,
                    "variant_id": variant.get("id"),
                    "params": params,
                    "derived": derived,
                    "views": rendered_views,
                    "answers": answers
                }
        raise RuntimeError(f"Failed to satisfy constraints for '{family_id}' after {max_attempts} attempts")

# quick test helper
def _demo():
    gen = QuestionGenerator(QUESTION_BANK_PATH, seed=123)
    samples = {}
    for fid in [
        "LEQ.solve.basic",
        "LEQ.solve.negatives",
        "LEQ.solve.fractions",
        "LEQ.solve.both_sides",
        "LEQ.solve.parentheses.v1",
        "LEQ.solve.special",
        "QF.int_roots.scaled",
        "QF2.formula.two_real",
        "QF2.formula.double_root",
        "QF2.formula.no_real"
    ]:
        inst = gen.generate(fid)
        samples[fid] = {
            "variant": inst["variant_id"],
            "prompt": inst["views"].get("question"),
            "answer": inst["answers"].get("question")
        }
    return samples
