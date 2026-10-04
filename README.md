"""CG Operation System - number base calculator (Flask)."""
from fractions import Fraction
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
PRECISION = 12  # max fractional digits in results


def check_base(b):
    b = int(b)
    if not 2 <= b <= 36:
        raise ValueError("Base must be between 2 and 36.")
    return b


def parse(text, base):
    """Text in `base` -> Fraction (supports sign and a fractional part)."""
    s = str(text).strip().upper().replace(" ", "")
    neg = s.startswith("-")
    s = s.lstrip("+-")
    if not s or s == ".":
        raise ValueError("Enter a number.")
    ip, _, fp = s.partition(".")
    value = Fraction(0)
    for ch in ip:
        d = DIGITS.find(ch)
        if d < 0 or d >= base:
            raise ValueError(f"'{ch}' is not a valid digit in base {base}.")
        value = value * base + d
    for i, ch in enumerate(fp, 1):
        d = DIGITS.find(ch)
        if d < 0 or d >= base:
            raise ValueError(f"'{ch}' is not a valid digit in base {base}.")
        value += Fraction(d, base ** i)
    return -value if neg else value


def fmt(value, base):
    """Fraction -> string in `base` (truncated to PRECISION fractional digits)."""
    sign = "-" if value < 0 else ""
    value = abs(value)
    whole, frac = divmod(value.numerator, value.denominator)
    out = "" if whole else "0"
    while whole:
        whole, r = divmod(whole, base)
        out = DIGITS[r] + out
    frac = Fraction(frac, value.denominator)
    if frac:
        out += "."
        for _ in range(PRECISION):
            frac *= base
            d = int(frac)
            out += DIGITS[d]
            frac -= d
            if not frac:
                break
    return sign + out


def expand_steps(text, base, label):
    """Step: write a number in `base` as a decimal sum of digit x base^position."""
    s = str(text).strip().upper().replace(" ", "")
    neg = s.startswith("-")
    s = s.lstrip("+-")
    v = parse(text, base)
    if base == 10:
        return {"title": f"{label} is already in decimal", "lines": [f"{label} = {fmt(v, 10)}"]}
    ip, _, fp = s.partition(".")
    terms = [f"{DIGITS.find(c)}×{base}^{len(ip) - 1 - i}" for i, c in enumerate(ip)]
    terms += [f"{DIGITS.find(c)}×{base}^-{i}" for i, c in enumerate(fp, 1)]
    body = " + ".join(terms)
    lines = [f"{label} = {s} (base {base})",
             f"= {'-(' + body + ')' if neg else body}",
             f"= {fmt(v, 10)}"]
    letters = sorted({c for c in s if c.isalpha()})
    if letters:
        lines.append("Letter digits: " + ", ".join(f"{c}={DIGITS.find(c)}" for c in letters))
    return {"title": f"Convert {label} to decimal", "lines": lines}


def to_base_steps(value, base):
    """Steps: turn a decimal Fraction into `base` (repeated division / multiplication)."""
    if base == 10:
        return [{"title": "Result is already decimal", "lines": [f"Answer = {fmt(value, 10)}"]}]
    v = abs(value)
    whole, rem = divmod(v.numerator, v.denominator)
    frac = Fraction(rem, v.denominator)
    lines, n = [], whole
    if n == 0:
        lines.append("Whole part is 0, so it stays 0")
    while n:
        q, r = divmod(n, base)
        lines.append(f"{n} ÷ {base} = {q} remainder {r}" + (f" ({DIGITS[r]})" if r > 9 else ""))
        n = q
    if whole:
        lines.append(f"Read the remainders from bottom to top: {fmt(Fraction(whole), base)}")
    steps = [{"title": f"Convert the whole part {whole} to base {base}", "lines": lines}]
    if frac:
        fl, f = [], frac
        for _ in range(PRECISION):
            p = f * base
            d = int(p)
            fl.append(f"{fmt(f, 10)} × {base} = {fmt(p, 10)} → digit {DIGITS[d]}")
            f = p - d
            if not f:
                break
        fl.append(f"Read the digits from top to bottom: {fmt(frac, base)[1:]}")
        if f:
            fl.append(f"(stopped after {PRECISION} digits)")
        steps.append({"title": f"Convert the fractional part to base {base}", "lines": fl})
    steps.append({"title": "Combine", "lines": [f"Answer = {fmt(value, base)} (base {base})"]})
    return steps


@app.route("/")
def index():
    return render_template("index.html")


@app.post("/api/operate")
def operate():
    try:
        d = request.get_json(force=True)
        base_a, base_b, base_r = check_base(d["base_a"]), check_base(d["base_b"]), check_base(d["base_r"])
        a, b = parse(d["a"], base_a), parse(d["b"], base_b)
        op = d["op"]
        extra = None
        dec_note = None
        sym = {"+": "+", "-": "−", "*": "×", "/": "÷"}.get(op, op)
        if op == "+":
            r = a + b
        elif op == "-":
            r = a - b
        elif op == "*":
            r = a * b
        elif op == "/":
            if b == 0:
                raise ValueError("Cannot divide by zero.")
            r = a / b
            if a.denominator == 1 and b.denominator == 1:
                q, rem = divmod(abs(a.numerator), abs(b.numerator))
                sg = -1 if (a < 0) != (b < 0) else 1
                extra = f"Quotient {fmt(Fraction(sg * q), base_r)}, remainder {fmt(Fraction(rem), base_r)}"
                dec_note = f"Whole-number division: quotient {sg * q}, remainder {rem}"
        else:
            raise ValueError("Unknown operation.")
        calc = [f"{fmt(a, 10)} {sym} {fmt(b, 10)} = {fmt(r, 10)}"]
        if dec_note:
            calc.append(dec_note)
        steps = [expand_steps(d["a"], base_a, "A"), expand_steps(d["b"], base_b, "B"),
                 {"title": "Do the operation in decimal", "lines": calc}]
        steps += to_base_steps(r, base_r)
        if base_r != 10:
            steps[3]["title"] = f"Convert the result to base {base_r}"
        return jsonify(ok=True, result=fmt(r, base_r), decimal=fmt(r, 10), extra=extra, steps=steps)
    except (ValueError, KeyError, TypeError) as e:
        return jsonify(ok=False, error=str(e)), 400


@app.post("/api/convert")
def convert():
    try:
        d = request.get_json(force=True)
        src, dst = check_base(d["from"]), check_base(d["to"])
        v = parse(d["value"], src)
        common = {str(b): fmt(v, b) for b in (2, 8, 10, 16)}
        steps = [expand_steps(d["value"], src, "N")] + to_base_steps(v, dst)
        return jsonify(ok=True, result=fmt(v, dst), common=common, steps=steps)
    except (ValueError, KeyError, TypeError) as e:
        return jsonify(ok=False, error=str(e)), 400


if __name__ == "__main__":
    app.run(debug=True)  

<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CG Operation System</title>
<link rel="icon" href="{{ url_for('static', filename='logo.svg') }}">
<link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;700&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#070402;--panel:#140a03cc;--line:#ff8a1f55;--o:#ff8a1f;--y:#ffd54a;--t:#ffe9cf;--dim:#c08a55;--err:#ff5a4a}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;background:radial-gradient(ellipse at 20% 110%,#ff8a1f55,transparent 55%),var(--bg);color:var(--t);font-family:'Chakra Petch',sans-serif}
#rain{position:fixed;inset:0;z-index:0;opacity:.55}
main{position:relative;z-index:1;max-width:620px;margin:0 auto;padding:28px 18px 60px}
.logo{display:block;width:min(360px,90%);margin:0 auto 10px;filter:drop-shadow(0 0 18px #ff7a0088)}
p.sub{text-align:center;color:var(--dim);margin:0 0 22px}
.tabs{display:flex;gap:8px;margin-bottom:14px}
.tabs button{flex:1;padding:12px;border:1px solid var(--line);background:#00000066;color:var(--dim);font:700 16px 'Chakra Petch';cursor:pointer;border-radius:10px}
.tabs button[aria-selected=true]{color:#1a0c00;background:linear-gradient(135deg,var(--o),var(--y));border-color:transparent;box-shadow:0 0 22px #ff8a1f88}
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:22px;backdrop-filter:blur(8px)}
.card[hidden]{display:none}
label{display:block;margin:0 0 6px;color:var(--dim);font-size:14px}
input,select{width:100%;padding:12px;border-radius:10px;border:1px solid var(--line);background:#0a0502;color:var(--y);font:400 18px 'JetBrains Mono',monospace}
input:focus,select:focus,button:focus-visible{outline:2px solid var(--y);outline-offset:2px}
.row{display:grid;gap:12px;margin-bottom:14px}
.two{grid-template-columns:1fr 1fr}
.ops{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:16px}
.ops button{padding:12px 0;font:700 22px 'JetBrains Mono';background:#0a0502;color:var(--o);border:1px solid var(--line);border-radius:10px;cursor:pointer}
.ops button[aria-pressed=true]{background:var(--o);color:#1a0c00}
.go{width:100%;padding:14px;border:0;border-radius:10px;background:linear-gradient(135deg,var(--o),var(--y));color:#1a0c00;font:700 18px 'Chakra Petch';cursor:pointer}
.out{margin-top:18px;padding:16px;border-radius:10px;background:#00000088;border:1px dashed var(--line);font-family:'JetBrains Mono',monospace;word-break:break-all;min-height:64px}
.out b{display:block;font-size:26px;color:var(--y);text-shadow:0 0 14px #ff8a1f}
.out small{display:block;color:var(--dim);margin-top:6px}
.out.err{color:var(--err)}
.sol{margin-top:16px;padding-top:12px;border-top:1px dashed var(--line);font-size:15px;line-height:1.6}
.sol h3{margin:0 0 8px;color:var(--o);font:700 18px 'Chakra Petch'}
.sol h4{margin:12px 0 4px;color:var(--y);font:700 15px 'Chakra Petch'}
.sol div{color:var(--t)}
@media(max-width:480px){.two{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){ #rain{display:none}}
</style></head><body>
<canvas id="rain" aria-hidden="true"></canvas>
<main>
<img class="logo" src="{{ url_for('static', filename='logo.svg') }}" alt="CG Operation System logo">
<p class="sub">Calculate and convert numbers in any base from 2 to 36.</p>

<div class="tabs" role="tablist">
<button role="tab" id="t1" aria-selected="true">Base operations</button>
<button role="tab" id="t2" aria-selected="false">Base conversion</button>
</div>

<section class="card" id="p1">
<div class="row two">
<div><label for="a">First number</label><input id="a" value="1011" autocomplete="off"></div>
<div><label for="ba">Base of first number</label><input id="ba" type="number" min="2" max="36" value="2"></div></div>
<div class="row two">
<div><label for="b">Second number</label><input id="b" value="1F" autocomplete="off"></div>
<div><label for="bb">Base of second number</label><input id="bb" type="number" min="2" max="36" value="16"></div></div>
<div class="ops" id="ops">
<button data-op="+" aria-pressed="true" title="Add">+</button><button data-op="-" aria-pressed="false" title="Subtract">−</button>
<button data-op="*" aria-pressed="false" title="Multiply">×</button><button data-op="/" aria-pressed="false" title="Divide">÷</button></div>
<div class="row"><div><label for="br">Show the result in base</label><input id="br" type="number" min="2" max="36" value="10"></div></div>
<button class="go" id="calc">Calculate</button>
<div class="out" id="o1" aria-live="polite">Result appears here.</div>
</section>

<section class="card" id="p2" hidden>
<div class="row"><div><label for="v">Number</label><input id="v" value="255" autocomplete="off"></div></div>
<div class="row two">
<div><label for="from">From base</label><input id="from" type="number" min="2" max="36" value="10"></div>
<div><label for="to">To base</label><input id="to" type="number" min="2" max="36" value="2"></div></div>
<button class="go" id="conv">Convert</button>
<div class="out" id="o2" aria-live="polite">Result appears here.</div>
</section>
</main>
<script>
const $=id=>document.getElementById(id);let op='+';
const sol=d=>`<div class="sol"><h3>Solution</h3>${d.steps.map((s,i)=>`<h4>Step ${i+1}: ${s.title}</h4>${s.lines.map(l=>`<div>${l}</div>`).join('')}`).join('')}</div>`;
function tab(n){[1,2].forEach(i=>{$('p'+i).hidden=i!==n;$('t'+i).setAttribute('aria-selected',i===n)})}
$('t1').onclick=()=>tab(1);$('t2').onclick=()=>tab(2);
$('ops').onclick=e=>{const b=e.target.closest('button');if(!b)return;op=b.dataset.op;
 document.querySelectorAll('#ops button').forEach(x=>x.setAttribute('aria-pressed',x===b))};
async function post(url,body,out,render){
 try{const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d=await r.json();out.className='out'+(d.ok?'':' err');out.innerHTML=d.ok?render(d):d.error}
 catch{out.className='out err';out.textContent='Could not reach the server.'}}
$('calc').onclick=()=>post('/api/operate',{base_a:$('ba').value,base_b:$('bb').value,base_r:$('br').value,a:$('a').value,b:$('b').value,op},$('o1'),
 d=>`<b>${d.result}</b><small>Base ${$('br').value} result</small><small>Decimal: ${d.decimal}</small>${d.extra?`<small>${d.extra}</small>`:''}${sol(d)}`);
$('conv').onclick=()=>post('/api/convert',{value:$('v').value,from:$('from').value,to:$('to').value},$('o2'),
 d=>`<b>${d.result}</b><small>Base ${$('to').value} result</small><small>BIN ${d.common[2]} · OCT ${d.common[8]} · DEC ${d.common[10]} · HEX ${d.common[16]}</small>${sol(d)}`);
['a','b','v'].forEach(id=>$(id).addEventListener('keydown',e=>{if(e.key==='Enter')(id==='v'?$('conv'):$('calc')).click()}));

// falling binary background
const c=$('rain'),x=c.getContext('2d');let cols,drops;
function size(){c.width=innerWidth;c.height=innerHeight;cols=Math.ceil(c.width/22);drops=Array.from({length:cols},()=>Math.random()*-40)}
size();addEventListener('resize',size);
setInterval(()=>{x.fillStyle='rgba(7,4,2,.14)';x.fillRect(0,0,c.width,c.height);x.font='18px JetBrains Mono, monospace';
 drops.forEach((y,i)=>{x.fillStyle=Math.random()<.08?'#ffd54a':'#ff8a1f';x.fillText(Math.random()<.5?'0':'1',i*22,y*22);
  drops[i]=y*22>c.height&&Math.random()>.975?0:y+1})},70);
</script></body></html>


