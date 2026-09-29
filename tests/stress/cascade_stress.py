#!/usr/bin/env python3
"""
Empirical Cascade Stress Test Suite
Verifies:
1. Foreign addresses (Toronto, Montreal, Vancouver, London, Paris, etc.) -> OutOfBoundsError / Rejection.
2. Fail-fast error propagation: PO Box and missing street number abort immediately without calling subsequent cascade tiers.
3. Cascade error preservation: GeocodingError, AddressNotFoundError, GeocoderTimeoutError propagation on cascade exhaustion.
4. Reverse geocoding bounds enforcement and country verification.
5. Autocomplete suggestion filtering for foreign addresses and PO Boxes.
6. Boundary conditions & adversarial edge cases (NaN, 0,0, missing properties, malformed geometry).
7. TypeScript source code AST / structural verification.
"""

import os
import re
import sys
import time
import math

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
SRC_DIR = os.path.join(BASE_DIR, 'src/lib/geocoding')

# ============================================================================
# Core Type & Error Definitions (Mirrored from src/lib/geocoding/types.ts)
# ============================================================================

class GeocodingError(Exception):
    def __init__(self, message: str, code: str = 'GEOCODING_ERROR', status_code: int = 500, details=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}

class AddressValidationError(GeocodingError):
    def __init__(self, message: str, code: str = 'ADDRESS_VALIDATION_ERROR', details=None):
        super().__init__(message, code, 400, details)

class PoBoxError(AddressValidationError):
    def __init__(self, po_box_str: str = ''):
        super().__init__(
            'Fixed wireless home internet requires a physical residential street address. PO Boxes are not eligible.',
            'PO_BOX_NOT_SUPPORTED',
            {'submittedAddress': po_box_str, 'field': 'address'}
        )

class MissingStreetNumberError(AddressValidationError):
    def __init__(self, address: str = ''):
        super().__init__(
            'Please provide a full street address including building number.',
            'STREET_NUMBER_REQUIRED',
            {'submittedAddress': address, 'field': 'address'}
        )

class AddressNotFoundError(GeocodingError):
    def __init__(self, address: str, last_provider: str = ''):
        super().__init__(
            f'Unable to geocode the submitted address into a valid US physical location: "{address}".',
            'ADDRESS_NOT_RESOLVED',
            400,
            {'submittedAddress': address, 'lastProvider': last_provider}
        )

class OutOfBoundsError(AddressValidationError):
    def __init__(self, lat: float, lng: float):
        super().__init__(
            f'Address coordinates ({lat:.4f}, {lng:.4f}) are outside the United States broadband coverage area.',
            'OUT_OF_COVERAGE_AREA',
            {'lat': lat, 'lng': lng, 'reason': 'Only US postal addresses are supported for 5G Home Internet availability.'}
        )

class GeocoderTimeoutError(GeocodingError):
    def __init__(self, message: str = 'Upstream geocoding providers timed out. Please retry shortly.', details=None):
        super().__init__(message, 'GEOCODER_UPSTREAM_TIMEOUT', 504, details)

# ============================================================================
# Logic Implementations (Mirrored from source TypeScript files)
# ============================================================================

US_MIN_LAT = 17.5
US_MAX_LAT = 72.0
US_MIN_LNG = -179.0
US_MAX_LNG = -64.0

PO_BOX_REGEX = re.compile(
    r'\b(?:P(?:OST)?\.?\s*(?:O(?:FFICE)?\.?\s*)?BOX|P\.?\s*O\.?\s*B(?:\.|\b)|POST\s+OFFICE\s+DRAWER|PBOX)\b',
    re.IGNORECASE
)

def is_po_box(address: str) -> bool:
    if not address:
        return False
    return bool(PO_BOX_REGEX.search(address))

def assert_not_po_box(address: str):
    if is_po_box(address):
        raise PoBoxError(address)

def validate_coordinates(lat: float, lng: float):
    if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)) or math.isnan(lat) or math.isnan(lng):
        raise AddressValidationError(f"Invalid non-numeric coordinates: lat={lat}, lng={lng}")
    if not (US_MIN_LAT <= lat <= US_MAX_LAT and US_MIN_LNG <= lng <= US_MAX_LNG):
        raise OutOfBoundsError(lat, lng)

def is_us_photon_feature(feature: dict) -> bool:
    if not feature or not isinstance(feature, dict):
        return False
    geometry = feature.get('geometry')
    if not geometry or not isinstance(geometry, dict):
        return False
    coords = geometry.get('coordinates')
    if not isinstance(coords, list) or len(coords) < 2:
        return False
    lon, lat = coords[0], coords[1]
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or math.isnan(lat) or math.isnan(lon):
        return False

    # 1. Territorial bounding box check
    if lat < US_MIN_LAT or lat > US_MAX_LAT or lon < US_MIN_LNG or lon > US_MAX_LNG:
        return False

    # 2. Country metadata checks
    props = feature.get('properties') or {}
    country_code = props.get('countrycode', '').strip().lower() if props.get('countrycode') else ''
    country = props.get('country', '').strip().lower() if props.get('country') else ''

    if country_code and country_code != 'us':
        return False
    if country and country not in ('united states', 'united states of america', 'usa'):
        return False

    return (country_code == 'us' or country in ('united states', 'united states of america', 'usa'))

def is_us_nominatim_place(place: dict) -> bool:
    if not place or not isinstance(place, dict):
        return False
    try:
        lat = float(place.get('lat', 'nan'))
        lng = float(place.get('lon', 'nan'))
    except (ValueError, TypeError):
        return False

    if math.isnan(lat) or math.isnan(lng):
        return False

    # 1. Territorial bounding box check
    if lat < US_MIN_LAT or lat > US_MAX_LAT or lng < US_MIN_LNG or lng > US_MAX_LNG:
        return False

    # 2. Country metadata checks
    addr = place.get('address') or {}
    country_code = addr.get('country_code', '').strip().lower() if addr.get('country_code') else ''
    country = addr.get('country', '').strip().lower() if addr.get('country') else ''

    if country_code and country_code != 'us':
        return False
    if country and country not in ('united states', 'united states of america', 'usa'):
        return False

    return (country_code == 'us' or country in ('united states', 'united states of america', 'usa'))

# ============================================================================
# Cascade Service Implementation with Invocation Tracking
# ============================================================================

class MockGeocoder:
    def __init__(self, name: str, is_configured: bool = True):
        self.name = name
        self.is_configured = is_configured
        self.resolve_calls = 0
        self.suggest_calls = 0
        self.resolve_coords_calls = 0
        self.resolve_handler = None
        self.suggest_handler = None
        self.reverse_handler = None

    def resolve(self, address: str, options=None):
        self.resolve_calls += 1
        if self.resolve_handler:
            return self.resolve_handler(address, options)
        raise AddressNotFoundError(address, self.name)

    def suggest(self, query: str, options=None):
        self.suggest_calls += 1
        if self.suggest_handler:
            return self.suggest_handler(query, options)
        return []

    def resolve_coordinates(self, lat: float, lng: float, options=None):
        self.resolve_coords_calls += 1
        if self.reverse_handler:
            return self.reverse_handler(lat, lng, options)
        raise AddressNotFoundError(f"Coordinates ({lat}, {lng})", self.name)

class TrackedGeocodingService:
    def __init__(self):
        self.google = MockGeocoder('google', is_configured=False)
        self.mapbox = MockGeocoder('mapbox', is_configured=False)
        self.census = MockGeocoder('census', is_configured=True)
        self.photon = MockGeocoder('photon', is_configured=True)
        self.nominatim = MockGeocoder('nominatim', is_configured=True)
        self.cache = {}

    def get_cache_key(self, address: str) -> str:
        return re.sub(r'\s+', ' ', address.strip().lower())

    def suggest(self, query: str, options=None):
        if not query or len(query.strip()) < 3:
            return []
        if is_po_box(query):
            return []

        if self.google.is_configured:
            try:
                res = self.google.suggest(query, options)
                if res: return res
            except Exception:
                pass

        if self.mapbox.is_configured:
            try:
                res = self.mapbox.suggest(query, options)
                if res: return res
            except Exception:
                pass

        try:
            res = self.photon.suggest(query, options)
            if res: return res
        except Exception:
            pass

        try:
            return self.nominatim.suggest(query, options)
        except Exception:
            return []

    def resolve(self, address: str, options=None):
        if not address or not address.strip():
            raise AddressValidationError('Please provide a valid street address.')

        # Step 1: Pre-validation - reject PO Boxes immediately
        assert_not_po_box(address)

        cache_key = self.get_cache_key(address)
        if not options or not options.get('fresh'):
            cached = self.cache.get(cache_key)
            if cached and (time.time() - cached['timestamp'] < 3600):
                return cached['address']

        last_error = None

        # Step 2: Commercial Providers
        if self.google.is_configured:
            try:
                result = self.google.resolve(address, options)
                self.cache[cache_key] = {'address': result, 'timestamp': time.time()}
                return result
            except Exception as err:
                if isinstance(err, AddressValidationError):
                    raise err
                last_error = err

        if self.mapbox.is_configured:
            try:
                result = self.mapbox.resolve(address, options)
                self.cache[cache_key] = {'address': result, 'timestamp': time.time()}
                return result
            except Exception as err:
                if isinstance(err, AddressValidationError):
                    raise err
                last_error = err

        # Step 3: Primary Open Provider (Census)
        try:
            result = self.census.resolve(address, options)
            self.cache[cache_key] = {'address': result, 'timestamp': time.time()}
            return result
        except Exception as err:
            if isinstance(err, AddressValidationError):
                raise err
            last_error = err

        # Step 4: Secondary Open Provider (Photon)
        try:
            result = self.photon.resolve(address, options)
            self.cache[cache_key] = {'address': result, 'timestamp': time.time()}
            return result
        except Exception as err:
            if isinstance(err, AddressValidationError):
                raise err
            last_error = err

        # Step 5: Tertiary Open Provider (Nominatim)
        try:
            result = self.nominatim.resolve(address, options)
            self.cache[cache_key] = {'address': result, 'timestamp': time.time()}
            return result
        except Exception as err:
            if isinstance(err, AddressValidationError):
                raise err
            last_error = err

        # Cascade Exhaustion
        if isinstance(last_error, AddressValidationError):
            raise last_error
        if isinstance(last_error, AddressNotFoundError):
            raise last_error
        if isinstance(last_error, GeocodingError):
            raise last_error
        raise AddressNotFoundError(address, 'cascade_all')

    def resolve_coordinates(self, lat: float, lng: float, options=None):
        validate_coordinates(lat, lng)
        try:
            return self.nominatim.resolve_coordinates(lat, lng, options)
        except Exception as err:
            if isinstance(err, AddressValidationError):
                raise err
            raise AddressNotFoundError(f"Coordinates ({lat}, {lng})", 'nominatim')

# ============================================================================
# Test Runner & Reporting
# ============================================================================

def run_cascade_stress_suite():
    passes = []
    failures = []

    def record(group: str, test_name: str, passed: bool, details: str = ''):
        item = {'group': group, 'name': test_name, 'passed': passed, 'details': details}
        if passed:
            passes.append(item)
            print(f"  [PASS] {test_name}")
        else:
            failures.append(item)
            print(f"  [FAIL] {test_name} -> {details}")

    print("================================================================================")
    print("EMPIRICAL CHALLENGER: CASCADE ERROR PRESERVATION & TERRITORIAL BOUNDS TEST SUITE")
    print("================================================================================\n")

    # --------------------------------------------------------------------------
    # Group 1: Territorial Bounds & Sovereignty Isolation Logic
    # --------------------------------------------------------------------------
    print("--- Group 1: Territorial Bounds & Sovereignty Isolation Logic ---")

    test_locations = [
        # Canadian cities within US bbox (Lat: [17.5, 72.0], Lng: [-179.0, -64.0])
        ("Toronto, ON", {"lon": -79.3832, "lat": 43.6532, "countrycode": "ca", "country": "Canada"}, False),
        ("Montreal, QC", {"lon": -73.5673, "lat": 45.5017, "countrycode": "ca", "country": "Canada"}, False),
        ("Vancouver, BC", {"lon": -123.1207, "lat": 49.2827, "countrycode": "ca", "country": "Canada"}, False),
        ("Ottawa, ON", {"lon": -75.6972, "lat": 45.4215, "countrycode": "ca", "country": "Canada"}, False),
        ("Calgary, AB", {"lon": -114.0719, "lat": 51.0447, "countrycode": "ca", "country": "Canada"}, False),
        ("Windsor, ON (border)", {"lon": -83.0364, "lat": 42.3149, "countrycode": "ca", "country": "Canada"}, False),
        
        # Mexican border cities within US bbox
        ("Tijuana, Mexico", {"lon": -117.0382, "lat": 32.5149, "countrycode": "mx", "country": "Mexico"}, False),
        ("Ciudad Juarez, Mexico", {"lon": -106.4245, "lat": 31.6904, "countrycode": "mx", "country": "Mexico"}, False),
        ("Mexicali, Mexico", {"lon": -115.4673, "lat": 32.6519, "countrycode": "mx", "country": "Mexico"}, False),
        
        # European / Transatlantic cities (Outside US bbox longitude)
        ("London, UK", {"lon": -0.1278, "lat": 51.5074, "countrycode": "gb", "country": "United Kingdom"}, False),
        ("Paris, France", {"lon": 2.3522, "lat": 48.8566, "countrycode": "fr", "country": "France"}, False),
        ("Berlin, Germany", {"lon": 13.4050, "lat": 52.5200, "countrycode": "de", "country": "Germany"}, False),
        ("Madrid, Spain", {"lon": -3.7038, "lat": 40.4168, "countrycode": "es", "country": "Spain"}, False),
        
        # Asia / Pacific cities
        ("Tokyo, Japan", {"lon": 139.6503, "lat": 35.6762, "countrycode": "jp", "country": "Japan"}, False),
        ("Sydney, Australia", {"lon": 151.2093, "lat": -33.8688, "countrycode": "au", "country": "Australia"}, False),
        
        # Valid US Locations
        ("New York, NY", {"lon": -74.0060, "lat": 40.7128, "countrycode": "us", "country": "United States"}, True),
        ("Los Angeles, CA", {"lon": -118.2437, "lat": 34.0522, "countrycode": "us", "country": "United States of America"}, True),
        ("Chicago, IL", {"lon": -87.6298, "lat": 41.8781, "countrycode": "us", "country": "USA"}, True),
        ("Houston, TX", {"lon": -95.3698, "lat": 29.7604, "countrycode": "us", "country": "United States"}, True),
        ("Anchorage, AK", {"lon": -149.9003, "lat": 61.2181, "countrycode": "us", "country": "United States"}, True),
        ("Honolulu, HI", {"lon": -157.8583, "lat": 21.3069, "countrycode": "us", "country": "United States"}, True),
        ("San Juan, PR", {"lon": -66.1057, "lat": 18.4655, "countrycode": "us", "country": "United States"}, True),
        ("Key West, FL", {"lon": -81.7799, "lat": 24.5551, "countrycode": "us", "country": "United States"}, True),
        ("St. Thomas, VI", {"lon": -64.9307, "lat": 18.3419, "countrycode": "us", "country": "United States"}, True),
        
        # Bounding box extremes
        ("Extreme SW (17.5, -179.0)", {"lon": -179.0, "lat": 17.5, "countrycode": "us", "country": "United States"}, True),
        ("Extreme NE (72.0, -64.0)", {"lon": -64.0, "lat": 72.0, "countrycode": "us", "country": "United States"}, True),
        ("Just below min lat (17.49)", {"lon": -100.0, "lat": 17.49, "countrycode": "us", "country": "United States"}, False),
        ("Just above max lat (72.01)", {"lon": -100.0, "lat": 72.01, "countrycode": "us", "country": "United States"}, False),
        ("Just below min lng (-179.01)", {"lon": -179.01, "lat": 40.0, "countrycode": "us", "country": "United States"}, False),
        ("Just above max lng (-63.99)", {"lon": -63.99, "lat": 40.0, "countrycode": "us", "country": "United States"}, False),
        
        # Ambiguous / Missing metadata
        ("Within US bbox, no country info", {"lon": -100.0, "lat": 40.0, "countrycode": "", "country": ""}, False),
        ("Contradictory (us code, Canada name)", {"lon": -100.0, "lat": 40.0, "countrycode": "us", "country": "Canada"}, False),
        ("Contradictory (ca code, USA name)", {"lon": -100.0, "lat": 40.0, "countrycode": "ca", "country": "USA"}, False),
    ]

    for name, loc, expected in test_locations:
        # Test Photon feature format
        photon_feat = {
            "geometry": {"coordinates": [loc["lon"], loc["lat"]]},
            "properties": {"countrycode": loc["countrycode"], "country": loc["country"]}
        }
        res_photon = is_us_photon_feature(photon_feat)
        record("Territorial Bounds", f"Photon isUsPhotonFeature: {name}", res_photon == expected,
               f"Expected={expected}, Actual={res_photon}")

        # Test Nominatim place format
        nom_place = {
            "lat": str(loc["lat"]),
            "lon": str(loc["lon"]),
            "address": {"country_code": loc["countrycode"], "country": loc["country"]}
        }
        res_nom = is_us_nominatim_place(nom_place)
        record("Territorial Bounds", f"Nominatim isUsNominatimPlace: {name}", res_nom == expected,
               f"Expected={expected}, Actual={res_nom}")

    # --------------------------------------------------------------------------
    # Group 2: Fail-Fast Error Propagation (PO Box & Missing Street Number)
    # --------------------------------------------------------------------------
    print("\n--- Group 2: Fail-Fast Error Propagation (PO Box & Missing Street Number) ---")

    po_box_samples = [
        "PO Box 123, Dallas, TX 75201",
        "P.O. Box 456, New York, NY 10001",
        "P BOX 10, Atlanta, GA 30301",
        "Post Office Box 789, Chicago, IL 60601",
        "Post Office Drawer 99, Miami, FL 33101",
        "P.O.B. 555, Seattle, WA 98101",
        "POB 222, Denver, CO 80201",
        "PBOX 333, Phoenix, AZ 85001",
        "P.O. Box 999-A, Boston, MA 02108",
        "p. o. box 777, Austin, TX 78701",
        "po box 888, San Jose, CA 95101",
    ]

    for po_input in po_box_samples:
        svc = TrackedGeocodingService()
        threw_pobox = False
        try:
            svc.resolve(po_input)
        except PoBoxError:
            threw_pobox = True
        except Exception as e:
            threw_pobox = False

        total_calls = (svc.google.resolve_calls + svc.mapbox.resolve_calls +
                       svc.census.resolve_calls + svc.photon.resolve_calls + svc.nominatim.resolve_calls)
        passed = (threw_pobox and total_calls == 0)
        record("Fail-Fast PO Box", f"Zero cascade tiers on '{po_input}'", passed,
               f"threw_pobox={threw_pobox}, total_calls={total_calls}")

    # Empty / Whitespace strings
    for empty_input in ["", "   ", "\t\n  "]:
        svc = TrackedGeocodingService()
        threw_val = False
        try:
            svc.resolve(empty_input)
        except AddressValidationError:
            threw_val = True
        except Exception:
            threw_val = False

        total_calls = (svc.census.resolve_calls + svc.photon.resolve_calls + svc.nominatim.resolve_calls)
        passed = (threw_val and total_calls == 0)
        record("Fail-Fast Empty", f"Zero cascade tiers on whitespace '{repr(empty_input)}'", passed,
               f"threw_val={threw_val}, total_calls={total_calls}")

    # Missing Street Number Scenario A:
    # Census resolves street without house number -> throws MissingStreetNumberError
    # Verification: Cascade MUST immediately abort. Photon and Nominatim MUST NOT be called!
    svc_missing_census = TrackedGeocodingService()
    svc_missing_census.census.resolve_handler = lambda addr, opts: (_ for _ in ()).throw(
        MissingStreetNumberError(addr)
    )
    threw_missing = False
    try:
        svc_missing_census.resolve("Main Street, Seattle, WA 98101")
    except MissingStreetNumberError:
        threw_missing = True
    except Exception:
        threw_missing = False

    passed = (threw_missing and
              svc_missing_census.census.resolve_calls == 1 and
              svc_missing_census.photon.resolve_calls == 0 and
              svc_missing_census.nominatim.resolve_calls == 0)
    record("Fail-Fast Missing Street", "Census MissingStreetNumberError halts cascade immediately (Photon=0, Nominatim=0)",
           passed,
           f"threw={threw_missing}, census={svc_missing_census.census.resolve_calls}, photon={svc_missing_census.photon.resolve_calls}, nom={svc_missing_census.nominatim.resolve_calls}")

    # Missing Street Number Scenario B:
    # Census returns 0 matches (AddressNotFoundError) -> falls back to Photon.
    # Photon resolves street without house number -> throws MissingStreetNumberError.
    # Verification: Cascade MUST immediately abort. Nominatim MUST NOT be called!
    svc_missing_photon = TrackedGeocodingService()
    svc_missing_photon.census.resolve_handler = lambda addr, opts: (_ for _ in ()).throw(
        AddressNotFoundError(addr, 'census')
    )
    svc_missing_photon.photon.resolve_handler = lambda addr, opts: (_ for _ in ()).throw(
        MissingStreetNumberError(addr)
    )
    threw_missing = False
    try:
        svc_missing_photon.resolve("Broadway, New York, NY")
    except MissingStreetNumberError:
        threw_missing = True
    except Exception:
        threw_missing = False

    passed = (threw_missing and
              svc_missing_photon.census.resolve_calls == 1 and
              svc_missing_photon.photon.resolve_calls == 1 and
              svc_missing_photon.nominatim.resolve_calls == 0)
    record("Fail-Fast Missing Street", "Photon MissingStreetNumberError halts cascade immediately (Nominatim=0)",
           passed,
           f"threw={threw_missing}, census={svc_missing_photon.census.resolve_calls}, photon={svc_missing_photon.photon.resolve_calls}, nom={svc_missing_photon.nominatim.resolve_calls}")

    # --------------------------------------------------------------------------
    # Group 3: Foreign Address Cascade Resolution & OutOfBounds Rejection
    # --------------------------------------------------------------------------
    print("\n--- Group 3: Foreign Address Cascade Resolution & OutOfBounds Rejection ---")

    foreign_scenarios = [
        ("Toronto, ON", "100 Queen St W, Toronto, ON M5H 2N2", 43.6532, -79.3832, "ca", "Canada"),
        ("Montreal, QC", "1000 Rue de la Gauchetiere O, Montreal, QC H3B 4W5", 45.5017, -73.5673, "ca", "Canada"),
        ("Vancouver, BC", "800 Robson St, Vancouver, BC V6Z 3B7", 49.2827, -123.1207, "ca", "Canada"),
        ("Calgary, AB", "200 8 Ave SW, Calgary, AB T2P 1B5", 51.0447, -114.0719, "ca", "Canada"),
        ("Tijuana, Mexico", "Paseo de los Heroes 100, Tijuana, BC 22010", 32.5149, -117.0382, "mx", "Mexico"),
        ("London, UK", "10 Downing Street, London SW1A 2AA", 51.5034, -0.1276, "gb", "United Kingdom"),
        ("Paris, France", "Place Charles de Gaulle, 75008 Paris", 48.8738, 2.2950, "fr", "France"),
        ("Tokyo, Japan", "1-1 Chiyoda, Chiyoda-ku, Tokyo 100-8111", 35.6852, 139.7528, "jp", "Japan"),
        ("Sydney, Australia", "Bennelong Point, Sydney NSW 2000", -33.8568, 151.2153, "au", "Australia"),
    ]

    for city_name, addr, lat, lng, cc, country in foreign_scenarios:
        # Simulate realistic cascade:
        # Census returns 0 matches (US only database) -> AddressNotFoundError
        # Photon returns raw candidate matching the query with foreign country tags
        svc = TrackedGeocodingService()
        svc.census.resolve_handler = lambda a, o: (_ for _ in ()).throw(AddressNotFoundError(a, 'census'))

        # Photon feature filtering logic simulation
        def photon_resolve_mock(a, o, f_lat=lat, f_lng=lng, f_cc=cc, f_c=country):
            feat = {
                "geometry": {"coordinates": [f_lng, f_lat]},
                "properties": {"countrycode": f_cc, "country": f_c, "housenumber": "100", "street": "Street"}
            }
            if not is_us_photon_feature(feat):
                raise OutOfBoundsError(f_lat, f_lng)
            return {"formattedAddress": a, "lat": f_lat, "lng": f_lng}

        svc.photon.resolve_handler = photon_resolve_mock

        threw_oob = False
        caught_lat = None
        caught_lng = None
        try:
            svc.resolve(addr)
        except OutOfBoundsError as e:
            threw_oob = True
            caught_lat = e.details.get('lat')
            caught_lng = e.details.get('lng')
        except Exception as e:
            threw_oob = False

        # Verification: OutOfBoundsError MUST be thrown AND Nominatim tier MUST NOT be called!
        passed = (threw_oob and
                  caught_lat == lat and
                  caught_lng == lng and
                  svc.census.resolve_calls == 1 and
                  svc.photon.resolve_calls == 1 and
                  svc.nominatim.resolve_calls == 0)
        record("Foreign Address OutOfBounds", f"Foreign address '{city_name}' throws OutOfBoundsError without calling Nominatim",
               passed,
               f"threw_oob={threw_oob}, nom_calls={svc.nominatim.resolve_calls}, lat={caught_lat}, lng={caught_lng}")

    # Case: European address with zero matches across tiers -> rejected via AddressNotFoundError
    svc_london_exhausted = TrackedGeocodingService()
    svc_london_exhausted.census.resolve_handler = lambda a, o: (_ for _ in ()).throw(AddressNotFoundError(a, 'census'))
    svc_london_exhausted.photon.resolve_handler = lambda a, o: (_ for _ in ()).throw(AddressNotFoundError(a, 'photon'))
    svc_london_exhausted.nominatim.resolve_handler = lambda a, o: (_ for _ in ()).throw(AddressNotFoundError(a, 'nominatim'))

    threw_rejection = False
    try:
        svc_london_exhausted.resolve("10 Downing Street, London, UK")
    except AddressNotFoundError:
        threw_rejection = True
    except Exception:
        threw_rejection = False

    passed = (threw_rejection and
              svc_london_exhausted.census.resolve_calls == 1 and
              svc_london_exhausted.photon.resolve_calls == 1 and
              svc_london_exhausted.nominatim.resolve_calls == 1)
    record("Foreign Address Rejection", "European address with zero matches across tiers rejected via AddressNotFoundError",
           passed, f"threw_rejection={threw_rejection}")

    # --------------------------------------------------------------------------
    # Group 4: Cascade Error Preservation (Fallback on Non-Validation Errors)
    # --------------------------------------------------------------------------
    print("\n--- Group 4: Cascade Error Preservation on Transient/Exhaustion Errors ---")

    # Transient error: Census times out -> Photon succeeds
    svc_timeout_fallback = TrackedGeocodingService()
    svc_timeout_fallback.census.resolve_handler = lambda a, o: (_ for _ in ()).throw(GeocoderTimeoutError("Census 2500ms timeout"))
    svc_timeout_fallback.photon.resolve_handler = lambda a, o: {
        "formattedAddress": "1600 Pennsylvania Ave NW, Washington, DC 20500",
        "lat": 38.8977,
        "lng": -77.0365
    }

    res = svc_timeout_fallback.resolve("1600 Pennsylvania Ave NW, Washington, DC 20500")
    passed = (res["lat"] == 38.8977 and
              svc_timeout_fallback.census.resolve_calls == 1 and
              svc_timeout_fallback.photon.resolve_calls == 1 and
              svc_timeout_fallback.nominatim.resolve_calls == 0)
    record("Cascade Resilience", "Census timeout gracefully falls back to Photon", passed,
           f"census_calls={svc_timeout_fallback.census.resolve_calls}, photon_calls={svc_timeout_fallback.photon.resolve_calls}")

    # Census and Photon fail with 500/timeout -> Nominatim succeeds
    svc_nom_fallback = TrackedGeocodingService()
    svc_nom_fallback.census.resolve_handler = lambda a, o: (_ for _ in ()).throw(GeocodingError("Census 500 Internal Error"))
    svc_nom_fallback.photon.resolve_handler = lambda a, o: (_ for _ in ()).throw(GeocoderTimeoutError("Photon timeout"))
    svc_nom_fallback.nominatim.resolve_handler = lambda a, o: {
        "formattedAddress": "350 5th Ave, New York, NY 10118",
        "lat": 40.7484,
        "lng": -73.9857
    }

    res2 = svc_nom_fallback.resolve("350 5th Ave, New York, NY 10118")
    passed = (res2["lat"] == 40.7484 and
              svc_nom_fallback.census.resolve_calls == 1 and
              svc_nom_fallback.photon.resolve_calls == 1 and
              svc_nom_fallback.nominatim.resolve_calls == 1)
    record("Cascade Resilience", "Census 500 and Photon timeout fall back to Nominatim", passed,
           f"all 3 tiers called in order")

    # Cascade exhaustion: all fail with timeouts -> GeocoderTimeoutError preserved
    svc_exhaust_timeout = TrackedGeocodingService()
    svc_exhaust_timeout.census.resolve_handler = lambda a, o: (_ for _ in ()).throw(GeocoderTimeoutError("Census timeout"))
    svc_exhaust_timeout.photon.resolve_handler = lambda a, o: (_ for _ in ()).throw(GeocoderTimeoutError("Photon timeout"))
    svc_exhaust_timeout.nominatim.resolve_handler = lambda a, o: (_ for _ in ()).throw(GeocoderTimeoutError("Nominatim timeout"))

    threw_timeout = False
    try:
        svc_exhaust_timeout.resolve("742 Evergreen Terrace, Springfield, OR")
    except GeocoderTimeoutError:
        threw_timeout = True
    except Exception:
        threw_timeout = False

    passed = (threw_timeout and svc_exhaust_timeout.nominatim.resolve_calls == 1)
    record("Cascade Preservation", "Cascade exhaustion preserves typed GeocoderTimeoutError", passed,
           f"threw_timeout={threw_timeout}")

    # --------------------------------------------------------------------------
    # Group 5: Reverse Geocoding (`resolveCoordinates`)
    # --------------------------------------------------------------------------
    print("\n--- Group 5: Reverse Geocoding (`resolveCoordinates`) ---")

    # 5a. Out of bounds upfront coordinates (London coords)
    svc_rev = TrackedGeocodingService()
    threw_rev_oob = False
    try:
        svc_rev.resolve_coordinates(51.5074, -0.1278)
    except OutOfBoundsError:
        threw_rev_oob = True
    except Exception:
        threw_rev_oob = False

    passed = (threw_rev_oob and svc_rev.nominatim.resolve_coords_calls == 0)
    record("Reverse Geocoding", "London coordinates throw OutOfBoundsError upfront without calling provider", passed,
           f"threw={threw_rev_oob}, nom_calls={svc_rev.nominatim.resolve_coords_calls}")

    # 5b. Out of bounds upfront coordinates (Sydney coords)
    threw_sydney = False
    try:
        svc_rev.resolve_coordinates(-33.8688, 151.2093)
    except OutOfBoundsError:
        threw_sydney = True
    except Exception:
        threw_sydney = False

    passed = (threw_sydney and svc_rev.nominatim.resolve_coords_calls == 0)
    record("Reverse Geocoding", "Sydney coordinates throw OutOfBoundsError upfront without calling provider", passed,
           f"threw={threw_sydney}")

    # 5c. Null Island (0.0, 0.0)
    threw_null_island = False
    try:
        svc_rev.resolve_coordinates(0.0, 0.0)
    except OutOfBoundsError:
        threw_null_island = True
    except Exception:
        threw_null_island = False
    passed = (threw_null_island and svc_rev.nominatim.resolve_coords_calls == 0)
    record("Reverse Geocoding", "Null Island (0.0, 0.0) throws OutOfBoundsError upfront", passed,
           f"threw={threw_null_island}")

    # 5d. Coordinates within bbox, but reverse response returns Canadian country code (Toronto)
    svc_rev_toronto = TrackedGeocodingService()
    def mock_toronto_reverse(lat, lng, opts):
        place = {"lat": str(lat), "lon": str(lng), "address": {"country_code": "ca", "country": "Canada"}}
        if not is_us_nominatim_place(place):
            raise OutOfBoundsError(lat, lng)
        return {"formattedAddress": "Toronto, ON", "lat": lat, "lng": lng}

    svc_rev_toronto.nominatim.reverse_handler = mock_toronto_reverse

    threw_toronto_rev = False
    try:
        svc_rev_toronto.resolve_coordinates(43.6532, -79.3832)
    except OutOfBoundsError:
        threw_toronto_rev = True
    except Exception:
        threw_toronto_rev = False

    passed = (threw_toronto_rev and svc_rev_toronto.nominatim.resolve_coords_calls == 1)
    record("Reverse Geocoding", "Toronto coordinates within bbox rejected by country verification in reverse lookup", passed,
           f"threw={threw_toronto_rev}, calls={svc_rev_toronto.nominatim.resolve_coords_calls}")

    # 5e. Valid US Coordinates (Empire State Building: 40.7484, -73.9857)
    svc_rev_nyc = TrackedGeocodingService()
    svc_rev_nyc.nominatim.reverse_handler = lambda lat, lng, opts: {
        "formattedAddress": "350 5th Ave, New York, NY 10118",
        "lat": lat,
        "lng": lng
    }
    nyc_res = svc_rev_nyc.resolve_coordinates(40.7484, -73.9857)
    passed = (nyc_res["lat"] == 40.7484 and svc_rev_nyc.nominatim.resolve_coords_calls == 1)
    record("Reverse Geocoding", "Valid US coordinates resolve successfully", passed, f"result={nyc_res['formattedAddress']}")

    # --------------------------------------------------------------------------
    # Group 6: Autocomplete Suggestion Filtering (`suggest`)
    # --------------------------------------------------------------------------
    print("\n--- Group 6: Autocomplete Suggestion Filtering (`suggest`) ---")

    # 6a. PO Box in suggest returns empty array immediately
    svc_sug = TrackedGeocodingService()
    sug_res = svc_sug.suggest("PO Box 123")
    passed = (sug_res == [] and svc_sug.photon.suggest_calls == 0 and svc_sug.nominatim.suggest_calls == 0)
    record("Autocomplete Filtering", "PO Box suggest returns empty array without executing tiers", passed,
           f"len={len(sug_res)}, photon_calls={svc_sug.photon.suggest_calls}")

    # 6b. Short query (< 3 chars) returns empty array immediately
    sug_short = svc_sug.suggest("12")
    passed = (sug_short == [] and svc_sug.photon.suggest_calls == 0)
    record("Autocomplete Filtering", "Short query (<3 chars) returns empty array", passed,
           f"len={len(sug_short)}")

    # 6c. Photon suggest filters out foreign candidates
    svc_sug_filter = TrackedGeocodingService()
    def mock_photon_suggest(query, opts):
        raw_candidates = [
            {"geometry": {"coordinates": [-79.38, 43.65]}, "properties": {"countrycode": "ca", "housenumber": "100", "street": "Queen St W", "city": "Toronto", "state": "ON"}},
            {"geometry": {"coordinates": [-74.00, 40.71]}, "properties": {"countrycode": "us", "housenumber": "100", "street": "Broadway", "city": "New York", "state": "NY"}},
            {"geometry": {"coordinates": [-117.03, 32.51]}, "properties": {"countrycode": "mx", "housenumber": "200", "street": "Revolucion", "city": "Tijuana", "state": "BC"}},
        ]
        filtered = []
        for feat in raw_candidates:
            if is_us_photon_feature(feat):
                p = feat["properties"]
                filtered.append({"label": f"{p['housenumber']} {p['street']}, {p['city']}, {p['state']}"})
        return filtered

    svc_sug_filter.photon.suggest_handler = mock_photon_suggest
    filtered_suggestions = svc_sug_filter.suggest("100 Main")
    passed = (len(filtered_suggestions) == 1 and "New York" in filtered_suggestions[0]["label"])
    record("Autocomplete Filtering", "Photon suggest filters out Canada and Mexico candidates, returning only US", passed,
           f"returned={filtered_suggestions}")

    # --------------------------------------------------------------------------
    # Group 7: Adversarial Inputs & Boundary Conditions
    # --------------------------------------------------------------------------
    print("\n--- Group 7: Adversarial Inputs & Boundary Conditions ---")

    # 7a. Non-numeric coordinates to validateCoordinates
    for bad_lat, bad_lng in [(float('nan'), -74.0), (40.7, float('nan')), ("40.7", -74.0), (None, None)]:
        threw_bad = False
        try:
            validate_coordinates(bad_lat, bad_lng)
        except AddressValidationError:
            threw_bad = True
        except Exception:
            threw_bad = False
        record("Adversarial Bounds", f"validateCoordinates rejects ({bad_lat}, {bad_lng})", threw_bad, f"threw={threw_bad}")

    # 7b. Malformed feature payloads to isUsPhotonFeature
    malformed_features = [
        ("None feature", None),
        ("Empty dict", {}),
        ("No geometry", {"properties": {"countrycode": "us"}}),
        ("Geometry not dict", {"geometry": "invalid", "properties": {"countrycode": "us"}}),
        ("Coordinates not list", {"geometry": {"coordinates": "invalid"}}),
        ("Coordinates empty", {"geometry": {"coordinates": []}}),
        ("Coordinates 1 element", {"geometry": {"coordinates": [-74.0]}}),
        ("Coordinates NaN", {"geometry": {"coordinates": [float('nan'), float('nan')]}}),
        ("Properties None", {"geometry": {"coordinates": [-74.0, 40.7]}, "properties": None}),
    ]
    for feat_name, feat_payload in malformed_features:
        res = is_us_photon_feature(feat_payload)
        record("Adversarial Bounds", f"isUsPhotonFeature safely handles {feat_name} without crashing", res is False, f"res={res}")

    # 7c. Malformed places to isUsNominatimPlace
    malformed_places = [
        ("None place", None),
        ("Empty dict", {}),
        ("Lat lon strings invalid", {"lat": "abc", "lon": "xyz"}),
        ("Lat lon NaN", {"lat": "nan", "lon": "nan"}),
        ("Address None", {"lat": "40.7", "lon": "-74.0", "address": None}),
    ]
    for place_name, place_payload in malformed_places:
        res = is_us_nominatim_place(place_payload)
        record("Adversarial Bounds", f"isUsNominatimPlace safely handles {place_name} without crashing", res is False, f"res={res}")

    # --------------------------------------------------------------------------
    # Group 8: Source Code AST & Implementation Pattern Verification
    # --------------------------------------------------------------------------
    print("\n--- Group 8: Source Code AST & Implementation Pattern Verification ---")

    service_ts_path = os.path.join(SRC_DIR, 'service.ts')
    with open(service_ts_path, 'r', encoding='utf-8') as f:
        service_ts = f.read()

    photon_ts_path = os.path.join(SRC_DIR, 'photon-geocoder.ts')
    with open(photon_ts_path, 'r', encoding='utf-8') as f:
        photon_ts = f.read()

    nom_ts_path = os.path.join(SRC_DIR, 'nominatim-geocoder.ts')
    with open(nom_ts_path, 'r', encoding='utf-8') as f:
        nom_ts = f.read()

    # 8a. All 5 cascade tiers in service.ts have AddressValidationError re-throw guards
    rethrow_pattern = r'if\s*\(\s*err\s+instanceof\s+AddressValidationError\s*\)\s*\{\s*throw err;\s*\}'
    tier_rethrows = re.findall(rethrow_pattern, service_ts)
    passed = len(tier_rethrows) >= 6
    record("Source Verification", f"service.ts contains {len(tier_rethrows)} AddressValidationError re-throw catch guards (>=6 required)",
           passed, f"count={len(tier_rethrows)}")

    # 8b. Cascade exhaustion preserves AddressValidationError, AddressNotFoundError, GeocodingError
    has_val_exhaust = bool(re.search(r'if\s*\(\s*lastError\s+instanceof\s+AddressValidationError\s*\)\s*\{\s*throw lastError;\s*\}', service_ts))
    has_notfound_exhaust = bool(re.search(r'if\s*\(\s*lastError\s+instanceof\s+AddressNotFoundError\s*\)\s*\{\s*throw lastError;\s*\}', service_ts))
    has_geo_exhaust = bool(re.search(r'if\s*\(\s*lastError\s+instanceof\s+GeocodingError\s*\)\s*\{\s*throw lastError;\s*\}', service_ts))
    passed = (has_val_exhaust and has_notfound_exhaust and has_geo_exhaust)
    record("Source Verification", "service.ts cascade exhaustion preserves typed errors", passed,
           f"val={has_val_exhaust}, notfound={has_notfound_exhaust}, geo={has_geo_exhaust}")

    # 8c. Photon imports and throws OutOfBoundsError
    has_photon_oob_import = "OutOfBoundsError" in photon_ts
    has_photon_oob_throw = "throw new OutOfBoundsError(lat, lon)" in photon_ts
    passed = (has_photon_oob_import and has_photon_oob_throw)
    record("Source Verification", "photon-geocoder.ts imports and throws OutOfBoundsError on foreign feature", passed,
           f"import={has_photon_oob_import}, throw={has_photon_oob_throw}")

    # 8d. Nominatim imports and throws OutOfBoundsError
    has_nom_oob_import = "OutOfBoundsError" in nom_ts
    has_nom_oob_throw = "throw new OutOfBoundsError" in nom_ts
    has_nom_countrycodes_us = "countrycodes: 'us'" in nom_ts
    passed = (has_nom_oob_import and has_nom_oob_throw and has_nom_countrycodes_us)
    record("Source Verification", "nominatim-geocoder.ts enforces countrycodes='us' and throws OutOfBoundsError", passed,
           f"import={has_nom_oob_import}, throw={has_nom_oob_throw}, countrycodes_us={has_nom_countrycodes_us}")

    # 8e. Upfront PO Box rejection before cache check in service.ts
    resolve_fn_match = re.search(r'public async resolve\(address: string[^{]+\{([\s\S]+?)const cacheKey', service_ts)
    passed = bool(resolve_fn_match and "AddressNormalizer.assertNotPoBox(address)" in resolve_fn_match.group(1))
    record("Source Verification", "service.ts invokes assertNotPoBox before checking cache", passed,
           f"present_before_cache={passed}")

    # --------------------------------------------------------------------------
    # Final Summary
    # --------------------------------------------------------------------------
    print("\n================================================================================")
    print(f"STRESS TEST SUITE RESULTS: {len(passes)} PASSED, {len(failures)} FAILED")
    print("================================================================================")

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(f"  - [{f['group']}] {f['name']}: {f['details']}")

    return len(failures)

if __name__ == '__main__':
    fail_count = run_cascade_stress_suite()
    sys.exit(1 if fail_count > 0 else 0)
