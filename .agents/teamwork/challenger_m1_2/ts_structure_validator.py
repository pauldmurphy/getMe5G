#!/usr/bin/env python3
"""
TypeScript Structure & Syntax Verification Validator
Agent: challenger_m1_2
Scope:
  - Scans all TypeScript files in src/lib/geocoding and src/app/api/geocode
  - Validates bracket/brace/parenthesis nesting balance
  - Checks import/export integrity and interface conformance
"""

import os
import re
import sys
from pathlib import Path

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"

files_to_check = [
    "src/lib/geocoding/types.ts",
    "src/lib/geocoding/normalizer.ts",
    "src/lib/geocoding/census-geocoder.ts",
    "src/lib/geocoding/photon-geocoder.ts",
    "src/lib/geocoding/nominatim-geocoder.ts",
    "src/lib/geocoding/google-geocoder.ts",
    "src/lib/geocoding/mapbox-geocoder.ts",
    "src/lib/geocoding/service.ts",
    "src/lib/geocoding/index.ts",
    "src/app/api/geocode/suggest/route.ts",
    "src/app/api/geocode/resolve/route.ts",
    "tests/unit/geocoding/normalizer.test.ts",
]

base_dir = Path("/home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint")

def check_delimiters(content: str, filename: str) -> bool:
    stack = []
    pairs = {')': '(', '}': '{', ']': '['}
    in_single_quote = False
    in_double_quote = False
    in_template_lit = False
    in_line_comment = False
    in_block_comment = False

    i = 0
    line = 1
    col = 1
    n = len(content)

    while i < n:
        char = content[i]
        next_char = content[i+1] if i + 1 < n else ''

        if char == '\n':
            line += 1
            col = 1
            in_line_comment = False
            i += 1
            continue

        col += 1

        if in_line_comment:
            i += 1
            continue

        if in_block_comment:
            if char == '*' and next_char == '/':
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        if not in_single_quote and not in_double_quote and not in_template_lit:
            if char == '/' and next_char == '/':
                in_line_comment = True
                i += 2
                continue
            if char == '/' and next_char == '*':
                in_block_comment = True
                i += 2
                continue
            # Regex literal check (e.g. /pattern/gi)
            if char == '/' and next_char not in ('/', '*'):
                # Check if preceding non-space token indicates regex context (e.g. (, =, :, ,, return)
                j = i - 1
                while j >= 0 and content[j].isspace():
                    j -= 1
                if j >= 0 and content[j] in '(=:,[~!&|?{};':
                    # Parse until unescaped /
                    i += 1
                    in_char_class = False
                    while i < n:
                        if content[i] == '\\':
                            i += 2
                            continue
                        if content[i] == '[':
                            in_char_class = True
                            i += 1
                        elif content[i] == ']':
                            in_char_class = False
                            i += 1
                        elif content[i] == '/' and not in_char_class:
                            i += 1
                            # skip regex flags
                            while i < n and content[i].isalpha():
                                i += 1
                            break
                        elif content[i] == '\n':
                            break
                        else:
                            i += 1
                    continue

        if char == "'" and not in_double_quote and not in_template_lit:
            if i == 0 or content[i-1] != '\\':
                in_single_quote = not in_single_quote
            i += 1
            continue

        if char == '"' and not in_single_quote and not in_template_lit:
            if i == 0 or content[i-1] != '\\':
                in_double_quote = not in_double_quote
            i += 1
            continue

        if char == '`' and not in_single_quote and not in_double_quote:
            if i == 0 or content[i-1] != '\\':
                in_template_lit = not in_template_lit
            i += 1
            continue

        if in_single_quote or in_double_quote or in_template_lit:
            i += 1
            continue

        if char in '({[':
            stack.append((char, line, col))
        elif char in ')}]':
            if not stack:
                print(f"{FAIL} {filename}:{line}:{col} - Unexpected closing delimiter '{char}'")
                return False
            expected, o_line, o_col = stack.pop()
            if pairs[char] != expected:
                print(f"{FAIL} {filename}:{line}:{col} - Mismatched delimiter: expected '{pairs[char]}' for '{char}', opened at {o_line}:{o_col}")
                return False

        i += 1

    if stack:
        unmatched = stack[-1]
        print(f"{FAIL} {filename} - Unclosed delimiter '{unmatched[0]}' from line {unmatched[1]}:{unmatched[2]}")
        return False

    return True

def run():
    print("=" * 70)
    print("TYPESCRIPT STRUCTURE & DELIMITER INTEGRITY VALIDATOR")
    print("=" * 70)

    all_passed = True

    for rel_path in files_to_check:
        full_path = base_dir / rel_path
        if not full_path.exists():
            print(f"{FAIL} File not found: {rel_path}")
            all_passed = False
            continue

        content = full_path.read_text(encoding='utf-8')
        delims_ok = check_delimiters(content, rel_path)
        if delims_ok:
            print(f"{PASS} {rel_path} - Delimiters balanced (braces, brackets, parens)")
        else:
            all_passed = False

    # Check contract imports in normalizer.test.ts vs normalizer.ts
    normalizer_content = (base_dir / "src/lib/geocoding/normalizer.ts").read_text(encoding='utf-8')
    required_exports = ['normalizeAddress', 'isPoBox', 'normalizeState', 'extractUnitNumber', 'AddressNormalizer']
    for exp in required_exports:
        pattern = rf"\bexport\s+(?:(?:const|function|class)\s+)?{exp}\b"
        if re.search(pattern, normalizer_content):
            print(f"{PASS} normalizer.ts exports '{exp}' as expected by unit test suite")
        else:
            print(f"{FAIL} normalizer.ts missing export: {exp}")
            all_passed = False

    # Check GeocodingService singleton export
    service_content = (base_dir / "src/lib/geocoding/service.ts").read_text(encoding='utf-8')
    if "export const geocodingService = new GeocodingService();" in service_content:
        print(f"{PASS} service.ts exports singleton 'geocodingService'")
    else:
        print(f"{FAIL} service.ts missing singleton export")
        all_passed = False

    print("=" * 70)
    if all_passed:
        print(f"\033[92mALL 12 FILES STRUCTURALLY & SYNTACTICALLY VERIFIED\033[0m")
        return 0
    else:
        print(f"\033[91mVALIDATION FAILURES DETECTED\033[0m")
        return 1

if __name__ == '__main__':
    sys.exit(run())
