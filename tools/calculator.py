"""NeonAI: Tool implementation used by the router."""

import ast
import math
import re


import operator

# Safe math functions available
SAFE_FUNCTIONS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "abs": abs,
    "round": round,
    "pow": pow,
}

SAFE_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
}

_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node):
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.BinOp):
        left_val = _eval_node(node.left)
        right_val = _eval_node(node.right)
        op_callable = _OPERATORS.get(type(node.op))
        if op_callable is None:
            raise ValueError(f"Unsupported operator: {type(node.op)}")
        return op_callable(left_val, right_val)
    elif isinstance(node, ast.UnaryOp):
        operand_val = _eval_node(node.operand)
        op_callable = _OPERATORS.get(type(node.op))
        if op_callable is None:
            raise ValueError(f"Unsupported operator: {type(node.op)}")
        return op_callable(operand_val)
    elif isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only direct function calls are supported.")
        func_name = node.func.id
        if func_name not in SAFE_FUNCTIONS:
            raise ValueError(f"Unsupported function: {func_name}")
        args = [_eval_node(arg) for arg in node.args]
        return SAFE_FUNCTIONS[func_name](*args)
    elif isinstance(node, ast.Name):
        var_name = node.id
        if var_name in SAFE_CONSTANTS:
            return SAFE_CONSTANTS[var_name]
        raise ValueError(f"Unsupported variable/constant: {var_name}")
    else:
        raise ValueError(f"Unsupported expression node: {type(node)}")


def safe_eval(expression):
    """Safely evaluate a math expression using AST parsing."""
    try:
        # Clean expression
        expr = expression.strip()
        expr = expr.replace("^", "**")  # Power operator
        expr = expr.replace("×", "*").replace("÷", "/")
        expr = expr.replace(",", "")  # Remove commas from numbers

        # Prettify the spacing out of operators for readability (careful with **)
        pretty_expr = re.sub(r'(?<!\*)\*(?!\*)', ' * ', expr)
        pretty_expr = pretty_expr.replace("/", " / ").replace("+", " + ").replace("-", " - ")
        pretty_expr = re.sub(r'\s+', ' ', pretty_expr).strip()
        
        # Parse into AST tree
        node = ast.parse(expr, mode='eval').body
        
        # Evaluate 
        result = _eval_node(node)
        
        if isinstance(result, float) and result == int(result):
            result = int(result)
            
        return result, pretty_expr
    except Exception as e:
        return None, None


def handle(user_text):
    """Handle calculator queries. Returns string or None."""
    lower = user_text.lower()

    def parse_multi_word_numbers(text):
        units = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
        teens = {"ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
        tens = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
        
        # Clean commas and basic punctuation that might be attached to words
        text = text.replace(",", "").replace("?", "").replace("!", "")
        words = text.split()
        res_words = []
        i = 0
        while i < len(words):
            current_val = 0
            found = False
            
            while i < len(words):
                w = words[i].strip()
                val = -1
                if w in units: val = units[w]
                elif w in teens: val = teens[w]
                elif w in tens: val = tens[w]
                elif w == "and" and found and i + 1 < len(words) and (words[i+1] in units or words[i+1] in teens or words[i+1] in tens):
                    i += 1 # Skip 'and' in 'one hundred and five'
                    continue
                elif w == "hundred" and current_val > 0:
                    current_val *= 100
                    i += 1
                    found = True
                    continue
                
                if val != -1:
                    current_val += val
                    i += 1
                    found = True
                else:
                    break
            
            if found:
                res_words.append(str(current_val))
            else:
                res_words.append(words[i])
                i += 1
        return " ".join(res_words)

    lower = parse_multi_word_numbers(lower)

    # Pre-process common voice transcription artifacts for math
    replace_map = {
        "x": "*",
        "times": "*",
        "multiply": "*",
        "multiplied by": "*",
        "divide by": "/",
        "divided by": "/",
        "divide": "/",
        "over": "/",
        "plus": "+",
        "add": "+",
        "minus": "-",
        "subtract": "-",
        "squared": "**2",
        "cubed": "**3",
        "to the power of": "**",
        "power of": "**",
        "bracket open": "(",
        "open bracket": "(",
        "bracket close": ")",
        "close bracket": ")",
        "equals": "",
        "equal": "",
    }
    
    # Remove basic punctuation that voice transcription adds to numbers (like "9, multiply 9")
    lower = lower.replace(",", "")
    lower = lower.replace(".", "") if lower.endswith(".") else lower
    
    for word, symbol in replace_map.items():
        # Match standalone words to avoid replacing inside other unrelated words
        lower = re.sub(rf"\b{word}\b", symbol, lower)
        
    # Clean up any weird spacing caused by replacements
    lower = re.sub(r'\s+', ' ', lower).strip()

    # Direct math expressions (natural prefixes & raw math formulas matching)
    calc_patterns = [
        r"(?:calculate|compute|solve|what is|what's|how much is)\s+(.+?)(?:\?|$)",
        r"^(sqrt|log|sin|cos|tan|log10|abs)\s+(.+?)(?:\?|$)",
    ]

    for pattern in calc_patterns:
        match = re.search(pattern, lower)
        if match:
            if len(match.groups()) == 2:
                # Direct function call like "sqrt 16"
                expr = f"{match.group(1)}({match.group(2)})"
            else:
                expr = match.group(1).strip()
            
            # Auto-wrap function names if parens are missing: "sqrt 16" -> "sqrt(16)"
            for fn in SAFE_FUNCTIONS.keys():
                expr = re.sub(rf"\b{fn}\s+([0-9.]+)\b", rf"{fn}(\1)", expr)
                
            result, pretty_expr = safe_eval(expr)
            if result is not None:
                return f"🧮 **{pretty_expr}** = **{result}**"

    # Direct regex triggering (e.g. "5.5+5", "(10/2) * 4", "sqrt(16)")
    safe_funs = "|".join(SAFE_FUNCTIONS.keys())
    # Clean up "sqrt 16" -> "sqrt(16)" in direct math as well
    for fn in SAFE_FUNCTIONS.keys():
        lower = re.sub(rf"\b{fn}\s+([0-9.]+)\b", rf"{fn}(\1)", lower)

    math_pattern = rf'^([\s0-9+\-*/().,]|{safe_funs}|pi|e)+$'
    if re.fullmatch(math_pattern, lower, re.IGNORECASE):
        result, pretty_expr = safe_eval(lower)
        if result is not None:
            return f"🧮 **{pretty_expr}** = **{result}**"

    # Aggressive math extraction (Fallback if semantic router insists it's math)
    # E.g. "can you tell me 5 + 5" -> "5 + 5"
    cleaned_for_math = re.sub(r'[a-z]+', '', lower).strip()
    if re.fullmatch(r'^[\s0-9+\-*/().,]+$', cleaned_for_math):
        result, pretty_expr = safe_eval(cleaned_for_math)
        if result is not None:
            return f"🧮 **{pretty_expr}** = **{result}**"

    # Unit conversions
    conv_patterns = [
        (r"(\d+\.?\d*)\s*(?:km|kilometers?)\s+(?:to|in)\s+(?:miles?|mi)", lambda x: (x * 0.621371, "miles")),
        (r"(\d+\.?\d*)\s*(?:miles?|mi)\s+(?:to|in)\s+(?:km|kilometers?)", lambda x: (x * 1.60934, "km")),
        (r"(\d+\.?\d*)\s*(?:kg|kilograms?)\s+(?:to|in)\s+(?:pounds?|lbs?)", lambda x: (x * 2.20462, "lbs")),
        (r"(\d+\.?\d*)\s*(?:pounds?|lbs?)\s+(?:to|in)\s+(?:kg|kilograms?)", lambda x: (x * 0.453592, "kg")),
        (r"(\d+\.?\d*)\s*(?:°?[cC]|celsius)\s+(?:to|in)\s+(?:°?[fF]|fahrenheit)", lambda x: (x * 9/5 + 32, "°F")),
        (r"(\d+\.?\d*)\s*(?:°?[fF]|fahrenheit)\s+(?:to|in)\s+(?:°?[cC]|celsius)", lambda x: ((x - 32) * 5/9, "°C")),
        (r"(\d+\.?\d*)\s*(?:cm|centimeters?)\s+(?:to|in)\s+(?:inches?|in)", lambda x: (x * 0.393701, "inches")),
        (r"(\d+\.?\d*)\s*(?:inches?)\s+(?:to|in)\s+(?:cm|centimeters?)", lambda x: (x * 2.54, "cm")),
        (r"(\d+\.?\d*)\s*(?:m|meters?|metres?)\s+(?:to|in)\s+(?:feet|ft)", lambda x: (x * 3.28084, "feet")),
        (r"(\d+\.?\d*)\s*(?:feet|ft)\s+(?:to|in)\s+(?:m|meters?|metres?)", lambda x: (x * 0.3048, "meters")),
        (r"(\d+\.?\d*)\s*(?:l|liters?)\s+(?:to|in)\s+(?:gal|gallons?)", lambda x: (x * 0.264172, "gallons")),
        (r"(\d+\.?\d*)\s*(?:gal|gallons?)\s+(?:to|in)\s+(?:l|liters?)", lambda x: (x * 3.78541, "liters")),
        (r"(\d+\.?\d*)\s*(?:secs?|seconds?)\s+(?:to|in)\s+(?:mins?|minutes?)", lambda x: (x / 60, "minutes")),
        (r"(\d+\.?\d*)\s*(?:mins?|minutes?)\s+(?:to|in)\s+(?:secs?|seconds?)", lambda x: (x * 60, "seconds")),
        (r"(\d+\.?\d*)\s*(?:kb|kilobytes?)\s+(?:to|in)\s+(?:mb|megabytes?)", lambda x: (x / 1024, "MB")),
        (r"(\d+\.?\d*)\s*(?:mb|megabytes?)\s+(?:to|in)\s+(?:gb|gigabytes?)", lambda x: (x / 1024, "GB")),
    ]

    for pattern, converter in conv_patterns:
        match = re.search(pattern, lower)
        if match:
            value = float(match.group(1))
            result, unit = converter(value)
            return f"📐 **{value}** = **{round(result, 2)} {unit}**"

    return None
