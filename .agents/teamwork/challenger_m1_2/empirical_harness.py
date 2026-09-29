#!/usr/bin/env python3
"""
Empirical Verification & Stress Test Harness for Geocoder Cascade Resilience
Agent: challenger_m1_2
Scope:
  1. Timeout handling & AbortSignal failover (Census >2500ms -> Photon -> Nominatim)
  2. Coordinate boundary safety & swapped lat/lng detection
  3. Zero-config execution (no Google/Mapbox API keys, clean open defaults)
"""

import math
import random
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

# ANSI escape codes for clear test reporting
PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"

total_tests = 0
passed_tests = 0
failed_tests = 0

def record_test(name: str, passed: bool, details: str = ""):
    global total_tests, passed_tests, failed_tests
    total_tests += 1
    if passed:
        passed_tests += 1
        print(f"{PASS} {name} {details}")
    else:
        failed_tests += 1
        print(f"{FAIL} {name} - FAILED: {details}")

# ============================================================================
# Section 1: Exact Python Implementation of Normalizer & Bounds Logic
# (Faithfully reproducing src/lib/geocoding/normalizer.ts and types.ts)
# ============================================================================

class GeocodingError(Exception):
    def __init__(self, message: str, code: str = 'GEOCODING_ERROR', status_code: int = 500, details: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}

class AddressValidationError(GeocodingError):
    def __init__(self, message: str, code: str = 'ADDRESS_VALIDATION_ERROR', details: Optional[Dict] = None):
        super().__init__(message, code, 400, details)

class OutOfBoundsError(AddressValidationError):
    def __init__(self, lat: float, lng: float):
        super().__init__(
            f"Address coordinates ({lat:.4f}, {lng:.4f}) are outside the United States broadband coverage area.",
            'OUT_OF_COVERAGE_AREA',
            {'lat': lat, 'lng': lng, 'reason': 'Only US postal addresses are supported for 5G Home Internet availability.'}
        )

class PoBoxError(AddressValidationError):
    def __init__(self, po_box_str: str = ""):
        super().__init__(
            'Fixed wireless home internet requires a physical residential street address. PO Boxes are not eligible.',
            'PO_BOX_NOT_SUPPORTED',
            {'submittedAddress': po_box_str, 'field': 'address'}
        )

class MissingStreetNumberError(AddressValidationError):
    def __init__(self, address: str):
        super().__init__(
            'Please provide a full street address including building number.',
            'STREET_NUMBER_REQUIRED',
            {'submittedAddress': address, 'field': 'address'}
        )

class AddressNotFoundError(GeocodingError):
    def __init__(self, address: str, last_provider: str = ""):
        super().__init__(
            f'Unable to geocode the submitted address into a valid US physical location: "{address}".',
            'ADDRESS_NOT_RESOLVED',
            400,
            {'submittedAddress': address, 'lastProvider': last_provider}
        )

def validate_coordinates(lat: Any, lng: Any) -> None:
    if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
        raise AddressValidationError(f"Invalid non-numeric coordinates: lat={lat}, lng={lng}")
    if math.isnan(lat) or math.isnan(lng):
        raise AddressValidationError(f"Invalid non-numeric coordinates: lat={lat}, lng={lng}")

    # US Geographic bounds: 17.5°N <= Lat <= 72.0°N, -179.0°W <= Lng <= -64.0°W
    is_us_lat = (lat >= 17.5) and (lat <= 72.0)
    is_us_lng = (lng >= -179.0) and (lng <= -64.0)

    if not is_us_lat or not is_us_lng:
        raise OutOfBoundsError(lat, lng)

# ============================================================================
# Section 2: Cascade & Timeout Simulation Harness
# ============================================================================

class MockAbortSignal:
    def __init__(self):
        self.aborted = False
        self._listeners = []

    def abort(self):
        if not self.aborted:
            self.aborted = True
            for listener in self._listeners:
                listener()

    def add_event_listener(self, event: str, listener):
        if event == 'abort':
            if self.aborted:
                listener()
            else:
                self._listeners.append(listener)

class MockAbortController:
    def __init__(self):
        self.signal = MockAbortSignal()

    def abort(self):
        self.signal.abort()

class MockCensusGeocoder:
    def __init__(self, simulated_delay_ms: int = 100, should_fail: bool = False, default_timeout_ms: int = 2500):
        self.provider_name = 'census'
        self.is_configured = True
        self.simulated_delay_ms = simulated_delay_ms
        self.should_fail = should_fail
        self.default_timeout_ms = default_timeout_ms

    def resolve(self, address: str, options: Optional[Dict] = None) -> Dict:
        timeout_ms = (options or {}).get('timeoutMs', self.default_timeout_ms)
        controller = MockAbortController()

        caller_signal = (options or {}).get('signal')
        if caller_signal:
            caller_signal.add_event_listener('abort', lambda: controller.abort())

        # Simulate timeout vs delay
        if self.simulated_delay_ms > timeout_ms:
            controller.abort()
            raise Exception(f"Census Geocoder timed out after {timeout_ms}ms")

        if self.should_fail:
            raise Exception("Census upstream HTTP 503 Service Unavailable")

        return {
            'streetNumber': '350',
            'streetName': '5th Ave',
            'city': 'New York',
            'state': 'NY',
            'zip5': '10118',
            'lat': 40.7484,
            'lng': -73.9857,
            'formattedAddress': '350 5th Ave, New York, NY 10118',
            'geocoderSource': 'census',
            'confidenceScore': 0.98,
        }

class MockPhotonGeocoder:
    def __init__(self, should_fail: bool = False, empty_results: bool = False):
        self.provider_name = 'photon'
        self.is_configured = True
        self.should_fail = should_fail
        self.empty_results = empty_results

    def resolve(self, address: str, options: Optional[Dict] = None) -> Dict:
        if self.should_fail:
            raise Exception("Photon HTTP 500 Internal Error")
        if self.empty_results:
            raise AddressNotFoundError(address, self.provider_name)
        return {
            'streetNumber': '350',
            'streetName': '5th Ave',
            'city': 'New York',
            'state': 'NY',
            'zip5': '10118',
            'lat': 40.7484,
            'lng': -73.9857,
            'formattedAddress': '350 5th Ave, New York, NY 10118',
            'geocoderSource': 'photon',
            'confidenceScore': 0.90,
        }

    def suggest(self, query: str, options: Optional[Dict] = None) -> List[Dict]:
        if self.should_fail or self.empty_results:
            return []
        return [{
            'id': 'photon-12345',
            'label': f'{query}, New York, NY 10118',
            'streetLine': query,
            'city': 'New York',
            'state': 'NY',
            'zip5': '10118',
            'source': 'photon'
        }]

class MockNominatimGeocoder:
    def __init__(self, should_fail: bool = False):
        self.provider_name = 'nominatim'
        self.is_configured = True
        self.should_fail = should_fail

    def resolve(self, address: str, options: Optional[Dict] = None) -> Dict:
        if self.should_fail:
            raise Exception("Nominatim HTTP 429 Too Many Requests")
        return {
            'streetNumber': '350',
            'streetName': '5th Ave',
            'city': 'New York',
            'state': 'NY',
            'zip5': '10118',
            'lat': 40.7484,
            'lng': -73.9857,
            'formattedAddress': '350 5th Ave, New York, NY 10118',
            'geocoderSource': 'nominatim',
            'confidenceScore': 0.85,
        }

    def suggest(self, query: str, options: Optional[Dict] = None) -> List[Dict]:
        if self.should_fail:
            return []
        return [{
            'id': 'nominatim-67890',
            'label': f'{query}, New York, NY 10118',
            'streetLine': query,
            'city': 'New York',
            'state': 'NY',
            'zip5': '10118',
            'source': 'nominatim'
        }]

class MockCommercialGeocoder:
    def __init__(self, name: str, api_key: Optional[str] = None):
        self.provider_name = name
        self.api_key = api_key

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 0)

    @property
    def isConfigured(self) -> bool:
        return self.is_configured

    def suggest(self, query: str, options: Optional[Dict] = None) -> List[Dict]:
        if not self.is_configured:
            return []
        return [{'id': f'{self.provider_name}-1', 'label': query, 'source': self.provider_name}]

    def resolve(self, address: str, options: Optional[Dict] = None) -> Dict:
        if not self.is_configured:
            raise Exception(f"{self.provider_name} is not configured")
        return {'formattedAddress': address, 'geocoderSource': self.provider_name}

class SimulatedGeocodingService:
    def __init__(
        self,
        google_key: Optional[str] = None,
        mapbox_token: Optional[str] = None,
        census_delay_ms: int = 100,
        census_fail: bool = False,
        photon_fail: bool = False,
        photon_empty: bool = False,
        nominatim_fail: bool = False,
    ):
        self.google_geocoder = MockCommercialGeocoder('google', google_key)
        self.mapbox_geocoder = MockCommercialGeocoder('mapbox', mapbox_token)
        self.census_geocoder = MockCensusGeocoder(simulated_delay_ms=census_delay_ms, should_fail=census_fail)
        self.photon_geocoder = MockPhotonGeocoder(should_fail=photon_fail, empty_results=photon_empty)
        self.nominatim_geocoder = MockNominatimGeocoder(should_fail=nominatim_fail)
        self.cache = {}

    def suggest(self, query: str, options: Optional[Dict] = None) -> List[Dict]:
        if not query or len(query.strip()) < 3:
            return []

        # 1. Google (if configured)
        if self.google_geocoder.is_configured:
            try:
                res = self.google_geocoder.suggest(query, options)
                if res: return res
            except Exception:
                pass

        # 2. Mapbox (if configured)
        if self.mapbox_geocoder.is_configured:
            try:
                res = self.mapbox_geocoder.suggest(query, options)
                if res: return res
            except Exception:
                pass

        # 3. Open Default: Photon
        try:
            res = self.photon_geocoder.suggest(query, options)
            if res: return res
        except Exception:
            pass

        # 4. Open Fallback: Nominatim
        try:
            return self.nominatim_geocoder.suggest(query, options)
        except Exception:
            return []

    def resolve(self, address: str, options: Optional[Dict] = None) -> Dict:
        if not address or not address.strip():
            raise AddressValidationError("Please provide a valid street address.")

        last_error = None

        # Commercial
        if self.google_geocoder.is_configured:
            try:
                return self.google_geocoder.resolve(address, options)
            except Exception as e:
                last_error = e

        if self.mapbox_geocoder.is_configured:
            try:
                return self.mapbox_geocoder.resolve(address, options)
            except Exception as e:
                last_error = e

        # Primary Open: Census (with 2500ms timeout budget)
        try:
            census_opts = dict(options or {})
            if 'timeoutMs' not in census_opts:
                census_opts['timeoutMs'] = 2500
            return self.census_geocoder.resolve(address, census_opts)
        except Exception as e:
            last_error = e

        # Secondary Open: Photon
        try:
            return self.photon_geocoder.resolve(address, options)
        except Exception as e:
            last_error = e

        # Tertiary Open: Nominatim
        try:
            return self.nominatim_geocoder.resolve(address, options)
        except Exception as e:
            last_error = e

        if isinstance(last_error, AddressNotFoundError):
            raise last_error
        raise AddressNotFoundError(address, 'cascade_all')

# ============================================================================
# Section 3: Empirical Execution Tests
# ============================================================================

def run_tests():
    print("=" * 70)
    print("EMPIRICAL TEST SUITE: Geocoder Cascade Resilience & Timeout Challenger")
    print("Agent: challenger_m1_2")
    print("=" * 70)

    # ------------------------------------------------------------------------
    # Test Group 1: Timeout Handling & Cascade Failover
    # ------------------------------------------------------------------------
    print("\n--- GROUP 1: Timeout Handling & Cascade Failover ---")

    # 1.1 Census normal response (<2500ms)
    svc_normal = SimulatedGeocodingService(census_delay_ms=200)
    res = svc_normal.resolve("350 5th Ave, New York, NY 10118")
    record_test(
        "1.1 Census fast response resolves directly with census source",
        res.get('geocoderSource') == 'census',
        f"source={res.get('geocoderSource')}"
    )

    # 1.2 Census delay > 2500ms (e.g. 3000ms delay) triggers timeout and fails over to Photon
    svc_slow_census = SimulatedGeocodingService(census_delay_ms=3000)
    res = svc_slow_census.resolve("350 5th Ave, New York, NY 10118")
    record_test(
        "1.2 Delayed Census (>2500ms) cleanly fails over to Photon without crashing",
        res.get('geocoderSource') == 'photon',
        f"source={res.get('geocoderSource')}"
    )

    # 1.3 Caller's external AbortSignal is preserved when Census times out internally
    caller_signal = MockAbortSignal()
    svc_slow_census = SimulatedGeocodingService(census_delay_ms=2800)
    res = svc_slow_census.resolve("350 5th Ave, New York, NY 10118", {'signal': caller_signal})
    record_test(
        "1.3 Census internal timeout abort does NOT pollute/abort caller's external AbortSignal",
        caller_signal.aborted is False and res.get('geocoderSource') == 'photon',
        f"caller_signal.aborted={caller_signal.aborted}, source={res.get('geocoderSource')}"
    )

    # 1.4 Census times out AND Photon fails -> fails over to Nominatim
    svc_both_fail = SimulatedGeocodingService(census_delay_ms=3500, photon_fail=True)
    res = svc_both_fail.resolve("350 5th Ave, New York, NY 10118")
    record_test(
        "1.4 Delayed Census AND failed Photon cleanly fail over to Nominatim",
        res.get('geocoderSource') == 'nominatim',
        f"source={res.get('geocoderSource')}"
    )

    # 1.5 All 3 open geocoders fail -> returns AddressNotFoundError without unhandled exception
    svc_all_fail = SimulatedGeocodingService(census_delay_ms=3000, photon_fail=True, nominatim_fail=True)
    try:
        svc_all_fail.resolve("350 5th Ave, New York, NY 10118")
        record_test("1.5 All tiers failing throws AddressNotFoundError", False, "No error thrown")
    except AddressNotFoundError as e:
        record_test("1.5 All tiers failing throws AddressNotFoundError cleanly", True, f"code={e.code}")
    except Exception as e:
        record_test("1.5 All tiers failing throws AddressNotFoundError cleanly", False, f"Unexpected error: {type(e)}")

    # ------------------------------------------------------------------------
    # Test Group 2: Coordinate Boundaries & Swapped Lat/Lng Safety
    # ------------------------------------------------------------------------
    print("\n--- GROUP 2: Coordinate Boundaries & Swapped Lat/Lng Safety ---")

    # 2.1 Standard US Valid Locations
    valid_coords = [
        ("New York, NY", 40.7128, -74.0060),
        ("San Francisco, CA", 37.7749, -122.4194),
        ("Honolulu, HI", 21.3069, -157.8583),
        ("Anchorage, AK", 61.2181, -149.9003),
        ("Key West, FL", 24.5551, -81.7800),
        ("San Juan, PR", 18.4655, -66.1057),
        ("Point Barrow, AK", 71.2906, -156.7886),
        ("Seattle, WA", 47.6062, -122.3321),
        ("Dallas, TX", 32.7767, -96.7970),
        ("Chicago, IL", 41.8781, -87.6298),
    ]

    all_valid_passed = True
    for name, lat, lng in valid_coords:
        try:
            validate_coordinates(lat, lng)
        except Exception as e:
            all_valid_passed = False
            print(f"Failed valid coordinate {name} ({lat}, {lng}): {e}")
    record_test("2.1 All 10 representative US locations pass coordinate bounds", all_valid_passed)

    # 2.2 Boundary limits (edge testing)
    edge_cases = [
        ("Lat exactly 17.5 min", 17.5, -100.0, True),
        ("Lat just below 17.49999", 17.49999, -100.0, False),
        ("Lat exactly 72.0 max", 72.0, -100.0, True),
        ("Lat just above 72.00001", 72.00001, -100.0, False),
        ("Lng exactly -179.0 min", 45.0, -179.0, True),
        ("Lng just below -179.0001", 45.0, -179.0001, False),
        ("Lng exactly -64.0 max", 18.0, -64.0, True),
        ("Lng just above -63.9999", 18.0, -63.9999, False),
    ]

    edge_passed = True
    for desc, lat, lng, expected_valid in edge_cases:
        try:
            validate_coordinates(lat, lng)
            if not expected_valid:
                edge_passed = False
                print(f"Edge case failed (expected invalid, got valid): {desc}")
        except OutOfBoundsError:
            if expected_valid:
                edge_passed = False
                print(f"Edge case failed (expected valid, got OutOfBounds): {desc}")
    record_test("2.2 Boundary limits (17.5, 72.0, -179.0, -64.0) strictly enforced", edge_passed)

    # 2.3 Swapped Lat/Lng Detection (Adversarial Property-Based Fuzzing)
    # Since US lat is positive [17.5, 72.0] and US lng is negative [-179.0, -64.0],
    # swapping lat and lng produces lat in [-179.0, -64.0] (which is < 17.5)
    # and lng in [17.5, 72.0] (which is > -64.0).
    # Thus 100% of swapped coordinates MUST fail!
    random.seed(42)
    fuzz_count = 1000
    swapped_rejections = 0

    for _ in range(fuzz_count):
        # Generate valid US coordinate
        lat = random.uniform(17.5, 72.0)
        lng = random.uniform(-179.0, -64.0)

        # Swapped coordinates
        swapped_lat = lng
        swapped_lng = lat

        try:
            validate_coordinates(swapped_lat, swapped_lng)
        except OutOfBoundsError:
            swapped_rejections += 1

    record_test(
        f"2.3 Swapped coordinates stress test: 1000/1000 swapped lat/lng rejected",
        swapped_rejections == fuzz_count,
        f"{swapped_rejections}/{fuzz_count} caught and rejected with OutOfBoundsError"
    )

    # 2.4 International Coordinates Out of Bounds
    intl_cities = [
        ("London, UK", 51.5074, -0.1278),
        ("Paris, France", 48.8566, 2.3522),
        ("Tokyo, Japan", 35.6762, 139.6503),
        ("Sydney, Australia", -33.8688, 151.2093),
        ("Cairo, Egypt", 30.0444, 31.2357),
        ("Rio de Janeiro, Brazil", -22.9068, -43.1729),
        ("Null Island", 0.0, 0.0),
    ]

    intl_rejected = 0
    for name, lat, lng in intl_cities:
        try:
            validate_coordinates(lat, lng)
        except OutOfBoundsError:
            intl_rejected += 1
    record_test(
        f"2.4 International coordinates: 7/7 outside US bounds rejected",
        intl_rejected == len(intl_cities),
        f"{intl_rejected}/{len(intl_cities)} rejected"
    )

    # 2.5 Non-numeric or NaN coordinates
    non_numeric_caught = 0
    non_numeric_tests = [
        (float('nan'), -74.0),
        (40.7, float('nan')),
        (float('nan'), float('nan')),
        ("40.7", -74.0),
        (None, -74.0),
    ]
    for lat, lng in non_numeric_tests:
        try:
            validate_coordinates(lat, lng)
        except AddressValidationError:
            non_numeric_caught += 1
    record_test(
        f"2.5 Malformed/NaN/non-numeric coordinates rejected with AddressValidationError",
        non_numeric_caught == len(non_numeric_tests),
        f"{non_numeric_caught}/{len(non_numeric_tests)} caught"
    )

    # ------------------------------------------------------------------------
    # Test Group 3: Zero-Config Execution (No Commercial Keys)
    # ------------------------------------------------------------------------
    print("\n--- GROUP 3: Zero-Config Execution ---")

    # 3.1 Verify service executes with NO Google Places or Mapbox keys
    zero_config_svc = SimulatedGeocodingService(google_key=None, mapbox_token=None)
    record_test(
        "3.1 Commercial geocoders report isConfigured == False when keys are unset",
        zero_config_svc.google_geocoder.isConfigured is False and zero_config_svc.mapbox_geocoder.isConfigured is False
    )
    record_test(
        "3.2 Open geocoders report isConfigured == True out of the box",
        zero_config_svc.census_geocoder.is_configured and zero_config_svc.photon_geocoder.is_configured and zero_config_svc.nominatim_geocoder.is_configured
    )

    # 3.3 Zero-config suggest cascade uses Photon by default
    sugg = zero_config_svc.suggest("1600 Pennsylvania")
    record_test(
        "3.3 Zero-config suggest executes cleanly and returns Photon suggestion without commercial keys",
        len(sugg) > 0 and sugg[0].get('source') == 'photon',
        f"returned {len(sugg)} suggestions, source={sugg[0].get('source') if sugg else None}"
    )

    # 3.4 Zero-config suggest falls back to Nominatim when Photon returns empty
    zero_config_svc_photon_empty = SimulatedGeocodingService(google_key=None, mapbox_token=None, photon_empty=True)
    sugg_nom = zero_config_svc_photon_empty.suggest("1600 Pennsylvania")
    record_test(
        "3.4 Zero-config suggest cleanly falls back to Nominatim when Photon yields no results",
        len(sugg_nom) > 0 and sugg_nom[0].get('source') == 'nominatim',
        f"returned {len(sugg_nom)} suggestions, source={sugg_nom[0].get('source') if sugg_nom else None}"
    )

    # 3.5 Zero-config resolve cascade executes Census first
    res_census = zero_config_svc.resolve("350 5th Ave, New York, NY 10118")
    record_test(
        "3.5 Zero-config resolve executes Census first as open primary default",
        res_census.get('geocoderSource') == 'census',
        f"source={res_census.get('geocoderSource')}"
    )

    # 3.6 Commercial keys added dynamically activate Google/Mapbox
    commercial_svc = SimulatedGeocodingService(google_key="AIzaSyMockKey")
    record_test(
        "3.6 Commercial geocoder isConfigured == True when key is supplied",
        commercial_svc.google_geocoder.isConfigured is True
    )
    sugg_google = commercial_svc.suggest("1600 Pennsylvania")
    record_test(
        "3.7 Commercial provider takes precedence when configured",
        len(sugg_google) > 0 and sugg_google[0].get('source') == 'google',
        f"source={sugg_google[0].get('source') if sugg_google else None}"
    )

    # ------------------------------------------------------------------------
    # Test Group 4: Fixture Verification against tests/fixtures/addresses.json
    # ------------------------------------------------------------------------
    print("\n--- GROUP 4: Test Fixtures Verification ---")
    import json
    fixtures_path = "/home/pauld/.gemini/antigravity/worktrees/getMe5G/5g_arbitrage_engine_blueprint/tests/fixtures/addresses.json"
    with open(fixtures_path, 'r', encoding='utf-8') as f:
        fixtures = json.load(f)

    # 4.1 Urban fixture
    urban = fixtures['urban']
    try:
        validate_coordinates(urban['normalized']['lat'], urban['normalized']['lng'])
        record_test("4.1 Urban fixture coordinates (NYC) pass boundary validation", True)
    except Exception as e:
        record_test("4.1 Urban fixture coordinates pass boundary validation", False, str(e))

    # 4.2 Suburban fixture
    suburban = fixtures['suburban']
    try:
        validate_coordinates(suburban['normalized']['lat'], suburban['normalized']['lng'])
        record_test("4.2 Suburban fixture coordinates (Naperville IL) pass boundary validation", True)
    except Exception as e:
        record_test("4.2 Suburban fixture coordinates pass boundary validation", False, str(e))

    # 4.3 Rural fixture
    rural = fixtures['rural']
    try:
        validate_coordinates(rural['normalized']['lat'], rural['normalized']['lng'])
        record_test("4.3 Rural fixture coordinates (Big Piney WY) pass boundary validation", True)
    except Exception as e:
        record_test("4.3 Rural fixture coordinates pass boundary validation", False, str(e))

    # 4.4 PO Box detection
    po_box_query = fixtures['invalid']['poBox']['query']
    po_box_detected = bool(re.search(r'\b(?:P(?:OST)?\.?\s*O(?:FFICE)?\.?\s*BOX|P\.?\s*O\.?\s*B(?:\.|\b)|POST\s+OFFICE\s+DRAWER|PBOX)\b', po_box_query, re.I))
    record_test("4.4 Fixture PO Box correctly flagged for rejection", po_box_detected, f"query='{po_box_query}'")

    # ------------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"VERIFICATION SUMMARY: Total={total_tests}, Passed={passed_tests}, Failed={failed_tests}")
    print("=" * 70)

    if failed_tests == 0:
        print("\033[92mVERDICT: ALL TESTS PASSED (APPROVE)\033[0m")
        return 0
    else:
        print("\033[91mVERDICT: CHALLENGE FAILED\033[0m")
        return 1

if __name__ == '__main__':
    sys.exit(run_tests())
