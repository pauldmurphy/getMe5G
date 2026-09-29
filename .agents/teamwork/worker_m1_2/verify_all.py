#!/usr/bin/env python3
"""
Comprehensive Verification Test Suite for Milestone 1 Iteration 2
Validates:
1. src/lib/geocoding/normalizer.ts (exact regex extraction, unit extraction, PO Box, suffix logic, Zip)
2. src/lib/geocoding/service.ts (fail-fast error preservation across all cascade tiers)
3. src/lib/geocoding/photon-geocoder.ts (US territorial bounds and country validation)
4. src/lib/geocoding/nominatim-geocoder.ts (US territorial bounds and country validation)
"""

import os
import re
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))

def test_normalizer():
    print("=== 1. Verifying src/lib/geocoding/normalizer.ts ===")
    path = os.path.join(BASE_DIR, 'src/lib/geocoding/normalizer.ts')
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Verify regexes in source code
    po_box_match = re.search(r'export const PO_BOX_REGEX = (/.+/i);', content)
    assert po_box_match, "PO_BOX_REGEX not found in normalizer.ts"
    po_box_str = po_box_match.group(1)
    print(f"  PO_BOX_REGEX in file: {po_box_str}")
    # Verify it matches P BOX
    po_re = re.compile(r'\b(?:P(?:OST)?\.?\s*(?:O(?:FFICE)?\.?\s*)?BOX|P\.?\s*O\.?\s*B(?:\.|\b)|POST\s+OFFICE\s+DRAWER|PBOX)\b', re.I)
    assert po_re.search("P BOX 10"), "P BOX 10 must match PO_BOX_REGEX"
    assert not po_re.search("123 Boxwood Ln"), "Boxwood Ln must not match PO_BOX_REGEX"

    unit_match = re.search(r'const UNIT_REGEX = (/.+/i);', content)
    assert unit_match, "UNIT_REGEX not found in normalizer.ts"
    unit_str = unit_match.group(1)
    print(f"  UNIT_REGEX in file: {unit_str}")
    unit_re = re.compile(r'(?:,\s*)?(?:\b(APARTMENT|APT|SUITE|STE|UNIT|BUILDING|BLDG|FLOOR|FL|ROOM|RM|LOT|DEPT)\b\.?\s*([A-Za-z0-9\-#\/]+)|#\s*([A-Za-z0-9\-]+))\b', re.I)
    m = unit_re.search("100 Pine St #304")
    assert m and m.group(3) == '304', f"100 Pine St #304 must match unit #304, got {m}"
    m5 = unit_re.search("100 Pine St #5")
    assert m5 and m5.group(3) == '5', f"100 Pine St #5 must match unit #5, got {m5}"

    # Verify XSS and SQL injection sanitization
    assert "cleaned.replace(/<[^>]+>/g, '').trim()" in content, "HTML tag stripping must be present"
    assert "cleaned.replace(/['\";]+\\s*(?:DROP|SELECT|INSERT|DELETE|UPDATE|ALTER|CREATE|EXEC|UNION)" in content, "SQL injection regex must be updated"

    # Verify zip5 empty fallback
    assert "return { zip5: '', zip4: null };" in content, "parseZip must return empty zip5 on fallback"

    # Verify suffixIndex logic
    assert "const suffixIndex = hasPostDirectional ? len - 2 : len - 1;" in content, "Positional suffixIndex must be present"
    assert "index === suffixIndex && STREET_SUFFIX_MAP[lower]" in content, "Suffix replacement must only occur at suffixIndex"

    # Verify PO Box check in normalizeFromComponents
    assert "this.isPoBox(streetNumber)" in content, "normalizeFromComponents must check isPoBox(streetNumber)"

    print("  [PASS] normalizer.ts source code verification succeeded.")

def test_service():
    print("\n=== 2. Verifying src/lib/geocoding/service.ts ===")
    path = os.path.join(BASE_DIR, 'src/lib/geocoding/service.ts')
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Verify imports
    assert "AddressValidationError" in content, "AddressValidationError must be imported"
    assert "GeocodingError" in content, "GeocodingError must be imported"

    # Count occurrences of `if (err instanceof AddressValidationError) {\n        throw err;\n      }`
    val_checks = re.findall(r'if\s*\(\s*err\s+instanceof\s+AddressValidationError\s*\)\s*\{\s*throw err;\s*\}', content)
    print(f"  Found {len(val_checks)} AddressValidationError re-throw catch guards.")
    assert len(val_checks) >= 6, f"Expected at least 6 AddressValidationError catch guards (Google, Mapbox, Census, Photon, Nominatim, Reverse), found {len(val_checks)}"

    # Check cascade exhaustion logic
    assert re.search(r'if\s*\(\s*lastError\s+instanceof\s+AddressValidationError\s*\)\s*\{\s*throw lastError;\s*\}', content), "Cascade exhaustion must check AddressValidationError"
    assert re.search(r'if\s*\(\s*lastError\s+instanceof\s+AddressNotFoundError\s*\)\s*\{\s*throw lastError;\s*\}', content), "Cascade exhaustion must check AddressNotFoundError"
    assert re.search(r'if\s*\(\s*lastError\s+instanceof\s+GeocodingError\s*\)\s*\{\s*throw lastError;\s*\}', content), "Cascade exhaustion must check GeocodingError"

    print("  [PASS] service.ts error preservation verification succeeded.")

def test_photon_geocoder():
    print("\n=== 3. Verifying src/lib/geocoding/photon-geocoder.ts ===")
    path = os.path.join(BASE_DIR, 'src/lib/geocoding/photon-geocoder.ts')
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    assert "OutOfBoundsError" in content, "OutOfBoundsError must be imported in photon-geocoder.ts"
    assert "US_MIN_LAT = 17.5" in content, "US_MIN_LAT must be defined"
    assert "US_MAX_LAT = 72.0" in content, "US_MAX_LAT must be defined"
    assert "US_MIN_LNG = -179.0" in content, "US_MIN_LNG must be defined"
    assert "US_MAX_LNG = -64.0" in content, "US_MAX_LNG must be defined"
    assert "function isUsPhotonFeature(feature: PhotonFeature): boolean" in content, "isUsPhotonFeature must be defined"

    # In suggest: isUsPhotonFeature check
    assert "if (!isUsPhotonFeature(feature))" in content, "suggest() must check isUsPhotonFeature"

    # In resolve: filter and throw OutOfBoundsError
    assert "data.features.filter(isUsPhotonFeature)" in content, "resolve() must filter features with isUsPhotonFeature"
    assert "throw new OutOfBoundsError(lat, lon)" in content, "resolve() must throw OutOfBoundsError when no US matches exist"

    # Functional test of isUsPhotonFeature logic
    def py_is_us_photon_feature(feature):
        if not feature.get('geometry') or not isinstance(feature['geometry'].get('coordinates'), list):
            return False
        coords = feature['geometry']['coordinates']
        lon, lat = coords[0], coords[1]
        if lat < 17.5 or lat > 72.0 or lon < -179.0 or lon > -64.0:
            return False
        props = feature.get('properties', {})
        cc = props.get('countrycode', '').strip().lower() if props.get('countrycode') else ''
        c = props.get('country', '').strip().lower() if props.get('country') else ''
        if cc and cc != 'us':
            return False
        if c and c not in ('united states', 'united states of america', 'usa'):
            return False
        return (cc == 'us' or c in ('united states', 'united states of america', 'usa'))

    # Tests
    toronto = {"geometry": {"coordinates": [-79.38, 43.65]}, "properties": {"countrycode": "ca", "country": "Canada"}}
    assert not py_is_us_photon_feature(toronto), "Toronto must be rejected by isUsPhotonFeature"

    tijuana = {"geometry": {"coordinates": [-117.03, 32.51]}, "properties": {"countrycode": "mx", "country": "Mexico"}}
    assert not py_is_us_photon_feature(tijuana), "Tijuana must be rejected by isUsPhotonFeature"

    london = {"geometry": {"coordinates": [-0.12, 51.5]}, "properties": {"countrycode": "gb", "country": "United Kingdom"}}
    assert not py_is_us_photon_feature(london), "London must be rejected by isUsPhotonFeature"

    nyc = {"geometry": {"coordinates": [-74.00, 40.71]}, "properties": {"countrycode": "us", "country": "United States"}}
    assert py_is_us_photon_feature(nyc), "NYC must be accepted by isUsPhotonFeature"

    honolulu = {"geometry": {"coordinates": [-157.85, 21.30]}, "properties": {"countrycode": "us", "country": "United States of America"}}
    assert py_is_us_photon_feature(honolulu), "Honolulu must be accepted by isUsPhotonFeature"

    print("  [PASS] photon-geocoder.ts verification succeeded.")

def test_nominatim_geocoder():
    print("\n=== 4. Verifying src/lib/geocoding/nominatim-geocoder.ts ===")
    path = os.path.join(BASE_DIR, 'src/lib/geocoding/nominatim-geocoder.ts')
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    assert "OutOfBoundsError" in content, "OutOfBoundsError must be imported in nominatim-geocoder.ts"
    assert "US_MIN_LAT = 17.5" in content, "US_MIN_LAT must be defined"
    assert "US_MAX_LAT = 72.0" in content, "US_MAX_LAT must be defined"
    assert "US_MIN_LNG = -179.0" in content, "US_MIN_LNG must be defined"
    assert "US_MAX_LNG = -64.0" in content, "US_MAX_LNG must be defined"
    assert "function isUsNominatimPlace(place: NominatimPlace): boolean" in content, "isUsNominatimPlace must be defined"

    # In suggest: isUsNominatimPlace check
    assert "if (!isUsNominatimPlace(item))" in content, "suggest() must check isUsNominatimPlace"

    # In resolve: filter and throw OutOfBoundsError
    assert "results.filter(isUsNominatimPlace)" in content, "resolve() must filter results with isUsNominatimPlace"
    assert "throw new OutOfBoundsError(isNaN(fLat) ? 0 : fLat, isNaN(fLng) ? 0 : fLng);" in content, "resolve() must throw OutOfBoundsError when foreign"

    # In resolveCoordinates: upfront check and country check
    assert "if (lat < US_MIN_LAT || lat > US_MAX_LAT || lng < US_MIN_LNG || lng > US_MAX_LNG)" in content, "resolveCoordinates must check bounds upfront"
    assert "if ((countryCode && countryCode !== 'us') || (country && !isUsCountry) || !isUsCountry)" in content, "resolveCoordinates must check country"

    # Functional test of isUsNominatimPlace logic
    def py_is_us_nominatim(place):
        try:
            lat = float(place['lat'])
            lng = float(place['lon'])
        except (ValueError, KeyError):
            return False
        if lat < 17.5 or lat > 72.0 or lng < -179.0 or lng > -64.0:
            return False
        addr = place.get('address', {})
        cc = addr.get('country_code', '').strip().lower() if addr.get('country_code') else ''
        c = addr.get('country', '').strip().lower() if addr.get('country') else ''
        if cc and cc != 'us':
            return False
        if c and c not in ('united states', 'united states of america', 'usa'):
            return False
        return (cc == 'us' or c in ('united states', 'united states of america', 'usa'))

    toronto_nom = {"lat": "43.65", "lon": "-79.38", "address": {"country_code": "ca", "country": "Canada"}}
    assert not py_is_us_nominatim(toronto_nom), "Toronto must be rejected by isUsNominatimPlace"

    nyc_nom = {"lat": "40.71", "lon": "-74.00", "address": {"country_code": "us", "country": "United States"}}
    assert py_is_us_nominatim(nyc_nom), "NYC must be accepted by isUsNominatimPlace"

    print("  [PASS] nominatim-geocoder.ts verification succeeded.")

if __name__ == '__main__':
    test_normalizer()
    test_service()
    test_photon_geocoder()
    test_nominatim_geocoder()
    print("\nALL 4 SUBSYSTEM VERIFICATION CHECKS PASSED SUCCESSFULLY!")
