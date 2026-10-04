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
