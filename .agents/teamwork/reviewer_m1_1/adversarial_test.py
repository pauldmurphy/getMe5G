#!/usr/bin/env python3
"""
Adversarial Stress Test Suite for Geocoding & AddressNormalizer.
Explores boundary conditions, edge cases, injection attempts, and evasion attacks.
"""

import re

PO_BOX_REGEX = re.compile(r'\b(?:P(?:OST)?\.?\s*O(?:FFICE)?\.?\s*BOX|P\.?\s*O\.?\s*B(?:\.|\b)|POST\s+OFFICE\s+DRAWER|PBOX)\b', re.IGNORECASE)
UNIT_REGEX_ORIGINAL = re.compile(r'(?:,\s*)?\b(?:(APT|APARTMENT|SUITE|STE|UNIT|BLDG|BUILDING|FL|FLOOR|RM|ROOM|LOT|DEPT)\.?\s*([A-Za-z0-9\-#/]+)|#\s*([A-Za-z0-9\-]+))\b', re.IGNORECASE)
UNIT_REGEX_FIXED = re.compile(r'(?:,\s*)?(?:\b(APT|APARTMENT|SUITE|STE|UNIT|BLDG|BUILDING|FL|FLOOR|RM|ROOM|LOT|DEPT)\.?\s*([A-Za-z0-9\-#/]+)|#\s*([A-Za-z0-9\-]+))\b', re.IGNORECASE)

# 1. PO Box Evasion Tests
po_box_evasions = [
    ("PO Box 123", True),
    ("P.O. Box 123", True),
    ("p.o. box 123", True),
    ("Post Office Box 123", True),
    ("POB 123", True),
    ("P.O.B. 123", True),
    ("p.o.b 123", True),
    ("P.O.B. #123", True),
    ("POST OFFICE DRAWER 500", True),
    ("PBOX 404", True),
    ("123 Boxwood Lane", False),
    ("45 Post Office Rd", False),
    ("800 Boxberry Court", False),
    ("123 Box Canyon Rd", False),
    ("500 Little Box Rd", False),
    ("Box 42", False), # rural route box
]

print("=== PO BOX ADVERSARIAL STRESS TEST ===")
for text, expected in po_box_evasions:
    match = bool(PO_BOX_REGEX.search(text))
    status = "PASS" if match == expected else "FAIL"
    print(f"[{status}] {text!r}: match={match}, expected={expected}")

# 2. Unit Extraction Comparison
unit_samples = [
    "742 Evergreen Terrace Apt 4B",
    "450 7th Ave Suite 1501",
    "100 Pine St #304",
    "100 Pine St, #304",
    "100 Pine St # 304",
    "123 Main St Unit 2",
    "500 W Madison St Fl 2",
    "456 Oak Rd",
    "120 Broadway Dept 4",
    "200 Tech Way Bldg C",
    "55 Wall St Ste 2200",
    "101 Ocean Ave Floor 14",
    "77 Sunset Strip Penthouse B", # unhandled prefix?
]

print("\n=== UNIT EXTRACTION STRESS TEST (ORIGINAL vs FIXED) ===")
for sample in unit_samples:
    orig = UNIT_REGEX_ORIGINAL.search(sample)
    fixed = UNIT_REGEX_FIXED.search(sample)
    print(f"Sample: {sample}")
    print(f"  Original regex match: {orig.group(0) if orig else None}")
    print(f"  Fixed regex match:    {fixed.group(0) if fixed else None}")

# 3. Coordinate Bounding Box Test
print("\n=== COORDINATE BOUNDING BOX STRESS TEST ===")
coords_samples = [
    (40.7484, -73.9857, True, "NYC"),
    (21.3069, -157.8583, True, "Honolulu, HI"),
    (61.2181, -149.9003, True, "Anchorage, AK"),
    (18.2208, -66.5901, True, "Puerto Rico"),
    (51.5074, -0.1278, False, "London, UK"),
    (48.8566, 2.3522, False, "Paris, France"),
    (35.6762, 139.6503, False, "Tokyo, Japan"),
    (-33.8688, 151.2093, False, "Sydney, Australia"),
    (13.4443, 144.7937, False, "Guam (outside 17.5-72.0 or -179 to -64)"),
]

for lat, lng, expected_us, loc in coords_samples:
    is_us = 17.5 <= lat <= 72.0 and -179.0 <= lng <= -64.0
    status = "PASS" if is_us == expected_us else "FAIL"
    print(f"[{status}] {loc} ({lat}, {lng}): is_us={is_us}, expected={expected_us}")
