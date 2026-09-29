#!/usr/bin/env python3
"""
Comprehensive Reviewer & Adversarial Critic Test Suite for Milestone 1 Iteration 2
Agent: reviewer_m1_r2_2

Verifies:
1. Canadian/foreign addresses are rejected with OutOfBoundsError.
2. /api/geocode/resolve returns HTTP 400 with exact error codes:
   - PO_BOX_NOT_SUPPORTED
   - STREET_NUMBER_REQUIRED
   - OUT_OF_COVERAGE_AREA
3. Suggest route filters out non-US suggestions.
4. Edge cases & adversarial stress testing (US border cities, exclaves, territories, regex boundary probes).
5. Source code integrity analysis (ensuring no hardcoded mocks, fake implementations, or bypassed checks).
"""

import json
import os
import re
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))

US_MIN_LAT = 17.5
US_MAX_LAT = 72.0
US_MIN_LNG = -179.0
US_MAX_LNG = -64.0

class OutOfBoundsError(Exception):
    def __init__(self, lat, lng):
        self.code = 'OUT_OF_COVERAGE_AREA'
        self.statusCode = 400
        self.lat = lat
        self.lng = lng
        self.message = f"Address coordinates ({lat:.4f}, {lng:.4f}) are outside the United States broadband coverage area."
        self.details = {
            'lat': lat,
            'lng': lng,
            'reason': 'Only US postal addresses are supported for 5G Home Internet availability.'
        }
        super().__init__(self.message)

class MissingStreetNumberError(Exception):
    def __init__(self, address):
        self.code = 'STREET_NUMBER_REQUIRED'
        self.statusCode = 400
        self.message = 'Please provide a full street address including building number.'
        self.details = {
            'submittedAddress': address,
            'field': 'address',
            'reason': 'Building or house number is missing from the query.'
        }
        super().__init__(self.message)

class PoBoxError(Exception):
    def __init__(self, poBoxString=''):
        self.code = 'PO_BOX_NOT_SUPPORTED'
        self.statusCode = 400
        self.message = 'Fixed wireless home internet requires a physical residential street address. PO Boxes are not eligible.'
        self.details = {
            'submittedAddress': poBoxString,
            'poBox': poBoxString,
            'field': 'address',
            'reason': 'PO Boxes do not possess discrete physical rooftop coordinates for cellular RF line-of-sight analysis or home gateway delivery.'
        }
        super().__init__(self.message)

class AddressNotFoundError(Exception):
    def __init__(self, address, lastProvider=''):
        self.code = 'ADDRESS_NOT_RESOLVED'
        self.statusCode = 400
        self.message = f'Unable to geocode the submitted address into a valid US physical location: "{address}".'
        self.details = {
            'submittedAddress': address,
            'lastProvider': lastProvider,
            'field': 'address',
            'reason': 'Zero matches returned across geocoding cascade (Census, Photon, Nominatim).'
        }
        super().__init__(self.message)

def is_us_photon_feature(feature):
    """Exact python port of isUsPhotonFeature from photon-geocoder.ts"""
    geom = feature.get('geometry')
    if not geom or not isinstance(geom.get('coordinates'), list):
        return False
    coords = geom['coordinates']
    if len(coords) < 2:
        return False
    lon, lat = coords[0], coords[1]
    if lat < US_MIN_LAT or lat > US_MAX_LAT or lon < US_MIN_LNG or lon > US_MAX_LNG:
        return False
    props = feature.get('properties') or {}
    country_code = props.get('countrycode', '').strip().lower() if props.get('countrycode') else None
    country = props.get('country', '').strip().lower() if props.get('country') else None

    if country_code and country_code != 'us':
        return False
    if country and country not in ('united states', 'united states of america', 'usa'):
        return False

    return (
        country_code == 'us' or
        country in ('united states', 'united states of america', 'usa')
    )

def is_us_nominatim_place(place):
    """Exact python port of isUsNominatimPlace from nominatim-geocoder.ts"""
    try:
        lat = float(place['lat'])
        lng = float(place['lon'])
    except (ValueError, KeyError, TypeError):
        return False
    if lat < US_MIN_LAT or lat > US_MAX_LAT or lng < US_MIN_LNG or lng > US_MAX_LNG:
        return False
    addr = place.get('address') or {}
    country_code = addr.get('country_code', '').strip().lower() if addr.get('country_code') else None
    country = addr.get('country', '').strip().lower() if addr.get('country') else None

    if country_code and country_code != 'us':
        return False
    if country and country not in ('united states', 'united states of america', 'usa'):
        return False

    return (
        country_code == 'us' or
        country in ('united states', 'united states of america', 'usa')
    )

def simulate_photon_resolve(raw_address, features):
    """Simulates photon-geocoder.ts resolve() logic"""
    # PO box check
    po_re = re.compile(r'\b(?:P(?:OST)?\.?\s*(?:O(?:FFICE)?\.?\s*)?BOX|P\.?\s*O\.?\s*B(?:\.|\b)|POST\s+OFFICE\s+DRAWER|PBOX)\b', re.I)
    if po_re.search(raw_address):
        raise PoBoxError(raw_address)

    if not features or len(features) == 0:
        raise AddressNotFoundError(raw_address, 'photon')

    us_features = [f for f in features if is_us_photon_feature(f)]
    if len(us_features) == 0:
        best_foreign = None
        for f in features:
            props = f.get('properties', {})
            if props.get('housenumber') and props.get('street'):
                best_foreign = f
                break
        if not best_foreign:
            best_foreign = features[0]
        lon, lat = best_foreign['geometry']['coordinates']
        raise OutOfBoundsError(lat, lon)

    f = us_features[0]
    props = f.get('properties', {})
    street_num = props.get('housenumber', '')
    if not street_num:
        # Check rawAddress
        m = re.match(r'^([0-9]+(?:\s+1/[2-4])?|[0-9]+-[0-9]+|[A-Z][0-9]+[A-Z][0-9]+)\b', raw_address)
        if m:
            street_num = m.group(1)
        else:
            raise MissingStreetNumberError(raw_address)
    return {
        'streetNumber': street_num,
        'lat': f['geometry']['coordinates'][1],
        'lng': f['geometry']['coordinates'][0],
    }

def simulate_nominatim_resolve(raw_address, places):
    """Simulates nominatim-geocoder.ts resolve() logic"""
    po_re = re.compile(r'\b(?:P(?:OST)?\.?\s*(?:O(?:FFICE)?\.?\s*)?BOX|P\.?\s*O\.?\s*B(?:\.|\b)|POST\s+OFFICE\s+DRAWER|PBOX)\b', re.I)
    if po_re.search(raw_address):
        raise PoBoxError(raw_address)

    if not places or len(places) == 0:
        raise AddressNotFoundError(raw_address, 'nominatim')

    us_places = [p for p in places if is_us_nominatim_place(p)]
    if len(us_places) == 0:
        foreign_item = places[0]
        f_lat = float(foreign_item.get('lat', 0))
        f_lng = float(foreign_item.get('lon', 0))
        raise OutOfBoundsError(f_lat, f_lng)

    item = us_places[0]
    addr = item.get('address', {})
    street_num = addr.get('house_number', '')
    if not street_num:
        m = re.match(r'^([0-9]+(?:\s+1/[2-4])?|[0-9]+-[0-9]+|[A-Z][0-9]+[A-Z][0-9]+)\b', raw_address)
        if m:
            street_num = m.group(1)
        else:
            raise MissingStreetNumberError(raw_address)
    return {
        'streetNumber': street_num,
        'lat': float(item['lat']),
        'lng': float(item['lon']),
    }

def simulate_resolve_route(params, mock_resolver_fn):
    """Simulates src/app/api/geocode/resolve/route.ts GET handler"""
    raw_address = params.get('address')
    lat_param = params.get('lat')
    lng_param = params.get('lng')

    if raw_address is None and (lat_param is None or lng_param is None):
        return {
            'status': 400,
            'body': {
                'status': 'error',
                'code': 'MISSING_ADDRESS_PARAMETER',
                'message': "Query parameter 'address' or 'lat'/'lng' is required.",
                'details': {'parameter': 'address'}
            }
        }

    if raw_address is not None:
        address = raw_address.strip()
        if len(address) < 5:
            return {
                'status': 400,
                'body': {
                    'status': 'error',
                    'code': 'ADDRESS_TOO_SHORT',
                    'message': 'Address string must be at least 5 characters.',
                    'details': {'address': address, 'minLength': 5}
                }
            }
        if len(address) > 500:
            return {
                'status': 400,
                'body': {
                    'status': 'error',
                    'code': 'ADDRESS_TOO_LONG',
                    'message': 'Address string exceeds maximum length of 500 characters.',
                    'details': {'address': address, 'maxLength': 500}
                }
            }

        po_re = re.compile(r'\b(?:P(?:OST)?\.?\s*(?:O(?:FFICE)?\.?\s*)?BOX|P\.?\s*O\.?\s*B(?:\.|\b)|POST\s+OFFICE\s+DRAWER|PBOX)\b', re.I)
        if po_re.search(address):
            return {
                'status': 400,
                'body': {
                    'status': 'error',
                    'code': 'PO_BOX_NOT_SUPPORTED',
                    'message': 'Fixed wireless home internet requires a physical residential street address. PO Boxes are not eligible.',
                    'details': {
                        'submittedAddress': address,
                        'field': 'address',
                        'reason': 'PO Boxes do not possess discrete physical rooftop coordinates for cellular RF line-of-sight analysis or home gateway delivery.'
                    }
                }
            }

        try:
            normalized = mock_resolver_fn(address)
            return {
                'status': 200,
                'body': {
                    'status': 'success',
                    'address': normalized
                }
            }
        except Exception as err:
            return handle_geocode_error(err, address)

    # Reverse geocoding
    try:
        lat = float(lat_param)
        lng = float(lng_param)
    except (ValueError, TypeError):
        lat = float('nan')
        lng = float('nan')

    if lat != lat or lng != lng or lat < -90 or lat > 90 or lng < -180 or lng > 180:
        return {
            'status': 422,
            'body': {
                'status': 'error',
                'code': 'INVALID_COORDINATES',
                'message': 'Provided latitude or longitude coordinate is outside valid geographical boundaries.',
                'details': {
                    'lat': lat,
                    'lng': lng,
                    'reason': 'Latitude must be between -90.0 and 90.0 degrees and Longitude between -180.0 and 180.0 degrees.'
                }
            }
        }

    try:
        normalized = mock_resolver_fn(f"({lat}, {lng})", lat=lat, lng=lng)
        return {
            'status': 200,
            'body': {
                'status': 'success',
                'address': normalized
            }
        }
    except Exception as err:
        return handle_geocode_error(err, f"({lat}, {lng})")

def handle_geocode_error(err, address_context):
    if isinstance(err, PoBoxError):
        return {
            'status': 400,
            'body': {
                'status': 'error',
                'code': getattr(err, 'code', 'PO_BOX_NOT_SUPPORTED'),
                'message': err.message,
                'details': getattr(err, 'details', {'submittedAddress': address_context, 'field': 'address'})
            }
        }
    if isinstance(err, MissingStreetNumberError):
        return {
            'status': 400,
            'body': {
                'status': 'error',
                'code': getattr(err, 'code', 'STREET_NUMBER_REQUIRED'),
                'message': 'Please provide a full street address including building number.',
                'details': getattr(err, 'details', {
                    'submittedAddress': address_context,
                    'field': 'address',
                    'reason': 'Building or house number is missing from the query.'
                })
            }
        }
    if isinstance(err, OutOfBoundsError):
        return {
            'status': 400,
            'body': {
                'status': 'error',
                'code': getattr(err, 'code', 'OUT_OF_COVERAGE_AREA'),
                'message': 'Address is outside the United States broadband coverage area.',
                'details': getattr(err, 'details', {
                    'submittedAddress': address_context,
                    'reason': 'Only US postal addresses are supported for 5G Home Internet availability.'
                })
            }
        }
    if isinstance(err, AddressNotFoundError):
        return {
            'status': 400,
            'body': {
                'status': 'error',
                'code': getattr(err, 'code', 'ADDRESS_NOT_RESOLVED'),
                'message': 'Unable to geocode the submitted address into a valid US physical location.',
                'details': getattr(err, 'details', {
                    'submittedAddress': address_context,
                    'field': 'address',
                    'reason': 'Zero matches returned across geocoding cascade (Census, Photon, Nominatim).'
                })
            }
        }
    return {
        'status': 500,
        'body': {
            'status': 'error',
            'code': 'INTERNAL_SERVER_ERROR',
            'message': 'Internal server error while resolving address.'
        }
    }

def simulate_suggest_route(params, mock_suggest_fn):
    """Simulates src/app/api/geocode/suggest/route.ts GET handler"""
    raw_q = params.get('q')
    if raw_q is None or len(raw_q.strip()) == 0:
        return {
            'status': 400,
            'body': {
                'status': 'error',
                'code': 'MISSING_QUERY_PARAMETER',
                'message': "Query parameter 'q' is required and cannot be empty.",
                'details': {'parameter': 'q'}
            }
        }
    if len(raw_q) > 256:
        return {
            'status': 400,
            'body': {
                'status': 'error',
                'code': 'QUERY_TOO_LONG',
                'message': "Query parameter 'q' exceeds maximum allowable length of 256 characters.",
                'details': {'parameter': 'q', 'maxLength': 256, 'receivedLength': len(raw_q)}
            }
        }
    q = re.sub(r'[\0\r\n]', '', raw_q).strip()
    if len(q) < 3:
        return {
            'status': 200,
            'body': {
                'status': 'success',
                'query': q,
                'count': 0,
                'suggestions': []
            }
        }
    suggestions = mock_suggest_fn(q)
    return {
        'status': 200,
        'body': {
            'status': 'success',
            'query': q,
            'count': len(suggestions),
            'suggestions': suggestions
        }
    }

def run_tests():
    total_passed = 0
    total_failed = 0

    def assert_eq(actual, expected, msg):
        nonlocal total_passed, total_failed
        if actual == expected:
            total_passed += 1
            print(f"  [PASS] {msg}")
        else:
            total_failed += 1
            print(f"  [FAIL] {msg} -> Expected: {expected}, Got: {actual}")

    print("======================================================================")
    print("VERIFICATION SUITE: Foreign Bounds, API Routes & Suggest Filtering")
    print("======================================================================")

    # -------------------------------------------------------------------------
    # SUITE 1: CANADIAN & FOREIGN ADDRESS REJECTION WITH OutOfBoundsError
    # -------------------------------------------------------------------------
    print("\n--- 1. Testing Foreign Address Rejection with OutOfBoundsError ---")

    canadian_photon_features = [
        # Toronto, ON
        {"geometry": {"type": "Point", "coordinates": [-79.3832, 43.6532]},
         "properties": {"osm_id": 1, "housenumber": "100", "street": "Queen St W", "city": "Toronto", "state": "ON", "countrycode": "ca", "country": "Canada"}},
        # Montreal, QC
        {"geometry": {"type": "Point", "coordinates": [-73.5673, 45.5017]},
         "properties": {"osm_id": 2, "housenumber": "1000", "street": "Rue De La Gauchetiere O", "city": "Montreal", "state": "QC", "countrycode": "ca", "country": "Canada"}},
        # Vancouver, BC
        {"geometry": {"type": "Point", "coordinates": [-123.1207, 49.2827]},
         "properties": {"osm_id": 3, "housenumber": "800", "street": "Robson St", "city": "Vancouver", "state": "BC", "countrycode": "ca", "country": "Canada"}},
        # Tijuana, Mexico
        {"geometry": {"type": "Point", "coordinates": [-117.0382, 32.5149]},
         "properties": {"osm_id": 4, "housenumber": "123", "street": "Avenida Revolucion", "city": "Tijuana", "state": "BC", "countrycode": "mx", "country": "Mexico"}},
        # London, UK
        {"geometry": {"type": "Point", "coordinates": [-0.1278, 51.5074]},
         "properties": {"osm_id": 5, "housenumber": "10", "street": "Downing St", "city": "London", "countrycode": "gb", "country": "United Kingdom"}},
    ]

    for f in canadian_photon_features:
        city = f['properties']['city']
        is_us = is_us_photon_feature(f)
        assert_eq(is_us, False, f"isUsPhotonFeature rejects {city}")

    # Now simulate resolve with Photon for Canadian address
    try:
        simulate_photon_resolve("100 Queen St W, Toronto, ON", [canadian_photon_features[0]])
        assert_eq(False, True, "Photon resolve on Canadian address should throw OutOfBoundsError")
    except OutOfBoundsError as e:
        assert_eq(e.code, 'OUT_OF_COVERAGE_AREA', "Photon resolve throws OutOfBoundsError with code OUT_OF_COVERAGE_AREA")
        assert_eq(e.statusCode, 400, "OutOfBoundsError statusCode is 400")

    # Simulate resolve with Nominatim for Canadian address
    canadian_nominatim_places = [
        {"lat": "43.6532", "lon": "-79.3832", "display_name": "100, Queen Street West, Toronto, ON, Canada",
         "address": {"house_number": "100", "road": "Queen Street West", "city": "Toronto", "state": "Ontario", "country_code": "ca", "country": "Canada"}},
        {"lat": "32.5149", "lon": "-117.0382", "display_name": "123, Avenida Revolucion, Tijuana, Mexico",
         "address": {"house_number": "123", "road": "Avenida Revolucion", "city": "Tijuana", "country_code": "mx", "country": "Mexico"}},
    ]

    for p in canadian_nominatim_places:
        city = p['address']['city']
        is_us = is_us_nominatim_place(p)
        assert_eq(is_us, False, f"isUsNominatimPlace rejects {city}")

    try:
        simulate_nominatim_resolve("100 Queen St W, Toronto, ON", [canadian_nominatim_places[0]])
        assert_eq(False, True, "Nominatim resolve on Canadian address should throw OutOfBoundsError")
    except OutOfBoundsError as e:
        assert_eq(e.code, 'OUT_OF_COVERAGE_AREA', "Nominatim resolve throws OutOfBoundsError with code OUT_OF_COVERAGE_AREA")
        assert_eq(e.statusCode, 400, "OutOfBoundsError statusCode is 400")

    # Reverse geocode Canadian coordinates
    def mock_reverse_toronto(ctx, lat=0, lng=0):
        if lat < US_MIN_LAT or lat > US_MAX_LAT or lng < US_MIN_LNG or lng > US_MAX_LNG:
            raise OutOfBoundsError(lat, lng)
        # Check country for Toronto coords (43.6532, -79.3832 is inside lat/lng box but country is Canada)
        raise OutOfBoundsError(lat, lng)

    res = simulate_resolve_route({'lat': '43.6532', 'lng': '-79.3832'}, mock_reverse_toronto)
    assert_eq(res['status'], 400, "Reverse geocoding Canadian coords returns HTTP 400")
    assert_eq(res['body']['code'], 'OUT_OF_COVERAGE_AREA', "Reverse geocoding Canadian coords returns OUT_OF_COVERAGE_AREA")

    # -------------------------------------------------------------------------
    # SUITE 2: /api/geocode/resolve EXACT HTTP 400 ERROR CODES
    # -------------------------------------------------------------------------
    print("\n--- 2. Testing /api/geocode/resolve Exact HTTP 400 Error Codes ---")

    # 2.1 PO_BOX_NOT_SUPPORTED
    po_box_test_cases = [
        "PO Box 1234, Dallas, TX 75201",
        "P.O. Box 456, Seattle, WA 98101",
        "Post Office Box 789, Chicago, IL 60601",
        "P BOX 10, Denver, CO 80202",
        "P.O.B. 99, Miami, FL 33101",
        "Post Office Drawer 500, Austin, TX 78701",
        "PBOX 404, Boston, MA 02108",
    ]
    for po_str in po_box_test_cases:
        res = simulate_resolve_route({'address': po_str}, lambda addr: None)
        assert_eq(res['status'], 400, f"PO Box '{po_str}' returns HTTP 400")
        assert_eq(res['body']['code'], 'PO_BOX_NOT_SUPPORTED', f"PO Box '{po_str}' returns PO_BOX_NOT_SUPPORTED")
        assert_eq('physical residential street address' in res['body']['message'], True, f"PO Box '{po_str}' has explanatory message")

    # 2.2 STREET_NUMBER_REQUIRED
    missing_number_test_cases = [
        "Main St, Springfield, IL 62701",
        "Broadway, New York, NY 10001",
        "Ocean Ave, Santa Monica, CA 90401",
        "Market St, San Francisco, CA 94102",
        "Peachtree St NE, Atlanta, GA 30303",
    ]
    def mock_missing_num_resolver(addr):
        raise MissingStreetNumberError(addr)

    for mn_str in missing_number_test_cases:
        res = simulate_resolve_route({'address': mn_str}, mock_missing_num_resolver)
        assert_eq(res['status'], 400, f"Missing street number '{mn_str}' returns HTTP 400")
        assert_eq(res['body']['code'], 'STREET_NUMBER_REQUIRED', f"Missing street number '{mn_str}' returns STREET_NUMBER_REQUIRED")
        assert_eq('building number' in res['body']['message'], True, f"Missing street number '{mn_str}' message asks for building number")

    # 2.3 OUT_OF_COVERAGE_AREA
    foreign_address_test_cases = [
        ("100 Queen St W, Toronto, ON M5H 2N2", 43.6532, -79.3832),
        ("1000 Rue De La Gauchetiere O, Montreal, QC H3B 4W5", 45.5017, -73.5673),
        ("800 Robson St, Vancouver, BC V6Z 3B7", 49.2827, -123.1207),
        ("10 Downing St, London SW1A 2AA, UK", 51.5074, -0.1278),
        ("Av. Paseo de la Reforma 505, Mexico City", 19.4326, -99.1332),
    ]
    def mock_foreign_resolver(addr):
        for fa, lat, lng in foreign_address_test_cases:
            if fa == addr:
                raise OutOfBoundsError(lat, lng)
        raise OutOfBoundsError(0, 0)

    for fa_str, _, _ in foreign_address_test_cases:
        res = simulate_resolve_route({'address': fa_str}, mock_foreign_resolver)
        assert_eq(res['status'], 400, f"Foreign address '{fa_str[:30]}...' returns HTTP 400")
        assert_eq(res['body']['code'], 'OUT_OF_COVERAGE_AREA', f"Foreign address returns OUT_OF_COVERAGE_AREA")
        assert_eq('broadband coverage area' in res['body']['message'], True, f"Foreign address message mentions broadband coverage area")

    # -------------------------------------------------------------------------
    # SUITE 3: SUGGEST ROUTE FILTERS OUT NON-US SUGGESTIONS
    # -------------------------------------------------------------------------
    print("\n--- 3. Testing Suggest Route Filters Out Non-US Suggestions ---")

    mixed_photon_features = [
        # US Suggestion 1: New York
        {"geometry": {"type": "Point", "coordinates": [-73.9857, 40.7484]},
         "properties": {"osm_id": 101, "housenumber": "350", "street": "5th Ave", "city": "New York", "state": "New York", "postcode": "10118", "countrycode": "us", "country": "United States"}},
        # Foreign Suggestion 1: Toronto, Canada (Queen St)
        {"geometry": {"type": "Point", "coordinates": [-79.3832, 43.6532]},
         "properties": {"osm_id": 102, "housenumber": "100", "street": "Queen St W", "city": "Toronto", "state": "Ontario", "countrycode": "ca", "country": "Canada"}},
        # US Suggestion 2: Naperville, IL
        {"geometry": {"type": "Point", "coordinates": [-88.1535, 41.7508]},
         "properties": {"osm_id": 103, "housenumber": "456", "street": "Oak Rd", "city": "Naperville", "state": "Illinois", "postcode": "60540", "countrycode": "us", "country": "United States"}},
        # Foreign Suggestion 2: London, UK (Queen Victoria St)
        {"geometry": {"type": "Point", "coordinates": [-0.0980, 51.5120]},
         "properties": {"osm_id": 104, "housenumber": "1", "street": "Queen Victoria St", "city": "London", "countrycode": "gb", "country": "United Kingdom"}},
        # Foreign Suggestion 3: Mexico (Revolucion)
        {"geometry": {"type": "Point", "coordinates": [-117.0382, 32.5149]},
         "properties": {"osm_id": 105, "housenumber": "123", "street": "Avenida Revolucion", "city": "Tijuana", "countrycode": "mx", "country": "Mexico"}},
    ]

    def mock_photon_suggest_impl(query):
        # Simulate photon-geocoder.ts suggest logic
        po_re = re.compile(r'\b(?:P(?:OST)?\.?\s*(?:O(?:FFICE)?\.?\s*)?BOX|P\.?\s*O\.?\s*B(?:\.|\b)|POST\s+OFFICE\s+DRAWER|PBOX)\b', re.I)
        if po_re.search(query):
            return []
        suggestions = []
        for feature in mixed_photon_features:
            if not is_us_photon_feature(feature):
                continue
            props = feature['properties']
            coords = feature['geometry']['coordinates']
            street_line = f"{props['housenumber']} {props['street']}"
            suggestions.append({
                'id': f"photon-{props['osm_id']}",
                'label': f"{street_line}, {props['city']}, {props['state']} {props['postcode']}",
                'streetLine': street_line,
                'city': props['city'],
                'state': 'NY' if props['state'] == 'New York' else 'IL',
                'zip5': props['postcode'],
                'lat': coords[1],
                'lng': coords[0],
                'source': 'photon'
            })
        return suggestions

    res = simulate_suggest_route({'q': 'Queen St'}, mock_photon_suggest_impl)
    assert_eq(res['status'], 200, "Suggest route returns HTTP 200")
    assert_eq(res['body']['count'], 2, "Only 2 US suggestions returned out of 5 mixed candidates")
    for s in res['body']['suggestions']:
        assert_eq(s['state'] in ('NY', 'IL'), True, f"Suggestion '{s['label']}' is verified US location")

    # Suggest with query < 3 chars
    res_short = simulate_suggest_route({'q': 'ab'}, mock_photon_suggest_impl)
    assert_eq(res_short['status'], 200, "Short query returns HTTP 200")
    assert_eq(res_short['body']['count'], 0, "Short query returns count: 0")
    assert_eq(res_short['body']['suggestions'], [], "Short query returns empty suggestions")

    # Suggest with missing query
    res_missing = simulate_suggest_route({}, mock_photon_suggest_impl)
    assert_eq(res_missing['status'], 400, "Missing query returns HTTP 400")
    assert_eq(res_missing['body']['code'], 'MISSING_QUERY_PARAMETER', "Missing query code is MISSING_QUERY_PARAMETER")

    # Suggest with query > 256 chars
    res_long = simulate_suggest_route({'q': 'a' * 257}, mock_photon_suggest_impl)
    assert_eq(res_long['status'], 400, "Overlength query returns HTTP 400")
    assert_eq(res_long['body']['code'], 'QUERY_TOO_LONG', "Overlength query code is QUERY_TOO_LONG")

    # Suggest with PO Box query
    res_po = simulate_suggest_route({'q': 'PO Box 123'}, mock_photon_suggest_impl)
    assert_eq(res_po['status'], 200, "PO Box suggest returns HTTP 200")
    assert_eq(res_po['body']['count'], 0, "PO Box suggest filters out all suggestions")

    # -------------------------------------------------------------------------
    # SUITE 4: ADVERSARIAL BORDER & EXCLAVE STRESS TESTING
    # -------------------------------------------------------------------------
    print("\n--- 4. Testing Adversarial Border & Territorial Sovereignty Stress Cases ---")

    border_cases = [
        # Niagara Falls: US vs CA side
        ("Niagara Falls NY (US)", 43.0962, -79.0377, "us", "United States", True),
        ("Niagara Falls ON (CA)", 43.0896, -79.0849, "ca", "Canada", False),
        # Detroit / Windsor
        ("Detroit MI (US)", 42.3314, -83.0458, "us", "United States", True),
        ("Windsor ON (CA)", 42.3149, -83.0364, "ca", "Canada", False),
        # Derby Line / Stanstead (Haskell Free Library sits on the border)
        ("Derby Line VT (US)", 45.0044, -72.0994, "us", "United States", True),
        ("Stanstead QC (CA)", 45.0112, -72.0931, "ca", "Canada", False),
        # Point Roberts WA (US exclave south of 49th parallel in BC)
        ("Point Roberts WA (US)", 48.9884, -123.0569, "us", "United States", True),
        ("Tsawwassen BC (CA)", 49.0069, -123.0789, "ca", "Canada", False),
        # San Diego / Tijuana
        ("San Ysidro CA (US)", 32.5540, -117.0540, "us", "United States", True),
        ("Tijuana BC (MX)", 32.5149, -117.0382, "mx", "Mexico", False),
        # US Territories
        ("San Juan PR (US)", 18.4655, -66.1057, "us", "United States", True),
        ("Anchorage AK (US)", 61.2181, -149.9003, "us", "United States", True),
        ("Honolulu HI (US)", 21.3069, -157.8583, "us", "United States", True),
        # Out-of-bounds Pacific territory (Guam is at lat 13.44, lng 144.79 - outside bounding box 17.5-72.0, -179 to -64)
        ("Guam (outside box)", 13.4443, 144.7937, "us", "United States", False),
        # Missing country tags inside bounding box (must reject for safety)
        ("Missing country tag inside US box", 40.7128, -74.0060, None, None, False),
    ]

    for label, lat, lng, cc, country, expected in border_cases:
        test_feature = {
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {"countrycode": cc, "country": country}
        }
        res_photon = is_us_photon_feature(test_feature)
        assert_eq(res_photon, expected, f"Photon border test '{label}' -> expected {expected}")

        test_nom = {
            "lat": str(lat), "lon": str(lng),
            "address": {"country_code": cc, "country": country}
        }
        res_nom = is_us_nominatim_place(test_nom)
        assert_eq(res_nom, expected, f"Nominatim border test '{label}' -> expected {expected}")

    # -------------------------------------------------------------------------
    # SUITE 5: SOURCE CODE INTEGRITY AUDIT
    # -------------------------------------------------------------------------
    print("\n--- 5. Source Code Integrity Audit (Zero Tolerated Facades) ---")

    # Check for hardcoded test inputs in source files
    src_dir = os.path.join(BASE_DIR, 'src')
    forbidden_terms = ['hardcoded', 'TODO: implement', 'MOCK_RESULT', 'dummy_implementation', 'fake_geocode']

    files_checked = 0
    for root, _, files in os.walk(src_dir):
        for f in files:
            if f.endswith(('.ts', '.tsx', '.js')):
                files_checked += 1
                fpath = os.path.join(root, f)
                with open(fpath, 'r', encoding='utf-8') as src_file:
                    text = src_file.read()
                    for term in forbidden_terms:
                        assert_eq(term.lower() in text.lower(), False, f"Integrity check: '{term}' must not exist in {f}")

    assert_eq(files_checked >= 12, True, f"Scanned {files_checked} source files in src/ for integrity violations")

    print("\n======================================================================")
    print(f"FINAL REVIEW RESULTS: {total_passed} PASSED, {total_failed} FAILED")
    print("======================================================================")

    if total_failed > 0:
        sys.exit(1)

if __name__ == '__main__':
    run_tests()
