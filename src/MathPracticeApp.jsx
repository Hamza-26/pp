import React, { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import 'katex/dist/katex.min.css';
import { BlockMath, InlineMath } from 'react-katex';
import { toast } from "sonner";

// =========================
// Inline/Display LaTeX in text
// =========================
function stripDelims(s, left, right) {
  if (s.startsWith(left) && s.endsWith(right)) return s.slice(left.length, -right.length);
  return s;
}
function TextWithInlineMath({ text }) {
  const parts = [];
  const regex = /(\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\))/g;
  let lastIndex = 0; let m;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > lastIndex) parts.push({ type: 'text', content: text.slice(lastIndex, m.index) });
    const token = m[0];
    if (token.startsWith('$$')) parts.push({ type: 'block', content: stripDelims(token, '$$', '$$') });
    else if (token.startsWith('\\[')) parts.push({ type: 'block', content: stripDelims(token, '\\[', '\\]') });
    else parts.push({ type: 'inline', content: stripDelims(token, '\\(', '\\)') });
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < text.length) parts.push({ type: 'text', content: text.slice(lastIndex) });

  return (
    <p className="leading-relaxed break-words whitespace-pre-wrap">
      {parts.map((p, i) => {
        if (p.type === 'text') return <span key={i}>{p.content}</span>;
        if (p.type === 'inline') return <InlineMath key={i} math={p.content} />;
        return <BlockMath key={i} math={p.content} />;
      })}
    </p>
  );
}

// =========================
// MathLive setup
// =========================
let mathliveLoaded = false;
async function ensureMathlive() {
  if (mathliveLoaded) return;
  try { await import('mathlive'); mathliveLoaded = true; }
  catch (e) { console.warn('Mathlive failed to load', e); }
}

function MathField({ value, onChange, placeholder }) {
  const ref = useRef(null);
  // Load MathLive and then set options on the element (avoid JSX JSON escaping issues)
  useEffect(() => {
    let mounted = true;
    (async () => {
      await ensureMathlive();
      if (!mounted) return;
      const el = ref.current;
      if (!el) return;
      // Set options as a real property, not as a string attribute
      el.setOptions?.({ smartFence: true, inlineShortcuts: {} });
    })();
    return () => { mounted = false; };
  }, []);

  // Keep external updates in sync with the math-field value
  useEffect(() => {
    const el = ref.current; if (!el) return;
    if (el.getValue && typeof el.getValue === 'function') {
      const current = el.getValue('latex-unstyled'); if (current !== (value ?? '')) el.setValue?.(value ?? '');
    } else { if (el.value !== (value ?? '')) el.value = value ?? ''; }
  }, [value]);

  return (
    <math-field
      ref={ref}
      style={{ width: '100%', minHeight: 56, padding: 12, borderRadius: 12, border: '1px solid #d1d5db', background: '#fff' }}
      placeholder={placeholder}
      virtual-keyboard-policy="manual"
      onInput={(e) => {
        const el = e.target;
        let raw = '';
        if (el?.getValue) {
          // Prefer ASCIIMath for clean plain-text fractions; then unstyled LaTeX
          try { raw = el.getValue('ASCIIMath'); } catch { raw = ''; }
          if (!raw) raw = el.getValue('latex-unstyled') || el.getValue('latex') || el.getValue();
        } else {
          raw = el?.value ?? '';
        }
        onChange?.(raw);
      }}
    />
  );
}

// =========================
// Algebraic equivalence (rationals) + numeric fallback
// =========================
function normalizeMathInput(raw) {
  let s = String(raw ?? '').trim();
  // Strip invisible / zero-width / NBSP / word-joiner & invisible operators
  s = s.replace(/[\u200B-\u200D\uFEFF\u00A0\u2060\u2061\u2062\u2063\u2064]/g, '');

  // Unicode normalization & punctuation
  s = s.normalize('NFKC')
       .replace(/[\u2212\u2013\u2014]/g, '-')    // minus & dashes → '-'
       .replace(/[∕⁄]/g, '/')                      // fraction slashes → '/'
       .replace(/÷/g, '/')                          // division sign
       .replace(/×|·/g, '*');                       // multiplication signs

  // Normalize common math identifiers
  s = s.replace(/π/g, 'pi').replace(/\\pi/g, 'pi');

  // Decimal comma → dot (only between digits)
  s = s.replace(/(\d),(?=\d)/g, '$1.');

  // Remove LaTeX spacing/size wrappers & \left/\right
  s = s
    .replace(/\\(,|;|:|!|quad|qquad|hspace\{[^}]*\}|vspace\{[^}]*\}|phantom\{[^}]*\}|thinspace|enspace)/g, '')
    .replace(/\\left\s*/g, '')
    .replace(/\\right\s*/g, '')
    .replace(/\\operatorname\s*\{([^}]*)\}/g, '$1');

  // Map vulgar fractions → (a/b)
  const vulgar = { '½':'(1/2)','¼':'(1/4)','¾':'(3/4)','⅓':'(1/3)','⅔':'(2/3)','⅕':'(1/5)','⅖':'(2/5)','⅗':'(3/5)','⅘':'(4/5)','⅙':'(1/6)','⅚':'(5/6)','⅛':'(1/8)','⅜':'(3/8)','⅝':'(5/8)','⅞':'(7/8)' };
  s = s.replace(/[½¼¾⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞]/g, m => vulgar[m]);

  // Strip inline math wrappers
  s = s.replace(/^\$(.*)\$$/, '$1').replace(/^\\\((.*)\\\)$/, '$1');

  // LaTeX → ASCII (support \frac, \dfrac, \tfrac)
  while (/\\(?:d|t)?frac{([^}]+)}{([^}]+)}/.test(s)) {
    s = s.replace(/\\(?:d|t)?frac{([^}]+)}{([^}]+)}/g, '($1)/($2)');
  }
  s = s.replace(/\\sqrt{([^}]+)}/g, 'sqrt($1)');
  s = s.replace(/\^\{([^}]+)}/g, '^($1)');

  // Remove braces around plain integers so ({3})/({8}) parses
  s = s.replace(/\{\s*([+-]?\d+)\s*\}/g, '$1');

  // Collapse spaces
  s = s.replace(/\s+/g, ' ').trim();
  return s;
}

// Fraction (BigInt) utilities
const BI = (x) => BigInt(x);
function gcd(a,b){ a = a<0n?-a:a; b=b<0n?-b:b; while(b){ const t=a%b; a=b; b=t;} return a; }
function norm(n,d){ if(d<0n){ n=-n; d=-d;} const g=gcd(n,d)||1n; return {n:n/g, d:d/g}; }
function addF(a,b){ return norm(a.n*b.d + b.n*a.d, a.d*b.d); }
function subF(a,b){ return norm(a.n*b.d - b.n*a.d, a.d*b.d); }
function mulF(a,b){ return norm(a.n*b.n, a.d*b.d); }
function divF(a,b){ if(b.n===0n) throw new Error('div0'); return norm(a.n*b.d, a.d*b.n); }
function powF(a,k){ k=Number(k); if(!Number.isInteger(k)) throw new Error('non-int exp'); if(k===0) return {n:1n,d:1n}; if(k<0){ const p=powF(a,-k); return {n:p.d,d:p.n}; } let base={...a}; let res={n:1n,d:1n}; while(k>0){ if(k&1) res=mulF(res,base); base=mulF(base,base); k>>=1; } return res; }
function eqF(a,b){ return a.n===b.n && a.d===b.d; }
function toNumberF(a){ return Number(a.n)/Number(a.d); }
function fromInt(i){ return {n:BI(i), d:1n}; }
function fromDecimalString(str){ if(!str.includes('.')) return fromInt(str); const [i,dec]=str.split('.'); const scale = 10n ** BI(dec.length); const n = BI(i||'0')*scale + BI(dec); return norm(n, scale); }

// Lexer
function tokenize(s){
  const tokens=[]; let i=0;
  const isdigit=c=>/\d/.test(c);
  while(i<s.length){
    const c=s[i];
    if(c===' '){ i++; continue; }
    if("+-*/^()".includes(c)){ tokens.push({t:c}); i++; continue; }
    if(isdigit(c) || c==='.'){
      let j=i; while(j<s.length && /[0-9.]/.test(s[j])) j++;
      tokens.push({t:'num', v:s.slice(i,j)}); i=j; continue;
    }
    if(/[a-zA-Z]/.test(c)){
      let j=i; while(j<s.length && /[a-zA-Z]/.test(s[j])) j++;
      tokens.push({t:'id', v:s.slice(i,j)}); i=j; continue;
    }
    if(c==='/' ){ tokens.push({t:'/'}); i++; continue; }
    if(c==='['||c===']'||c==='{'||c==='}'){ i++; continue; } // ignore stray
    throw new Error('bad char '+c);
  }
  tokens.push({t:'eof'}); return tokens;
}

// Pratt parser for + - * / ^
function parseExpr(tokens){ let i=0; const peek=()=>tokens[i]; const next=()=>tokens[i++];
  function parsePrimary(){ const tok=next();
    if(tok.t==='num') return {k:'num', v:tok.v};
    if(tok.t==='id') return {k:'id', v:tok.v};
    if(tok.t==='-'){ return {k:'neg', x:parsePrimary()}; }
    if(tok.t==='('){ const e=parseAddSub(); if(next().t!==')') throw new Error(')'); return e; }
    throw new Error('primary');
  }
  function parsePow(){ let left=parsePrimary(); while(peek().t==='^'){ next(); const right=parsePrimary(); left={k:'pow', a:left, b:right}; } return left; }
  function parseMulDiv(){ let left=parsePow(); while(peek().t==='*' || peek().t==='/' ){ const op=next().t; const r=parsePow(); left={k:op, a:left, b:r}; } return left; }
  function parseAddSub(){ let left=parseMulDiv(); while(peek().t==='+' || peek().t==='-'){ const op=next().t; const r=parseMulDiv(); left={k:op, a:left, b:r}; } return left; }
  const ast=parseAddSub(); if(peek().t!=='eof') throw new Error('trailing'); return ast;
}

function evalRational(ast){
  function evalNode(n){
    switch(n.k){
      case 'num': return n.v.includes('.') ? fromDecimalString(n.v) : fromInt(n.v);
      case 'id': throw new Error('symbol'); // pi, sqrt → numeric path
      case 'neg': { const t = evalNode(n.x); return {n:-t.n, d:t.d}; }
      case '+': return addF(evalNode(n.a), evalNode(n.b));
      case '-': return subF(evalNode(n.a), evalNode(n.b));
      case '*': return mulF(evalNode(n.a), evalNode(n.b));
      case '/': return divF(evalNode(n.a), evalNode(n.b));
      case 'pow': {
        const a = evalNode(n.a); if(n.b.k!=='num') throw new Error('exp');
        const expStr = n.b.v; if(expStr.includes('.')) throw new Error('exp');
        return powF(a, Number(expStr));
      }
      default: throw new Error('node');
    }
  }
  return evalNode(ast);
}

function tryEvalAlgebraic(expr){
  try {
    const s = normalizeMathInput(expr);
    // 1) Very tolerant simple fraction: optional parens around integers
    const simple = s.match(/^\(?\s*([+-]?\d+)\s*\)?\s*\/\s*\(?\s*([+-]?\d+)\s*\)?$/);
    if(simple){ return { ok:true, frac: norm(BI(simple[1]), BI(simple[2])) }; }
    // 2) Parse full expression as rational
    const tokens = tokenize(s); const ast = parseExpr(tokens); const frac = evalRational(ast); return { ok:true, frac };
  } catch { return { ok:false }; }
}

function tryEvalNumeric(expr){
  try{
    const s0 = normalizeMathInput(expr)
      .replace(/\bpi\b/g, 'Math.PI')
      .replace(/sqrt\(/g, 'Math.sqrt(')
      .replace(/\s+/g, '');
    if(/[^0-9+\-*/().,A-Za-z]/.test(s0)) return NaN;
    // eslint-disable-next-line no-new-func
    const val = Function('Math', '"use strict"; return (' + s0 + ')')(Math);
    const num = Number(val); return Number.isFinite(num) ? num : NaN;
  } catch { return NaN; }
}

const nearlyEqual = (a,b,tol=1e-6)=> Math.abs(a-b) <= tol*Math.max(1,Math.abs(a),Math.abs(b));

// ---- sample questions ----
const SAMPLE_QUESTIONS = [
  {
    id: 'q1', type: 'mcq', question: 'What is the derivative of \\(x^2\\)?',
    choices: [ { id: 'a', content: '1' }, { id: 'b', content: '2x', correct: true }, { id: 'c', content: 'x' }, { id: 'd', content: '\\ln x' } ],
    explanation: 'Using d/dx x^n = n x^{n-1} with n=2 gives 2x.'
  },
  {
    id: 'q2', type: 'free', question: 'Compute:  \\[ \\left( \\frac{1}{2} \\right)^3 + \\frac{1}{4} \\]',
    answer: { value: 0.375, tol: 1e-9 }, explanation: '((1/2)^3) + 1/4 = 1/8 + 1/4 = 3/8 = 0.375.'
  },
  {
    id: 'q3', type: 'free', question: 'Solve for x: \\(2x + 3 = 11\\)',
    answer: { value: 4, tol: 1e-9 }, explanation: '2x = 8 so x = 4.'
  },
];

export default function MathPracticeApp() {
  const [currentIdx, setCurrentIdx] = useState(0);
  const [answers, setAnswers] = useState({});
  const [showSolution, setShowSolution] = useState({});
  const [useMathField, setUseMathField] = useState(true);
  const [loadingMathfield, setLoadingMathfield] = useState(false);
  const [debug, setDebug] = useState(true); // DEBUG ON by default so you can see the panel

  useEffect(() => { if (useMathField) { setLoadingMathfield(true); ensureMathlive().finally(() => setLoadingMathfield(false)); } }, [useMathField]);

  // Keyboard toggle for debug (F2)
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'F2') setDebug(d => !d); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const q = SAMPLE_QUESTIONS[currentIdx];
  const currentAnswer = answers[q?.id] ?? '';
  const updateAnswer = (v)=> setAnswers(prev=>({...prev,[q.id]:v}));

  function checkAnswer() {
    if (!q) return false;
    let correct = false;
    if (q.type === 'mcq') {
      const chosen = currentAnswer; const found = q.choices?.find(c => c.id === chosen); correct = !!found?.correct;
    } else {
      const expected = q.answer;
      if (expected && typeof expected.value === 'number') {
        // Prefer algebraic rational comparison first
        const a = tryEvalAlgebraic(currentAnswer);
        if (a.ok) {
          const b = fromDecimalString(String(expected.value));
          correct = eqF(a.frac, b) || nearlyEqual(toNumberF(a.frac), expected.value, expected.tol ?? 1e-6);
        }
        // Numeric fallback (sqrt, pi, etc.)
        if (!correct) {
          const val = tryEvalNumeric(currentAnswer);
          correct = nearlyEqual(val, expected.value, expected.tol ?? 1e-6);
        }
      } else if (typeof expected === 'string') {
        const norm = (s) => String(s ?? '').replace(/\s+/g, ' ').trim();
        correct = norm(currentAnswer) === norm(expected);
      }
    }
    if (correct) toast.success("Correct! Nice work");
    else toast("Not quite", { description: "Click ‘Show solution’ for a hint." });
    return correct;
  }

  return (
    <div className="min-h-screen bg-neutral-100 text-neutral-900 grid place-items-center p-4">
      <div className="w-full max-w-3xl">
        <header className="flex items-center justify-between gap-3 mb-4">
          <h1 className="text-2xl">Math Practice</h1>
          <div className="flex items-center gap-4">
            <label className="text-sm flex items-center gap-2">
              <input type="checkbox" checked={useMathField} onChange={(e)=>setUseMathField(e.target.checked)} />
              Math input
            </label>
            <label className="text-xs flex items-center gap-2 opacity-80">
              <input type="checkbox" checked={debug} onChange={(e)=>setDebug(e.target.checked)} />
              Debug (F2)
            </label>
          </div>
        </header>

        <div className="rounded-2xl border border-neutral-300 bg-white p-5 shadow-sm">
          <div className="text-sm text-neutral-600 mb-2">Question {currentIdx + 1} of {SAMPLE_QUESTIONS.length}</div>

          <motion.div initial={{opacity:0,y:6}} animate={{opacity:1,y:0}} key={q.id}>
            <TextWithInlineMath text={q.question} />
          </motion.div>

          {q.type === 'mcq' ? (
            <div className="grid sm:grid-cols-2 gap-3 my-3">
              {q.choices?.map(c => {
                const selected = answers[q.id]===c.id;
                return (
                  <button
                    key={c.id}
                    onClick={()=>updateAnswer(c.id)}
                    className={`p-3 text-left w-full border rounded-xl transition ${selected ? 'bg-blue-600 text-white border-blue-600' : 'bg-white border-neutral-300 hover:bg-neutral-50'}`}
                  >
                    <InlineMath math={c.content} />
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="my-3">
              {useMathField && !loadingMathfield ? (
                <MathField value={currentAnswer} onChange={updateAnswer} placeholder="Type your answer (LaTeX or numeric)" />
              ) : useMathField && loadingMathfield ? (
                <div className="text-sm text-neutral-500">Loading math input…</div>
              ) : (
                <textarea
                  className="w-full min-h-20 rounded-xl border border-neutral-300 p-3 bg-transparent"
                  value={currentAnswer}
                  onChange={(e)=>updateAnswer(e.target.value)}
                  placeholder="Enter LaTeX or numeric expression"
                />
              )}

              {debug && (
                <div className="mt-2 text-xs p-2 border rounded bg-neutral-50 text-neutral-700 space-y-1">
                  <div><strong>Raw:</strong> <code>{String(currentAnswer)}</code></div>
                  <div><strong>Normalized:</strong> <code>{normalizeMathInput(currentAnswer)}</code></div>
                  <div><strong>Algebraic:</strong> <code>{(() => { const a=tryEvalAlgebraic(currentAnswer); return a.ok ? `${a.frac.n.toString()}/${a.frac.d.toString()}` : '—'; })()}</code></div>
                  <div><strong>Numeric:</strong> <code>{(() => { const n=tryEvalNumeric(currentAnswer); return Number.isFinite(n) ? n : 'NaN'; })()}</code></div>
                </div>
              )}

              <div className="text-xs text-neutral-600 mt-1">
                Tip: Enter <code>\\frac{3}{8}</code> or <code>3/8</code>, <code>sqrt(2)</code>, <code>pi/6</code>.
              </div>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2 mt-3">
            <button className="px-3 py-2 rounded-lg border border-neutral-300 bg-transparent" onClick={checkAnswer}>Check</button>
            <button className="px-3 py-2 rounded-lg border border-neutral-300 bg-transparent" onClick={()=> setShowSolution(prev=>({...prev,[q.id]: !prev[q.id]}))}>
              {showSolution[q.id] ? 'Hide solution' : 'Show solution'}
            </button>
            <div className="ml-auto flex items-center gap-2">
              <button className="px-3 py-2 rounded-lg border border-neutral-300 bg-transparent" onClick={()=> setCurrentIdx(i=> (i-1+SAMPLE_QUESTIONS.length)%SAMPLE_QUESTIONS.length)}>Prev</button>
              <button className="px-3 py-2 rounded-lg border border-neutral-300 bg-transparent" onClick={()=> setCurrentIdx(i=> (i+1)%SAMPLE_QUESTIONS.length)}>Next</button>
            </div>
          </div>

          {showSolution[q.id] && (
            <div className="mt-3 rounded-xl border border-neutral-300 p-3 bg-neutral-50">
              <p className="text-sm">
                {q.explanation ?? (q.type === 'mcq'
                  ? `Correct choice: ${(q.choices?.find(c=>c.correct)?.id || '').toUpperCase()}`
                  : (typeof q.answer === 'string'
                      ? <BlockMath math={q.answer} />
                      : <>Expected value ≈ <code>{q.answer?.value}</code></>))}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
