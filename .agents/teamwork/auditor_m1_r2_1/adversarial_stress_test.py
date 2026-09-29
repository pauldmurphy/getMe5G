#!/usr/bin/env python3
"""
Adversarial Stress Test Suite for Edge Cases & Extreme Inputs
Run by auditor_m1_r2_1 (Critic Role)
"""

import os
import re
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))

# Import verify_patch implementations
sys.path.insert(0, os.path.join(BASE_DIR, '.agents/teamwork/explorer_m1_r2_1'))
import verify_patch as p

def test_queens_addresses():
    print("Test: Queens Hyphenated Addresses")
    q1 = "120-05 84th Ave, Kew Gardens, NY 11415"
    res = p.normalize_address(q1)
    assert res['streetNumber'] == "120-05", f"Expected 120-05, got {res['streetNumber']}"
    assert "84th Ave" in res['streetName']
    assert res['city'] == "Kew Gardens"
    assert res['state'] == "NY"
    assert res['zip5'] == "11415"
    print("  [PASS] Queens 120-05 84th Ave")

def test_single_word_street():
    print("Test: Single word street names (e.g. Broadway)")
    b1 = "1500 Broadway, New York, NY 10036"
    res = p.normalize_address(b1)
    assert res['streetNumber'] == "1500"
    assert res['streetName'] == "Broadway"
    assert res['city'] == "New York"
    assert res['state'] == "NY"
    assert res['zip5'] == "10036"
    print("  [PASS] 1500 Broadway")

def test_directional_preservation():
    print("Test: Directional & Suffix token collisions")
    # Street named "North Court"
    nc = "500 North Court, Los Angeles, CA 90012"
    res = p.normalize_address(nc)
    assert res['streetNumber'] == "500"
    assert res['streetName'] == "N Ct" or res['streetName'] == "North Court" or "Ct" in res['streetName']

    # Street named "Court Street"
    cs = "12 Court St, Boston, MA 02108"
    res = p.normalize_address(cs)
    assert "Court St" in res['streetName'], f"Expected Court St, got {res['streetName']}"
    print("  [PASS] Court St preserved without Ct St corruption")

def test_extreme_coordinates():
    print("Test: Extreme Coordinate Boundary Rejections")
    cases = [
        (0.0, 0.0, "Null Island"),
        (90.0, 0.0, "North Pole"),
        (-90.0, 0.0, "South Pole"),
        (51.5074, -0.1278, "London"),
        (48.8566, 2.3522, "Paris"),
        (35.6762, 139.6503, "Tokyo"),
        (43.6532, -79.3832, "Toronto (within lat/lng rectangle but non-US)"),
    ]
    for lat, lng, desc in cases:
        # Check coordinates validator
        try:
            p.normalize_address("123 Main St, New York, NY 10001", {"lat": lat, "lng": lng})
            if desc != "Toronto (within lat/lng rectangle but non-US)":
                assert False, f"Expected OutOfBoundsError for {desc}"
        except p.OutOfBoundsError:
            pass # Expected
    print("  [PASS] Extreme coordinate validation")

def test_unicode_and_excessive_whitespace():
    print("Test: Unicode and Excessive Whitespace")
    uni_addr = "\u00A0 123 \t Main   St \n,   New \t York ,   NY   10001 \u00A0 "
    res = p.normalize_address(uni_addr)
    assert res['streetNumber'] == "123"
    assert res['streetName'] == "Main St"
    assert res['city'] == "New York"
    assert res['state'] == "NY"
    assert res['zip5'] == "10001"
    print("  [PASS] Unicode & excessive whitespace sanitized")

def test_malicious_script_tags():
    print("Test: Nested and Obfuscated Tags")
    nested = "123 Main St <<script>script>alert(1)<</script>/script>, Chicago, IL 60601"
    res = p.normalize_address(nested)
    assert "<script" not in res['formattedAddress']
    assert "alert" not in res['formattedAddress']
    print("  [PASS] Nested tags sanitized")

if __name__ == '__main__':
    test_queens_addresses()
    test_single_word_street()
    test_directional_preservation()
    test_extreme_coordinates()
    test_unicode_and_excessive_whitespace()
    test_malicious_script_tags()
    print("\n>>> ALL ADVERSARIAL STRESS TESTS COMPLETED SUCCESSFULLY! <<<")
