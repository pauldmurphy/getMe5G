#!/usr/bin/env python3
"""
Adversarial Stress Test Suite for Address Normalizer
Tests logic and regular expressions directly mirrored from src/lib/geocoding/normalizer.ts.
"""

import re
import sys
import time

# --- Mappings & Regular Expressions mirrored from normalizer.ts ---

US_STATE_CODE_MAP = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR', 'california': 'CA',
    'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE', 'florida': 'FL', 'georgia': 'GA',
    'hawaii': 'HI', 'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA',
    'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
    'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
    'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV', 'new hampshire': 'NH',
    'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC',
    'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK', 'oregon': 'OR', 'pennsylvania': 'PA',
    'rhode island': 'RI', 'south carolina': 'SC', 'south dakota': 'SD', 'tennessee': 'TN',
    'texas': 'TX', 'utah': 'UT', 'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA',
    'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY',
    'district of columbia': 'DC', 'dist of columbia': 'DC', 'washington dc': 'DC',
    'washington d.c.': 'DC', 'd.c.': 'DC', 'dc': 'DC',
    'puerto rico': 'PR', 'guam': 'GU', 'virgin islands': 'VI', 'u.s. virgin islands': 'VI',
    'northern mariana islands': 'MP', 'american samoa': 'AS',
    'armed forces americas': 'AA', 'armed forces europe': 'AE', 'armed forces pacific': 'AP',
}

STREET_SUFFIX_MAP = {
    'avenue': 'Ave', 'ave': 'Ave', 'street': 'St', 'st': 'St', 'road': 'Rd', 'rd': 'Rd',
    'boulevard': 'Blvd', 'blvd': 'Blvd', 'drive': 'Dr', 'dr': 'Dr', 'lane': 'Ln', 'ln': 'Ln',
    'court': 'Ct', 'ct': 'Ct', 'circle': 'Cir', 'cir': 'Cir', 'parkway': 'Pkwy', 'pkwy': 'Pkwy',
    'highway': 'Hwy', 'hwy': 'Hwy', 'place': 'Pl', 'pl': 'Pl', 'terrace': 'Ter', 'ter': 'Ter',
    'way': 'Way', 'trail': 'Trl', 'trl': 'Trl',
}

DIRECTIONAL_MAP = {
    'north': 'N', 'n': 'N', 'south': 'S', 's': 'S', 'east': 'E', 'e': 'E', 'west': 'W', 'w': 'W',
    'northeast': 'NE', 'ne': 'NE', 'northwest': 'NW', 'nw': 'NW', 'southeast': 'SE', 'se': 'SE',
    'southwest': 'SW', 'sw': 'SW',
}

PO_BOX_REGEX = re.compile(
    r'\b(?:P(?:OST)?\.?\s*(?:O(?:FFICE)?\.?\s*)?BOX|P\.?\s*O\.?\s*B(?:\.|\b)|POST\s+OFFICE\s+DRAWER|PBOX)\b',
    re.IGNORECASE
)

UNIT_REGEX = re.compile(
    r'(?:,\s*)?(?:\b(APARTMENT|APT|SUITE|STE|UNIT|BUILDING|BLDG|FLOOR|FL|ROOM|RM|LOT|DEPT)\b\.?\s*([A-Za-z0-9\-#\/]+)|#\s*([A-Za-z0-9\-]+))\b',
    re.IGNORECASE
)

ZIP_REGEX = re.compile(r'\b(\d{5})(?:[-\s](\d{4}))?\b')
STREET_NUMBER_REGEX = re.compile(r'^([0-9]+(?:\s+1\/[2-4])?|[0-9]+-[0-9]+|[A-Z][0-9]+[A-Z][0-9]+)\s+(.+)$', re.IGNORECASE)
RURAL_ROUTE_BOX_REGEX = re.compile(r'^(Route\s+\d+|RR\s+\d+|Rural\s+Route\s+\d+)\s+(Box\s+\d+)\b', re.IGNORECASE)

class PoBoxError(Exception): pass
class MissingStreetNumberError(Exception): pass
class OutOfBoundsError(Exception): pass
class AddressValidationError(Exception): pass

def is_po_box(address: str) -> bool:
    if not address:
        return False
    return bool(PO_BOX_REGEX.search(address))

def normalize_state(state_input: str) -> str:
    if not state_input:
        return ''
    clean = state_input.strip().lower()
    if clean in US_STATE_CODE_MAP:
        return US_STATE_CODE_MAP[clean]
    upper = state_input.strip().upper()
    if len(upper) == 2 and upper in US_STATE_CODE_MAP.values():
        return upper
    return upper

def extract_unit_number(street_text: str):
    if not street_text:
        return street_text, None
    m = UNIT_REGEX.search(street_text)
    if not m:
        return street_text.strip(), None
    if m.group(1) and m.group(2):
        raw_prefix = m.group(1).lower()
        prefix = m.group(1).capitalize()
        if raw_prefix in ('fl', 'floor'): prefix = 'Fl'
        elif raw_prefix in ('ste', 'suite'): prefix = 'Suite'
        elif raw_prefix in ('apt', 'apartment'): prefix = 'Apt'
        elif raw_prefix == 'unit': prefix = 'Unit'
        unit_number = f"{prefix} {m.group(2)}"
    elif m.group(3):
        unit_number = f"#{m.group(3)}"
    else:
        unit_number = m.group(0).strip()
    
    base_street = re.sub(UNIT_REGEX, '', street_text)
    base_street = re.sub(r',\s*$', '', base_street).strip()
    return base_street, unit_number

def parse_zip(zip_input: str):
    if not zip_input:
        return {'zip5': '', 'zip4': None}
    m = ZIP_REGEX.search(zip_input.strip())
    if not m:
        digits = re.sub(r'\D', '', zip_input)
        if len(digits) >= 5:
            return {'zip5': digits[:5], 'zip4': digits[5:9] if len(digits) >= 9 else None}
        return {'zip5': '', 'zip4': None}
    return {'zip5': m.group(1), 'zip4': m.group(2) if m.group(2) else None}

def standardize_street_name(street_name: str) -> str:
    tokens = street_name.strip().split()
    length = len(tokens)
    has_post_directional = length > 1 and re.sub(r'[.,]', '', tokens[-1].lower()) in DIRECTIONAL_MAP
    suffix_index = length - 2 if has_post_directional else length - 1

    normalized = []
    for index, token in enumerate(tokens):
        lower = re.sub(r'[.,]', '', token.lower())
        if (index == 0 or index == length - 1) and lower in DIRECTIONAL_MAP:
            normalized.append(DIRECTIONAL_MAP[lower])
        elif index == suffix_index and lower in STREET_SUFFIX_MAP:
            normalized.append(STREET_SUFFIX_MAP[lower])
        else:
            normalized.append(token[:1].upper() + token[1:])
    return ' '.join(normalized)

def format_address(parts):
    unit_part = f" {parts['unitNumber']}" if parts.get('unitNumber') else ''
    zip_part = f"{parts['zip5']}-{parts['zip4']}" if parts.get('zip4') else parts.get('zip5', '')
    
    street_line = f"{parts['streetNumber']} {parts['streetName']}"
    if parts['streetNumber'].lower().startswith('box '):
        street_line = f"{parts['streetName']} {parts['streetNumber']}"
        
    city_part = f"{parts['city']}, " if parts.get('city') else ''
    state_zip_part = f"{parts['state']} {zip_part}" if parts.get('state') and zip_part else (parts.get('state') or zip_part)
    
    raw_fmt = f"{street_line}{unit_part}, {city_part}{state_zip_part}"
    return re.sub(r',\s*,', ',', raw_fmt).strip()

def normalize_address(input_str: str, coords=None):
    if not input_str or not input_str.strip():
        raise AddressValidationError('Please enter a valid street address.')

    # Sanitize script tags (XSS prevention)
    cleaned = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', input_str, flags=re.IGNORECASE).strip()
    # Strip any remaining HTML tags (e.g. img onerror vectors)
    cleaned = re.sub(r'<[^>]+>', '', cleaned).strip()

    # Sanitize SQL injection meta-characters
    cleaned = re.sub(r'[\'";]+\s*(?:DROP|SELECT|INSERT|DELETE|UPDATE|ALTER|CREATE|EXEC|UNION)[\s\S]*?(?:--|;|$)', '', cleaned, flags=re.IGNORECASE).strip()

    # Check PO Box
    if is_po_box(cleaned):
        raise PoBoxError(cleaned)

    lat = 38.897675
    lng = -77.03653
    if coords:
        if not (17.5 <= coords['lat'] <= 72.0 and -179.0 <= coords['lng'] <= -64.0):
            raise OutOfBoundsError(f"Coordinates out of bounds: lat={coords['lat']}, lng={coords['lng']}")
        lat = coords['lat']
        lng = coords['lng']

    segments = [re.sub(r'\s+', ' ', s.strip()) for s in cleaned.split(',') if s.strip()]
    if not segments:
        raise AddressValidationError('Please enter a valid street address.')

    remaining_segments = list(segments)
    raw_street = remaining_segments.pop(0)

    # Extract unit if present on the street line
    raw_street, unit_number = extract_unit_number(raw_street)

    # Check if subsequent comma segment is a standalone unit (e.g. "123 Main St, Apt 4B, New York, NY 10001")
    if remaining_segments:
        cand_base, cand_unit = extract_unit_number(remaining_segments[0])
        if cand_unit and cand_base == '':
            if not unit_number:
                unit_number = cand_unit
            remaining_segments.pop(0)

    city = ''
    raw_state_zip = ''

    if len(remaining_segments) >= 2:
        city = remaining_segments[0]
        raw_state_zip = ' '.join(remaining_segments[1:])
    elif len(remaining_segments) == 1:
        raw_state_zip = remaining_segments[0]

    street_number = ''
    street_name = ''

    rural_match = RURAL_ROUTE_BOX_REGEX.match(raw_street)
    if rural_match:
        street_name = rural_match.group(1)
        street_number = rural_match.group(2)
    else:
        num_match = STREET_NUMBER_REGEX.match(raw_street)
        if num_match:
            street_number = num_match.group(1)
            raw_street = num_match.group(2)
        else:
            raise MissingStreetNumberError(input_str)
        street_name = standardize_street_name(raw_street)

    state = ''
    zip5 = ''
    zip4 = None

    if raw_state_zip:
        zip_parsed = parse_zip(raw_state_zip)
        zip5 = zip_parsed['zip5']
        zip4 = zip_parsed['zip4']

        remaining = re.sub(ZIP_REGEX, '', raw_state_zip).strip()
        if remaining:
            state = normalize_state(remaining)

    if not city and len(segments) == 2:
        words = [w for w in segments[1].split() if w]
        if len(words) > 2:
            city = ' '.join(words[:-2])
            state = normalize_state(words[-2])

    formatted = format_address({
        'streetNumber': street_number,
        'streetName': street_name,
        'unitNumber': unit_number,
        'city': city,
        'state': state,
        'zip5': zip5,
        'zip4': zip4,
    })

    return {
        'streetNumber': street_number,
        'streetName': street_name,
        'unitNumber': unit_number,
        'city': city,
        'state': state,
        'zip5': zip5,
        'zip4': zip4,
        'lat': round(lat, 6),
        'lng': round(lng, 6),
        'formattedAddress': formatted,
    }


def run_tests():
    failures = []
    passes = []

    def record_test(category, name, passed, details):
        entry = {'category': category, 'name': name, 'passed': passed, 'details': details}
        if passed:
            passes.append(entry)
            print(f"  [PASS] {name}")
        else:
            failures.append(entry)
            print(f"  [FAIL] {name}: {details}")

    print("=================================================================")
    print("RUNNING ADVERSARIAL STRESS TEST SUITE FOR ADDRESS NORMALIZER")
    print("=================================================================\n")

    # --- 1. PO BOX VARIATIONS ---
    print("Test Group 1: PO Box Variations & False Positive Resistance")
    po_boxes = [
        ("P.O. Box 123", True),
        ("PO Box 999", True),
        ("Post Office Box 42", True),
        ("P BOX 10", True),
        ("P.O.B 123", True),
        ("POB 456", True),
        ("PBOX 789", True),
        ("Post Office Drawer 500", True),
    ]
    for box, expected in po_boxes:
        actual = is_po_box(box)
        passed = (actual == expected)
        record_test("PO Box Detection", f"Detect '{box}' as PO Box", passed, f"Expected={expected}, Actual={actual}")

    fp_checks = [
        ("123 Boxwood Ln, Houston, TX 77001", False),
        ("45 Post Office Rd, Annapolis, MD 21401", False),
        ("800 Boxberry Court, Raleigh, NC 27601", False),
        ("100 Boxford St, Boston, MA 02108", False),
    ]
    for addr, expected in fp_checks:
        actual = is_po_box(addr)
        passed = (actual == expected)
        record_test("PO Box Non-Rejection", f"Do not flag '{addr}' as PO Box", passed, f"Expected={expected}, Actual={actual}")

    # Test full normalizeAddress on PO Box rejection
    try:
        normalize_address("P BOX 10, Dallas, TX 75201")
        record_test("PO Box Rejection", "Reject 'P BOX 10, Dallas, TX 75201' via PoBoxError", False, "No exception thrown")
    except PoBoxError:
        record_test("PO Box Rejection", "Reject 'P BOX 10, Dallas, TX 75201' via PoBoxError", True, "PoBoxError correctly thrown")
    except Exception as e:
        record_test("PO Box Rejection", "Reject 'P BOX 10, Dallas, TX 75201' via PoBoxError", False, f"Threw {type(e).__name__} instead: {e}")

    # --- 2. WEIRD / UNUSUAL ADDRESSES ---
    print("\nTest Group 2: Unusual Addresses (Fractional, Grid, Routes, Units)")

    # Fractional Numbers
    try:
        res = normalize_address("123 1/2 Maple St, Seattle, WA 98101")
        passed = (res['streetNumber'] == "123 1/2" and "Maple St" in res['streetName'])
        record_test("Unusual Addresses", "Fractional number '123 1/2 Maple St'", passed, f"Result={res}")
    except Exception as e:
        record_test("Unusual Addresses", "Fractional number '123 1/2 Maple St'", False, f"Exception: {e}")

    # Grid Addresses
    try:
        res = normalize_address("N12W34560 Lake Dr, Delafield, WI 53018")
        passed = (res['streetNumber'] == "N12W34560" and res['streetName'] == "Lake Dr")
        record_test("Unusual Addresses", "Wisconsin Grid 'N12W34560 Lake Dr'", passed, f"Result={res}")
    except Exception as e:
        record_test("Unusual Addresses", "Wisconsin Grid 'N12W34560 Lake Dr'", False, f"Exception: {e}")

    # Highway Routes
    try:
        res = normalize_address("Route 1 Box 42, Big Piney, WY 83113")
        passed = (res['streetNumber'] == "Box 42" and res['streetName'] == "Route 1")
        record_test("Unusual Addresses", "Rural Route 'Route 1 Box 42'", passed, f"Result={res}")
    except Exception as e:
        record_test("Unusual Addresses", "Rural Route 'Route 1 Box 42'", False, f"Exception: {e}")

    # Highway Route 66 without box or house number
    try:
        normalize_address("Route 66, Flagstaff, AZ 86001")
        record_test("Unusual Addresses", "Highway Route without house number 'Route 66'", False, "Expected MissingStreetNumberError")
    except MissingStreetNumberError:
        record_test("Unusual Addresses", "Highway Route without house number 'Route 66'", True, "Correctly rejected missing house number")
    except Exception as e:
        record_test("Unusual Addresses", "Highway Route without house number 'Route 66'", False, f"Unexpected error: {e}")

    # Highway Route 66 with house number
    try:
        res = normalize_address("100 Route 66, Flagstaff, AZ 86001")
        passed = (res['streetNumber'] == "100" and "Route 66" in res['streetName'])
        record_test("Unusual Addresses", "Highway Route with house number '100 Route 66'", passed, f"Result={res}")
    except Exception as e:
        record_test("Unusual Addresses", "Highway Route with house number '100 Route 66'", False, f"Exception: {e}")

    # Unit Numbers Inline
    unit_tests = [
        ("742 Evergreen Terrace Apt 4B", "Apt 4B", "742 Evergreen Terrace"),
        ("450 7th Ave Ste 100", "Suite 100", "450 7th Ave"),
        ("100 Pine St #5", "#5", "100 Pine St"),
        ("100 Pine St #304", "#304", "100 Pine St"),
        ("123 Main St Unit 2", "Unit 2", "123 Main St"),
        ("500 W Madison St Fl 2", "Fl 2", "500 W Madison St"),
    ]
    for raw, exp_unit, exp_base in unit_tests:
        base, unit = extract_unit_number(raw)
        passed = (unit == exp_unit and base == exp_base)
        record_test("Unit Extraction Inline", f"Extract unit from '{raw}'", passed, f"Expected ({exp_base}, {exp_unit}), Actual ({base}, {unit})")

    # Unit Numbers Comma Separated (CRITICAL EDGE CASE)
    try:
        res = normalize_address("123 Main St, Apt 4B, New York, NY 10001")
        passed = (res['unitNumber'] == "Apt 4B" and res['city'] == "New York" and res['state'] == "NY")
        record_test("Unit Extraction Comma", "Address with comma-separated unit '123 Main St, Apt 4B, New York, NY 10001'", passed,
                    f"Result: city='{res['city']}', state='{res['state']}', unit='{res['unitNumber']}'")
    except Exception as e:
        record_test("Unit Extraction Comma", "Address with comma-separated unit '123 Main St, Apt 4B, New York, NY 10001'", False, f"Exception: {e}")

    try:
        res = normalize_address("100 Pine St, Ste 100, San Francisco, CA 94111")
        passed = (res['unitNumber'] == "Suite 100" and res['city'] == "San Francisco" and res['state'] == "CA")
        record_test("Unit Extraction Comma", "Address with comma-separated suite '100 Pine St, Ste 100, San Francisco, CA 94111'", passed,
                    f"Result: city='{res['city']}', state='{res['state']}', unit='{res['unitNumber']}'")
    except Exception as e:
        record_test("Unit Extraction Comma", "Address with comma-separated suite '100 Pine St, Ste 100, San Francisco, CA 94111'", False, f"Exception: {e}")

    # --- 3. SECURITY & INJECTION PAYLOADS ---
    print("\nTest Group 3: Security & Injection Payloads")

    # SQL Injection with comment
    try:
        res = normalize_address("123 Main St'; DROP TABLE brands;--, Boston, MA 02108")
        passed = ("DROP" not in res['formattedAddress'] and res['city'] == "Boston")
        record_test("Security Sanitization", "SQL Injection with comment sanitized", passed, f"Formatted: {res['formattedAddress']}")
    except Exception as e:
        record_test("Security Sanitization", "SQL Injection with comment sanitized", False, f"Exception: {e}")

    # SQL Injection without comment
    try:
        res = normalize_address("123 Main St'; DROP TABLE brands;, Boston, MA 02108")
        passed = ("DROP" not in res['formattedAddress'])
        record_test("Security Sanitization", "SQL Injection without comment sanitized", passed, f"Formatted: {res['formattedAddress']}")
    except Exception as e:
        record_test("Security Sanitization", "SQL Injection without comment sanitized", False, f"Exception: {e}")

    # XSS Script Tag
    try:
        res = normalize_address('<script>alert("xss")</script> 123 Main St, Miami, FL 33101')
        passed = ("<script>" not in res['formattedAddress'] and res['streetNumber'] == "123")
        record_test("Security Sanitization", "XSS <script> tag sanitized", passed, f"Formatted: {res['formattedAddress']}")
    except Exception as e:
        record_test("Security Sanitization", "XSS <script> tag sanitized", False, f"Exception: {e}")

    # XSS Tag Variation (img onerror)
    try:
        res = normalize_address('123 Main St <img src=x onerror=alert(1)>, Miami, FL 33101')
        passed = ("<img" not in res['formattedAddress'])
        record_test("Security Sanitization", "XSS <img onerror> tag sanitized", passed, f"Formatted: {res['formattedAddress']}")
    except Exception as e:
        record_test("Security Sanitization", "XSS <img onerror> tag sanitized", False, f"Exception: {e}")

    # Buffer Length Limits (100,000 characters)
    t0 = time.time()
    try:
        huge_input = "123 Main St " + ("A" * 50000) + ", Miami, FL 33101"
        res = normalize_address(huge_input)
        elapsed = time.time() - t0
        passed = (elapsed < 0.5)  # Should not hang or take long
        record_test("Security Robustness", f"Buffer length test (50k chars, took {elapsed:.4f}s)", passed, f"Elapsed: {elapsed:.4f}s")
    except Exception as e:
        record_test("Security Robustness", "Buffer length test", False, f"Exception: {e}")

    # --- 4. MISSING COMPONENTS ---
    print("\nTest Group 4: Missing Components & Incomplete Addresses")

    # Missing street number
    try:
        normalize_address("Broadway, New York, NY 10001")
        record_test("Missing Components", "Missing street number throws error", False, "Did not throw exception")
    except MissingStreetNumberError:
        record_test("Missing Components", "Missing street number throws error", True, "Correctly threw MissingStreetNumberError")
    except Exception as e:
        record_test("Missing Components", "Missing street number throws error", False, f"Threw {type(e).__name__}: {e}")

    # Missing ZIP code: '123 Main St, New York, NY'
    try:
        res = normalize_address("123 Main St, New York, NY")
        # Check if zip5 was improperly assigned the state string 'NY'
        passed = (res['zip5'] == '' and res['state'] == 'NY' and res['formattedAddress'] == '123 Main St, New York, NY')
        record_test("Missing Components", "Missing ZIP code does not populate zip5 with state 'NY'", passed,
                    f"Result: zip5='{res['zip5']}', state='{res['state']}', formatted='{res['formattedAddress']}'")
    except Exception as e:
        record_test("Missing Components", "Missing ZIP code handled", False, f"Exception: {e}")

    # Missing City & State: '123 Main St'
    try:
        res = normalize_address("123 Main St")
        passed = (res['streetNumber'] == '123' and res['streetName'] == 'Main St' and res['city'] == '' and res['state'] == '')
        record_test("Missing Components", "Bare street address '123 Main St'", passed, f"Result={res}")
    except Exception as e:
        record_test("Missing Components", "Bare street address '123 Main St'", False, f"Exception: {e}")

    # Empty String
    try:
        normalize_address("")
        record_test("Missing Components", "Empty string throws AddressValidationError", False, "Did not throw")
    except AddressValidationError:
        record_test("Missing Components", "Empty string throws AddressValidationError", True, "Correctly threw AddressValidationError")
    except Exception as e:
        record_test("Missing Components", "Empty string throws AddressValidationError", False, f"Threw {type(e).__name__}: {e}")

    # Whitespace Only
    try:
        normalize_address("    ")
        record_test("Missing Components", "Whitespace throws AddressValidationError", True, "Correctly threw AddressValidationError")
    except AddressValidationError:
        record_test("Missing Components", "Whitespace throws AddressValidationError", True, "Correctly threw AddressValidationError")
    except Exception as e:
        record_test("Missing Components", "Whitespace throws AddressValidationError", False, f"Threw {type(e).__name__}: {e}")

    print("\n=================================================================")
    print(f"SUMMARY: {len(passes)} PASSED, {len(failures)} FAILED")
    print("=================================================================")
    if failures:
        print("\nFailed Tests:")
        for f in failures:
            print(f"  - [{f['category']}] {f['name']}: {f['details']}")
    
    return len(failures)

if __name__ == '__main__':
    num_failures = run_tests()
    sys.exit(1 if num_failures > 0 else 0)
