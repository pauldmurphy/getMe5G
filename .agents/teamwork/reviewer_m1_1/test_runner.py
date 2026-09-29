#!/usr/bin/env python3
"""
Independent Verification & Adversarial Stress-Test Suite for AddressNormalizer logic.
Re-implements the exact TS algorithms from src/lib/geocoding/normalizer.ts in Python
to verify compliance with tests/unit/geocoding/normalizer.test.ts and probe adversarial edge cases.
"""

import re
import sys

# 1. State Map
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
    'armed forces americas': 'AA', 'armed forces europe': 'AE', 'armed forces pacific': 'AP'
}

STREET_SUFFIX_MAP = {
    'avenue': 'Ave', 'ave': 'Ave', 'street': 'St', 'st': 'St', 'road': 'Rd', 'rd': 'Rd',
    'boulevard': 'Blvd', 'blvd': 'Blvd', 'drive': 'Dr', 'dr': 'Dr', 'lane': 'Ln', 'ln': 'Ln',
    'court': 'Ct', 'ct': 'Ct', 'circle': 'Cir', 'cir': 'Cir', 'parkway': 'Pkwy', 'pkwy': 'Pkwy',
    'highway': 'Hwy', 'hwy': 'Hwy', 'place': 'Pl', 'pl': 'Pl', 'terrace': 'Ter', 'ter': 'Ter',
    'way': 'Way', 'trail': 'Trl', 'trl': 'Trl'
}

DIRECTIONAL_MAP = {
    'north': 'N', 'n': 'N', 'south': 'S', 's': 'S', 'east': 'E', 'e': 'E', 'west': 'W', 'w': 'W',
    'northeast': 'NE', 'ne': 'NE', 'northwest': 'NW', 'nw': 'NW', 'southeast': 'SE', 'se': 'SE',
    'southwest': 'SW', 'sw': 'SW'
}

PO_BOX_REGEX = re.compile(r'\b(?:P(?:OST)?\.?\s*O(?:FFICE)?\.?\s*BOX|P\.?\s*O\.?\s*B(?:\.|\b)|POST\s+OFFICE\s+DRAWER|PBOX)\b', re.IGNORECASE)
UNIT_REGEX = re.compile(r'(?:,\s*)?\b(?:(APT|APARTMENT|SUITE|STE|UNIT|BLDG|BUILDING|FL|FLOOR|RM|ROOM|LOT|DEPT)\.?\s*([A-Za-z0-9\-#/]+)|#\s*([A-Za-z0-9\-]+))\b', re.IGNORECASE)
ZIP_REGEX = re.compile(r'\b(\d{5})(?:[-\s](\d{4}))?\b')
STREET_NUMBER_REGEX = re.compile(r'^([0-9]+(?:\s+1/[2-4])?|[0-9]+-[0-9]+|[A-Z][0-9]+[A-Z][0-9]+)\s+(.+)$', re.IGNORECASE)
RURAL_ROUTE_BOX_REGEX = re.compile(r'^(Route\s+\d+|RR\s+\d+|Rural\s+Route\s+\d+)\s+(Box\s+\d+)\b', re.IGNORECASE)

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
        return {'baseStreet': '', 'unitNumber': None}
    match = UNIT_REGEX.search(street_text)
    if not match:
        return {'baseStreet': street_text.strip(), 'unitNumber': None}
    
    if match.group(1) and match.group(2):
        raw_prefix = match.group(1).lower()
        prefix = match.group(1)[0].upper() + match.group(1)[1:].lower()
        if raw_prefix in ('fl', 'floor'):
            prefix = 'Fl'
        elif raw_prefix in ('ste', 'suite'):
            prefix = 'Suite'
        elif raw_prefix in ('apt', 'apartment'):
            prefix = 'Apt'
        elif raw_prefix == 'unit':
            prefix = 'Unit'
        unit_number = f"{prefix} {match.group(2)}"
    elif match.group(3):
        unit_number = f"#{match.group(3)}"
    else:
        unit_number = match.group(0).strip()
    
    base_street = UNIT_REGEX.sub('', street_text)
    base_street = re.sub(r',\s*$', '', base_street).strip()
    return {'baseStreet': base_street, 'unitNumber': unit_number}

def standardize_street_name(street_name: str) -> str:
    tokens = re.split(r'\s+', street_name.strip())
    normalized = []
    for i, token in enumerate(tokens):
        lower = re.sub(r'[.,]', '', token.lower())
        if (i == 0 or i == len(tokens) - 1) and lower in DIRECTIONAL_MAP:
            normalized.append(DIRECTIONAL_MAP[lower])
        elif lower in STREET_SUFFIX_MAP:
            normalized.append(STREET_SUFFIX_MAP[lower])
        else:
            normalized.append(token[:1].upper() + token[1:])
    return ' '.join(normalized)

def parse_zip(zip_input: str):
    if not zip_input:
        return {'zip5': '', 'zip4': None}
    match = ZIP_REGEX.search(zip_input.strip())
    if not match:
        digits = re.sub(r'\D', '', zip_input)
        if len(digits) >= 5:
            return {'zip5': digits[:5], 'zip4': digits[5:9] if len(digits) >= 9 else None}
        return {'zip5': zip_input.strip(), 'zip4': None}
    return {'zip5': match.group(1), 'zip4': match.group(2) if match.group(2) else None}

def validate_coordinates(lat, lng):
    if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
        raise ValueError(f"Invalid non-numeric coordinates: lat={lat}, lng={lng}")
    if not (17.5 <= lat <= 72.0 and -179.0 <= lng <= -64.0):
        raise ValueError(f"Out of bounds: ({lat}, {lng})")

def normalize_address(input_str: str, coords=None):
    if not input_str or not input_str.strip():
        raise ValueError('Please enter a valid street address.')
    
    cleaned = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', input_str, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"['\";]\s*(?:DROP|SELECT|INSERT|DELETE|UPDATE|ALTER|CREATE|EXEC|UNION)[\s\S]*?--", '', cleaned, flags=re.IGNORECASE).strip()
    
    if is_po_box(cleaned):
        raise ValueError(f"PO Box not supported: {cleaned}")
    
    lat = 38.897675
    lng = -77.03653
    if coords:
        validate_coordinates(coords['lat'], coords['lng'])
        lat = coords['lat']
        lng = coords['lng']
    
    segments = [re.sub(r'\s+', ' ', s.strip()) for s in cleaned.split(',') if s.strip()]
    if not segments:
        raise ValueError("Empty address segments")
    
    raw_street = segments[0]
    city = ''
    raw_state_zip = ''
    if len(segments) >= 3:
        city = segments[1]
        raw_state_zip = ' '.join(segments[2:])
    elif len(segments) == 2:
        raw_state_zip = segments[1]
    
    street_number = ''
    street_name = ''
    unit_number = None
    
    rural_match = RURAL_ROUTE_BOX_REGEX.match(raw_street)
    if rural_match:
        street_name = rural_match.group(1)
        street_number = rural_match.group(2)
    else:
        extracted = extract_unit_number(raw_street)
        raw_street = extracted['baseStreet']
        unit_number = extracted['unitNumber']
        
        num_match = STREET_NUMBER_REGEX.match(raw_street)
        if num_match:
            street_number = num_match.group(1)
            raw_street = num_match.group(2)
        else:
            raise ValueError(f"Missing street number in {input_str}")
        street_name = standardize_street_name(raw_street)
    
    state = ''
    zip5 = ''
    zip4 = None
    if raw_state_zip:
        pz = parse_zip(raw_state_zip)
        zip5 = pz['zip5']
        zip4 = pz['zip4']
        rem = ZIP_REGEX.sub('', raw_state_zip).strip()
        if rem:
            state = normalize_state(rem)
    
    if not city and len(segments) == 2:
        words = segments[1].split()
        if len(words) > 2:
            city = ' '.join(words[:-2])
            state = normalize_state(words[-2])
    
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
    }

# -----------------
# Run Test Suite
# -----------------
tests_passed = 0
tests_failed = 0

def assert_eq(actual, expected, desc):
    global tests_passed, tests_failed
    if actual == expected:
        tests_passed += 1
    else:
        tests_failed += 1
        print(f"[FAIL] {desc}: expected {expected!r}, got {actual!r}")

def assert_true(cond, desc):
    global tests_passed, tests_failed
    if cond:
        tests_passed += 1
    else:
        tests_failed += 1
        print(f"[FAIL] {desc}: expected True")

def assert_false(cond, desc):
    global tests_passed, tests_failed
    if not cond:
        tests_passed += 1
    else:
        tests_failed += 1
        print(f"[FAIL] {desc}: expected False")

def assert_raises(fn, expected_regex, desc):
    global tests_passed, tests_failed
    try:
        fn()
        tests_failed += 1
        print(f"[FAIL] {desc}: expected exception matching {expected_regex}")
    except Exception as e:
        if re.search(expected_regex, str(e), re.I):
            tests_passed += 1
        else:
            tests_failed += 1
            print(f"[FAIL] {desc}: exception {e} did not match {expected_regex}")

# Tier 1 tests
res = normalize_address('350 5th Ave, New York, NY 10118', {'lat': 40.7484, 'lng': -73.9857})
assert_eq(res['streetNumber'], '350', 'T1: streetNumber')
assert_true('5th Ave' in res['streetName'], 'T1: streetName contains 5th Ave')
assert_eq(res['city'], 'New York', 'T1: city')
assert_eq(res['state'], 'NY', 'T1: state')
assert_eq(res['zip5'], '10118', 'T1: zip5')
assert_eq(round(res['lat'], 4), 40.7484, 'T1: lat')
assert_eq(round(res['lng'], 4), -73.9857, 'T1: lng')

res = normalize_address('1600 Pennsylvania Avenue NW, Washington, DC 20500')
assert_eq(res['streetNumber'], '1600', 'T1 DC: streetNumber')
assert_true(bool(re.search(r'Pennsylvania (Avenue|Ave) NW', res['streetName'], re.I)), 'T1 DC: streetName')
assert_eq(res['city'], 'Washington', 'T1 DC: city')
assert_eq(res['state'], 'DC', 'T1 DC: state')
assert_eq(res['zip5'], '20500', 'T1 DC: zip5')

res = normalize_address('1600 Pennsylvania Ave NW, Washington, DC 20500-0003')
assert_eq(res['zip5'], '20500', 'T1 ZIP+4: zip5')
assert_eq(res['zip4'], '0003', 'T1 ZIP+4: zip4')

# State normalization
for full_name, code in [('California', 'CA'), ('california', 'CA'), ('New York', 'NY'), ('Texas', 'TX'), ('District of Columbia', 'DC'), ('Puerto Rico', 'PR'), ('IL', 'IL'), ('wy', 'WY'), ('FL', 'FL')]:
    assert_eq(normalize_state(full_name), code, f"State: {full_name} -> {code}")

# Unit extraction
u1 = extract_unit_number('742 Evergreen Terrace Apt 4B')
assert_true(bool(re.search(r'4B', u1['unitNumber'] or '', re.I)), 'Unit Apt 4B')
assert_eq(u1['baseStreet'], '742 Evergreen Terrace', 'Unit base 742 Evergreen Terrace')

u2 = extract_unit_number('450 7th Ave Suite 1501')
assert_true(bool(re.search(r'1501', u2['unitNumber'] or '', re.I)), 'Unit Suite 1501')
assert_eq(u2['baseStreet'], '450 7th Ave', 'Unit base 450 7th Ave')

u3 = extract_unit_number('100 Pine St #304')
assert_true(bool(re.search(r'304', u3['unitNumber'] or '', re.I)), 'Unit #304')
assert_eq(u3['baseStreet'], '100 Pine St', 'Unit base 100 Pine St')

u4 = extract_unit_number('123 Main St Unit 2')
assert_true(bool(re.search(r'2', u4['unitNumber'] or '', re.I)), 'Unit Unit 2')
assert_eq(u4['baseStreet'], '123 Main St', 'Unit base 123 Main St')

u5 = extract_unit_number('500 W Madison St Fl 2')
assert_true(bool(re.search(r'2', u5['unitNumber'] or '', re.I)), 'Unit Fl 2')
assert_eq(u5['baseStreet'], '500 W Madison St', 'Unit base 500 W Madison St')

u6 = extract_unit_number('456 Oak Rd')
assert_eq(u6['unitNumber'], None, 'Unit None')
assert_eq(u6['baseStreet'], '456 Oak Rd', 'Unit base 456 Oak Rd')

# PO Box
assert_true(is_po_box('PO Box 1234, Dallas, TX 75201'), 'isPoBox PO Box')
assert_true(is_po_box('po box 500'), 'isPoBox po box 500')
assert_true(is_po_box('P.O. Box 999, Atlanta, GA 30301'), 'isPoBox P.O. Box')
assert_true(is_po_box('P. O. Box 101, Chicago, IL 60601'), 'isPoBox P. O. Box')
assert_true(is_po_box('Post Office Box 42, Denver, CO 80201'), 'isPoBox Post Office Box')

assert_raises(lambda: normalize_address('PO Box 1234, Dallas, TX 75201'), r'PO Box', 'Reject PO Box')

assert_false(is_po_box('123 Boxwood Lane, Houston, TX 77001'), 'not isPoBox Boxwood')
assert_false(is_po_box('45 Post Office Rd, Annapolis, MD 21401'), 'not isPoBox Post Office Rd')
assert_false(is_po_box('800 Boxberry Court, Raleigh, NC 27601'), 'not isPoBox Boxberry')

# Edge cases & irregular addresses
res = normalize_address('123 1/2 Maple St, Seattle, WA 98101')
assert_eq(res['streetNumber'], '123 1/2', 'Fractional 123 1/2')
assert_true('Maple St' in res['streetName'], 'Fractional street')

res = normalize_address('N12W34560 Lake Dr, Delafield, WI 53018')
assert_eq(res['streetNumber'], 'N12W34560', 'Wisconsin grid streetNumber')
assert_eq(res['streetName'], 'Lake Dr', 'Wisconsin grid streetName')
assert_eq(res['state'], 'WI', 'Wisconsin grid state')

res = normalize_address('Route 1 Box 42, Big Piney, WY 83113')
assert_true('Route 1' in res['streetName'], 'Rural route name')
assert_eq(res['streetNumber'], 'Box 42', 'Rural route number')
assert_eq(res['city'], 'Big Piney', 'Rural route city')
assert_eq(res['state'], 'WY', 'Rural route state')
assert_eq(res['zip5'], '83113', 'Rural route zip5')

res = normalize_address('   350    5th   Ave ,   New   York  ,   NY    10118   ')
assert_eq(res['streetNumber'], '350', 'Whitespace number')
assert_eq(res['city'], 'New York', 'Whitespace city')
assert_eq(res['state'], 'NY', 'Whitespace state')
assert_eq(res['zip5'], '10118', 'Whitespace zip')

res = normalize_address("123 Main St'; DROP TABLE brands;--, Boston, MA 02108")
assert_eq(res['city'], 'Boston', 'SQLi city')
assert_eq(res['state'], 'MA', 'SQLi state')
assert_eq(res['zip5'], '02108', 'SQLi zip5')

res = normalize_address('<script>alert("xss")</script> 123 Main St, Miami, FL 33101')
assert_eq(res['streetNumber'], '123', 'XSS number')
assert_eq(res['city'], 'Miami', 'XSS city')
assert_eq(res['state'], 'FL', 'XSS state')

assert_raises(lambda: normalize_address(''), r'.+', 'Empty string throws')
assert_raises(lambda: normalize_address('    '), r'.+', 'Whitespace string throws')
assert_raises(lambda: normalize_address('Broadway, New York, NY 10001'), r'street number', 'Missing street number throws')

res = normalize_address('350 5th Ave, New York, NY 10118', {'lat': 40.7484, 'lng': -73.9857})
assert_true(18 < res['lat'] < 72, 'Coords lat bounds')
assert_true(-180 < res['lng'] < -65, 'Coords lng bounds')

print(f"\nRESULTS: {tests_passed} passed, {tests_failed} failed.")
if tests_failed > 0:
    sys.exit(1)
