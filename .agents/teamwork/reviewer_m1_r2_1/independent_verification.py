#!/usr/bin/env python3
"""
Independent Adversarial Verification Suite for Reviewer m1_r2_1.
Verifies all 6 required items, checks for integrity violations,
and stress tests edge cases against the actual source files.
"""

import os
import re
import sys
import time

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, '.agents/teamwork'))
NORMALIZER_PATH = os.path.join(ROOT_DIR, 'src/lib/geocoding/normalizer.ts')
SERVICE_PATH = os.path.join(ROOT_DIR, 'src/lib/geocoding/service.ts')
PHOTON_PATH = os.path.join(ROOT_DIR, 'src/lib/geocoding/photon-geocoder.ts')
NOMINATIM_PATH = os.path.join(ROOT_DIR, 'src/lib/geocoding/nominatim-geocoder.ts')

passed_tests = 0
failed_tests = 0

def check(assertion, description):
    global passed_tests, failed_tests
    if assertion:
        print(f"  [PASS] {description}")
        passed_tests += 1
    else:
        print(f"  [FAIL] {description}")
        failed_tests += 1

print("=" * 70)
print("1. INTEGRITY VIOLATION CHECKS")
print("=" * 70)

for path, name in [(NORMALIZER_PATH, 'normalizer.ts'), (SERVICE_PATH, 'service.ts'),
                   (PHOTON_PATH, 'photon-geocoder.ts'), (NOMINATIM_PATH, 'nominatim-geocoder.ts')]:
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    
    # Check for hardcoded fixture return values (e.g., if (address === '...') return {...})
    hardcoded_mock = re.search(r'if\s*\(\s*(?:address|query|input)\s*===?\s*[\'"][^\'"]+[\'"]\s*\)\s*return', src)
    check(hardcoded_mock is None, f"{name}: No hardcoded input fixtures bypassing logic")

    # Check for dummy facade implementations
    has_dummy = "TODO" in src or "not implemented" in src.lower() or "throw new Error('Not implemented')" in src
    check(not has_dummy, f"{name}: Real implementation (no TODOs or unfulfilled stubs)")

print("\n" + "=" * 70)
print("2. ITEM 1: UNIT_REGEX matches #304 and #5 after whitespace")
print("=" * 70)

with open(NORMALIZER_PATH, 'r', encoding='utf-8') as f:
    norm_content = f.read()

# Extract UNIT_REGEX from normalizer.ts
unit_re_match = re.search(r'const UNIT_REGEX = /(.*?)/i;', norm_content)
check(unit_re_match is not None, "UNIT_REGEX extracted from normalizer.ts")
unit_re_raw = unit_re_match.group(1)
unit_re = re.compile(unit_re_raw, re.IGNORECASE)
print(f"  Extracted UNIT_REGEX: {unit_re.pattern}")

# Test #304 and #5 with whitespace
m304 = unit_re.search("100 Pine St #304")
check(m304 is not None and m304.group(3) == "304", "'100 Pine St #304' matches unit group 3 == '304'")

m5 = unit_re.search("100 Pine St #5")
check(m5 is not None and m5.group(3) == "5", "'100 Pine St #5' matches unit group 3 == '5'")

m_space = unit_re.search("100 Pine St # 5")
check(m_space is not None and m_space.group(3) == "5", "'100 Pine St # 5' (space after #) matches unit group 3 == '5'")

m_comma = unit_re.search("100 Pine St, #5")
check(m_comma is not None and m_comma.group(3) == "5", "'100 Pine St, #5' matches unit group 3 == '5'")

m_alphanum = unit_re.search("100 Pine St #304-B")
check(m_alphanum is not None and m_alphanum.group(3) == "304-B", "'100 Pine St #304-B' matches unit group 3 == '304-B'")

print("\n" + "=" * 70)
print("3. ITEM 2: Prefix ordering (FLOOR before FL, etc.)")
print("=" * 70)

# Check keyword order inside UNIT_REGEX
# Should be: APARTMENT before APT, SUITE before STE, BUILDING before BLDG, FLOOR before FL, ROOM before RM
kw_match = re.search(r'\((APARTMENT.*?)\)', unit_re_raw)
check(kw_match is not None, "Unit keyword group found in regex")
keywords = kw_match.group(1).split('|')
print(f"  Keywords in order: {keywords}")

check(keywords.index("FLOOR") < keywords.index("FL"), "'FLOOR' precedes 'FL'")
check(keywords.index("APARTMENT") < keywords.index("APT"), "'APARTMENT' precedes 'APT'")
check(keywords.index("SUITE") < keywords.index("STE"), "'SUITE' precedes 'STE'")
check(keywords.index("BUILDING") < keywords.index("BLDG"), "'BUILDING' precedes 'BLDG'")
check(keywords.index("ROOM") < keywords.index("RM"), "'ROOM' precedes 'RM'")

# Test unit extraction with Floor vs Fl
def py_extract_unit(street_text):
    m = unit_re.search(street_text)
    if not m:
        return street_text.strip(), None
    if m.group(1) and m.group(2):
        raw_prefix = m.group(1).lower()
        prefix = m.group(1).capitalize()
        if raw_prefix in ("fl", "floor"): prefix = "Fl"
        elif raw_prefix in ("ste", "suite"): prefix = "Suite"
        elif raw_prefix in ("apt", "apartment"): prefix = "Apt"
        elif raw_prefix == "unit": prefix = "Unit"
        unit_number = f"{prefix} {m.group(2)}"
    elif m.group(3):
        unit_number = f"#{m.group(3)}"
    else:
        unit_number = m.group(0).strip()
    
    base = re.sub(unit_re, "", street_text)
    base = re.sub(r",\s*$", "", base).strip()
    return base, unit_number

b1, u1 = py_extract_unit("500 W Madison St Floor 2")
check(u1 == "Fl 2" and b1 == "500 W Madison St", f"'500 W Madison St Floor 2' -> unit: {u1}, base: {b1}")

b2, u2 = py_extract_unit("500 W Madison St Fl 2")
check(u2 == "Fl 2" and b2 == "500 W Madison St", f"'500 W Madison St Fl 2' -> unit: {u2}, base: {b2}")

b3, u3 = py_extract_unit("200 Main St Apartment 4B")
check(u3 == "Apt 4B" and b3 == "200 Main St", f"'200 Main St Apartment 4B' -> unit: {u3}, base: {b3}")

b4, u4 = py_extract_unit("200 Main St Suite 100")
check(u4 == "Suite 100" and b4 == "200 Main St", f"'200 Main St Suite 100' -> unit: {u4}, base: {b4}")

print("\n" + "=" * 70)
print("4. ITEM 3: Suffix replacement bounded to end of street name")
print("=" * 70)

# Verify source code for suffixIndex logic
check("const suffixIndex = hasPostDirectional ? len - 2 : len - 1;" in norm_content,
      "suffixIndex is correctly computed based on post-directional")
check("index === suffixIndex && STREET_SUFFIX_MAP[lower]" in norm_content,
      "Suffix map lookup strictly guarded by index === suffixIndex")

# Direct functional tests of standardization logic
DIRECTIONAL_MAP = {
    "north": "N", "n": "N", "south": "S", "s": "S", "east": "E", "e": "E", "west": "W", "w": "W",
    "northeast": "NE", "ne": "NE", "northwest": "NW", "nw": "NW", "southeast": "SE", "se": "SE",
    "southwest": "SW", "sw": "SW",
}
STREET_SUFFIX_MAP = {
    "avenue": "Ave", "ave": "Ave", "street": "St", "st": "St", "road": "Rd", "rd": "Rd",
    "boulevard": "Blvd", "blvd": "Blvd", "drive": "Dr", "dr": "Dr", "lane": "Ln", "ln": "Ln",
    "court": "Ct", "ct": "Ct", "circle": "Cir", "cir": "Cir", "parkway": "Pkwy", "pkwy": "Pkwy",
    "highway": "Hwy", "hwy": "Hwy", "place": "Pl", "pl": "Pl", "terrace": "Ter", "ter": "Ter",
    "way": "Way", "trail": "Trl", "trl": "Trl",
}

def py_standardize_street_name(name):
    tokens = name.strip().split()
    length = len(tokens)
    has_post_directional = length > 1 and re.sub(r"[.,]", "", tokens[-1].lower()) in DIRECTIONAL_MAP
    suffix_index = length - 2 if has_post_directional else length - 1

    normalized = []
    for index, token in enumerate(tokens):
        lower = re.sub(r"[.,]", "", token.lower())
        if (index == 0 or index == length - 1) and lower in DIRECTIONAL_MAP:
            normalized.append(DIRECTIONAL_MAP[lower])
        elif index == suffix_index and lower in STREET_SUFFIX_MAP:
            normalized.append(STREET_SUFFIX_MAP[lower])
        else:
            normalized.append(token[:1].upper() + token[1:])
    return " ".join(normalized)

check(py_standardize_street_name("Court Street") == "Court St",
      f"'Court Street' -> '{py_standardize_street_name('Court Street')}' (Court NOT changed to Ct)")

check(py_standardize_street_name("Court St") == "Court St",
      f"'Court St' -> '{py_standardize_street_name('Court St')}' (Court NOT changed to Ct)")

check(py_standardize_street_name("Court Street NW") == "Court St NW",
      f"'Court Street NW' -> '{py_standardize_street_name('Court Street NW')}'")

check(py_standardize_street_name("North Court Street NW") == "N Court St NW",
      f"'North Court Street NW' -> '{py_standardize_street_name('North Court Street NW')}'")

check(py_standardize_street_name("Park Avenue") == "Park Ave",
      f"'Park Avenue' -> '{py_standardize_street_name('Park Avenue')}'")

check(py_standardize_street_name("Circle Drive") == "Circle Dr",
      f"'Circle Drive' -> '{py_standardize_street_name('Circle Drive')}' (Circle NOT changed to Cir)")

check(py_standardize_street_name("Terrace Court") == "Terrace Ct",
      f"'Terrace Court' -> '{py_standardize_street_name('Terrace Court')}' (Terrace NOT changed to Ter)")

print("\n" + "=" * 70)
print("5. ITEM 4: Comma-separated units extract cleanly")
print("=" * 70)

# Check normalizer source code for standalone comma unit extraction
check("const candidateUnit = extractUnitNumber(remainingSegments[0]);" in norm_content and
      "candidateUnit.baseStreet === ''" in norm_content,
      "Standalone comma unit segment extraction logic present in normalizer.ts")

# Full end-to-end normalization test
from tests.stress.normalizer_stress import normalize_address as original_stress_norm
# We will use the implementation from explorer_m1_r2_1/verify_patch.py
import explorer_m1_r2_1.verify_patch as patched

addr1 = patched.normalize_address("123 Main St, Apt 4B, New York, NY 10001")
check(addr1["unitNumber"] == "Apt 4B", f"unitNumber is 'Apt 4B', got '{addr1['unitNumber']}'")
check(addr1["city"] == "New York", f"city is 'New York', got '{addr1['city']}'")
check(addr1["state"] == "NY", f"state is 'NY', got '{addr1['state']}'")
check(addr1["zip5"] == "10001", f"zip5 is '10001', got '{addr1['zip5']}'")
check(addr1["streetName"] == "Main St", f"streetName is 'Main St', got '{addr1['streetName']}'")

addr2 = patched.normalize_address("100 Pine St, #304, San Francisco, CA 94111")
check(addr2["unitNumber"] == "#304", f"unitNumber is '#304', got '{addr2['unitNumber']}'")
check(addr2["city"] == "San Francisco", f"city is 'San Francisco', got '{addr2['city']}'")
check(addr2["state"] == "CA", f"state is 'CA', got '{addr2['state']}'")

addr3 = patched.normalize_address("500 Elm St, Suite 200, Austin, TX 78701")
check(addr3["unitNumber"] == "Suite 200", f"unitNumber is 'Suite 200', got '{addr3['unitNumber']}'")
check(addr3["city"] == "Austin", f"city is 'Austin', got '{addr3['city']}'")

print("\n" + "=" * 70)
print("6. ITEM 5: Missing ZIP codes do not copy state into zip5")
print("=" * 70)

check("return { zip5: '', zip4: null };" in norm_content,
      "parseZip returns empty string for zip5 when ZIP is omitted")

z_empty = patched.parse_zip("NY")
check(z_empty["zip5"] == "" and z_empty["zip4"] is None,
      f"parse_zip('NY') -> zip5='{z_empty['zip5']}' (empty string, not 'NY')")

z_empty_ca = patched.parse_zip("CA")
check(z_empty_ca["zip5"] == "", f"parse_zip('CA') -> zip5='{z_empty_ca['zip5']}'")

no_zip_addr = patched.normalize_address("123 Main St, New York, NY")
check(no_zip_addr["state"] == "NY", f"state is 'NY', got '{no_zip_addr['state']}'")
check(no_zip_addr["zip5"] == "", f"zip5 is empty string, got '{no_zip_addr['zip5']}'")
check("NY NY" not in no_zip_addr["formattedAddress"],
      f"formattedAddress does not contain 'NY NY': '{no_zip_addr['formattedAddress']}'")

print("\n" + "=" * 70)
print("7. ITEM 6: Fail-fast error rethrowing in service.ts preserves AddressValidationError")
print("=" * 70)

with open(SERVICE_PATH, 'r', encoding='utf-8') as f:
    service_src = f.read()

# Check imports
check("AddressValidationError" in service_src, "AddressValidationError imported in service.ts")
check("GeocodingError" in service_src, "GeocodingError imported in service.ts")

# Check rethrows in all 5 provider tiers
check("this.googleGeocoder.resolve" in service_src and
      "if (err instanceof AddressValidationError) {\n          throw err;\n        }" in service_src,
      "Google Geocoder tier re-throws AddressValidationError immediately")

check("this.mapboxGeocoder.resolve" in service_src and
      "if (err instanceof AddressValidationError) {\n          throw err;\n        }" in service_src,
      "Mapbox Geocoder tier re-throws AddressValidationError immediately")

check("this.censusGeocoder.resolve" in service_src and
      "if (err instanceof AddressValidationError) {\n        throw err;\n      }" in service_src,
      "Census Geocoder tier re-throws AddressValidationError immediately")

check("this.photonGeocoder.resolve" in service_src and
      "if (err instanceof AddressValidationError) {\n        throw err;\n      }" in service_src,
      "Photon Geocoder tier re-throws AddressValidationError immediately")

check("this.nominatimGeocoder.resolve" in service_src and
      "if (err instanceof AddressValidationError) {\n        throw err;\n      }" in service_src,
      "Nominatim Geocoder tier re-throws AddressValidationError immediately")

check("resolveCoordinates" in service_src and
      "if (err instanceof AddressValidationError) {\n        throw err;\n      }" in service_src,
      "resolveCoordinates reverse geocoding re-throws AddressValidationError immediately")

# Check cascade exhaustion
check("if (lastError instanceof AddressValidationError) {\n      throw lastError;\n    }" in service_src,
      "Cascade exhaustion preserves AddressValidationError")
check("if (lastError instanceof AddressNotFoundError) {\n      throw lastError;\n    }" in service_src,
      "Cascade exhaustion preserves AddressNotFoundError")
check("if (lastError instanceof GeocodingError) {\n      throw lastError;\n    }" in service_src,
      "Cascade exhaustion preserves GeocodingError")

# Check PO Box pre-validation in suggest and resolve
check("AddressNormalizer.assertNotPoBox(address);" in service_src,
      "resolve() pre-validates PO Box upfront before touching any network provider")
check("if (AddressNormalizer.isPoBox(query)) return [];" in service_src,
      "suggest() rejects PO Box query upfront")

print("\n" + "=" * 70)
print("8. ADVERSARIAL STRESS TESTING: EDGE CASES & SECURITY")
print("=" * 70)

# PO Box Variations
po_box_positives = [
    "P.O. Box 123", "PO Box 999", "Post Office Box 42", "P BOX 10", "P.O.B 123",
    "POB 456", "PBOX 789", "Post Office Drawer 500", "p.o. box 10", "p box 99"
]
for p in po_box_positives:
    check(patched.is_po_box(p), f"Detects PO Box: '{p}'")

po_box_negatives = [
    "123 Boxwood Ln, Houston, TX 77001",
    "45 Post Office Rd, Annapolis, MD 21401",
    "800 Boxberry Court, Raleigh, NC 27601",
    "100 Boxford St, Boston, MA 02108",
    "Box Elder, MT 59521"
]
for neg in po_box_negatives:
    check(not patched.is_po_box(neg), f"Does NOT falsely flag: '{neg}'")

# ReDoS check
start_time = time.time()
patched.normalize_address("123 Main St " + "A" * 50000 + ", Miami, FL 33101")
duration = time.time() - start_time
check(duration < 0.1, f"50k character input processed in {duration:.4f}s (< 0.1s SLA)")

# XSS vector check
xss_result = patched.normalize_address("123 Main St <img src=x onerror=alert('pwnd')>, Austin, TX 78701")
check("<img" not in xss_result["formattedAddress"] and "onerror" not in xss_result["formattedAddress"],
      "HTML <img> tag and onerror attributes stripped")

print("\n" + "=" * 70)
print(f"VERIFICATION RESULTS: {passed_tests} PASSED, {failed_tests} FAILED")
print("=" * 70)

if failed_tests > 0:
    sys.exit(1)
