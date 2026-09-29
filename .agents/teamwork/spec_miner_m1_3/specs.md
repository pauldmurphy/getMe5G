# API Specification: Geocoding & Address Normalization Routes (`/api/geocode/*`)

**Subagent**: `spec_miner_m1_3`  
**Working Directory**: `.agents/teamwork/spec_miner_m1_3`  
**Milestone**: Milestone 1 (Address Intake & Pluggable Geocoding System)  
**Status**: Authoritative Technical Route Specification  
**Reference Documents**: `ORIGINAL_REQUEST.md`, `PROJECT.md`, `spec_miner_survey_2/specs.md`

---

## 1. Executive Summary & Route Overview

In the 5G Home Internet Arbitrage & Availability Engine, precise address resolution is mission-critical. Unlike wireline broadband where an entire ZIP code or street often shares cable/DSL infrastructure, 5G Fixed Wireless Access (FWA) depends strictly on millimeter-wave (mmWave) and mid-band (n41/n77/C-Band) cellular radio propagation from macro and small cell towers. A query must resolve to an exact physical rooftop coordinate and structured postal components (`streetNumber`, `streetName`, `city`, `state`, `zip5`) to:
1. Prevent delivery or carrier provisioning failures (e.g. PO Boxes cannot receive fixed wireless gateway hardware).
2. Accurately correlate the location with FCC Broadband Data Collection (BDC) Census Block fabric records.
3. Enable pre-flight availability checks against carrier endpoints (T-Mobile, Verizon, AT&T) without triggering false out-of-footprint rejections.

To achieve this without requiring external paid API keys out of the box, the system exposes two primary internal Next.js App Router API routes:
- **`GET /api/geocode/suggest`**: High-speed, search-as-you-type autocomplete suggestions powered by zero-config open geocoders (Komoot Photon / OSM Nominatim) with optional drop-in commercial adapters (Google Places / Mapbox).
- **`GET /api/geocode/resolve`**: Deep geocoding resolution and postal normalization cascade (US Census Bureau Geocoder $\rightarrow$ Komoot Photon $\rightarrow$ OSM Nominatim) producing canonical `NormalizedAddress` payloads and rejecting non-viable inputs (e.g. PO Boxes, missing street numbers).

---

## 2. Route Specification: `GET /api/geocode/suggest`

### 2.1 Route Signature & Purpose
- **Endpoint**: `/api/geocode/suggest`
- **HTTP Method**: `GET`
- **Purpose**: Powers the real-time search combobox (`AddressSearchBar.tsx`). Returns structured address suggestions as the user types, filtered to the United States.
- **Upstream SLA**: $\le 350$ms response latency.

### 2.2 Request Query Parameters
| Parameter | Type | Required | Default | Validation & Bounds | Description |
|---|---|---|---|---|---|
| `q` | `string` | **Yes** | — | `1 <= q.trim().length <= 256` | Search query text entered by the user. Stripped of control characters. |
| `limit` | `integer` | No | `5` | `1 <= limit <= 10` | Maximum number of suggestions to return. Clamped to `10` if exceeded. |
| `lat` | `float` | No | — | `-90.0 <= lat <= 90.0` | Optional user latitude for proximity-biased suggestion sorting. |
| `lng` | `float` | No | — | `-180.0 <= lng <= 180.0` | Optional user longitude for proximity-biased suggestion sorting. |

### 2.3 Input Validation & Debouncing Protocol

#### Query String Validation Rules:
1. **Missing Query**: If `q` is absent, null, or empty string after trimming (`q.trim().length === 0`), return `HTTP 400 Bad Request` with code `MISSING_QUERY_PARAMETER`.
2. **Short Query Threshold (Search-As-You-Type Grace)**: If `q.trim().length < 3` (e.g., user just typed `"1"` or `"16"`):
   - Return `HTTP 200 OK` with an empty suggestions array: `{"status": "success", "query": "...", "count": 0, "suggestions": []}`.
   - Do **NOT** call upstream geocoders (Photon/Nominatim/Google). This avoids spamming upstream rate limits with unsearchable 1- or 2-letter tokens.
3. **Maximum Length Enforcement**: If `q.length > 256`, reject with `HTTP 400 Bad Request` and code `QUERY_TOO_LONG`.
4. **Sanitization**: Null bytes (`\0`), Carriage Returns (`\r`), Newlines (`\n`), and unprintable control characters are stripped.

#### Client Debouncing & Cancellation Contract:
- **Client Debounce**: The frontend (`AddressSearchBar.tsx`) MUST implement a **300ms debounce** timer on keystrokes.
- **AbortController Cancellation**: Each new keystroke MUST cancel the preceding pending in-flight `fetch` request using `AbortController.abort()` to prevent race conditions and out-of-order suggestion rendering.

### 2.4 Upstream Provider Cascade for Suggestions
1. **Stage 1 (Commercial Drop-in)**:
   - If `GOOGLE_PLACES_API_KEY` is present in environment:
     - Call Google Places Autocomplete:
       `https://maps.googleapis.com/maps/api/place/autocomplete/json?input={encodeURIComponent(q)}&components=country:us&types=address&key={GOOGLE_PLACES_API_KEY}`
   - Else if `MAPBOX_ACCESS_TOKEN` is present:
     - Call Mapbox Geocoding forward:
       `https://api.mapbox.com/search/geocode/v6/forward?q={encodeURIComponent(q)}&country=us&types=address&limit={limit}&access_token={MAPBOX_ACCESS_TOKEN}`
2. **Stage 2 (Default Zero-Config Open Geocoder - Komoot Photon)**:
   - Call Komoot Photon API:
     `https://photon.komoot.io/api?q={encodeURIComponent(q)}&bbox=-125,24,-66,49&limit={limit}&lang=en`
   - If `lat` and `lng` are provided: append `&lat={lat}&lon={lng}` for local proximity sorting.
   - Filter results to United States (`properties.countrycode === 'US'` or `properties.country === 'United States'`).
3. **Stage 3 (Secondary Zero-Config Fallback - OSM Nominatim)**:
   - If Photon fails (HTTP error, timeout $\ge 2.0$s, or network failure):
     - Call Nominatim Search:
       `https://nominatim.openstreetmap.org/search?q={encodeURIComponent(q)}&format=jsonv2&addressdetails=1&countrycodes=us&limit={limit}`
     - Send required User-Agent header: `User-Agent: GetMe5G-ArbitrageEngine/1.0 (contact@getme5g.local)`.

### 2.5 HTTP Response Headers
- `Content-Type`: `application/json; charset=utf-8`
- `Cache-Control`: `public, s-maxage=3600, max-age=1800, stale-while-revalidate=86400` (Enables edge and browser caching for identical queries)
- `X-Geocoder-Source`: Identifier of provider that served the request (`google`, `mapbox`, `photon`, `nominatim`, `cache`)

### 2.6 Exact JSON Payloads for `GET /api/geocode/suggest`

#### Success Response (`200 OK`)
```json
{
  "status": "success",
  "query": "1600 Pennsylvania Ave",
  "count": 2,
  "suggestions": [
    {
      "id": "photon-osm-way-2382442",
      "label": "1600 Pennsylvania Avenue Northwest, Washington, DC 20500",
      "streetLine": "1600 Pennsylvania Avenue Northwest",
      "city": "Washington",
      "state": "DC",
      "zip5": "20500",
      "lat": 38.897675,
      "lng": -77.03653,
      "source": "photon"
    },
    {
      "id": "photon-osm-node-8912384",
      "label": "1600 Pennsylvania Avenue, McDonough, GA 30253",
      "streetLine": "1600 Pennsylvania Avenue",
      "city": "McDonough",
      "state": "GA",
      "zip5": "30253",
      "lat": 33.4358,
      "lng": -84.1481,
      "source": "photon"
    }
  ]
}
```

#### Short Query Response (`200 OK` — No Upstream Call)
```json
{
  "status": "success",
  "query": "16",
  "count": 0,
  "suggestions": []
}
```

#### Validation Error: Missing Query (`400 Bad Request`)
```json
{
  "status": "error",
  "code": "MISSING_QUERY_PARAMETER",
  "message": "Query parameter 'q' is required and cannot be empty.",
  "details": {
    "parameter": "q"
  }
}
```

#### Validation Error: Query Too Long (`400 Bad Request`)
```json
{
  "status": "error",
  "code": "QUERY_TOO_LONG",
  "message": "Query parameter 'q' exceeds maximum allowable length of 256 characters.",
  "details": {
    "parameter": "q",
    "maxLength": 256,
    "receivedLength": 280
  }
}
```

---

## 3. Route Specification: `GET /api/geocode/resolve`

### 3.1 Route Signature & Purpose
- **Endpoint**: `/api/geocode/resolve`
- **HTTP Method**: `GET`
- **Purpose**: Fully resolves and normalizes an address string into canonical postal components (`streetNumber`, `streetName`, `unitNumber`, `city`, `state`, `zip5`, `zip4`) and verified WGS84 geographic coordinates (`lat`, `lng`).
- **SLA**: $\le 1.2$ seconds cold query; $\le 5$ milliseconds warm cache hit.

### 3.2 Request Query Parameters
| Parameter | Type | Required | Default | Bounds & Validation | Description |
|---|---|---|---|---|---|
| `address` | `string` | Conditional | — | `5 <= address.trim().length <= 500` | Full single-line US address string. Required unless `lat` & `lng` are provided. |
| `lat` | `float` | Conditional | — | `-90.0 <= lat <= 90.0` | Latitude coordinate for reverse geocoding. Required if `address` omitted. |
| `lng` | `float` | Conditional | — | `-180.0 <= lng <= 180.0` | Longitude coordinate for reverse geocoding. Required if `address` omitted. |
| `fresh` | `boolean` | No | `false` | `true` or `false` | If `true`, bypasses L1 in-memory cache and forces live geocoder cascade. |

### 3.3 Strict Address Validation & Business Logic Rules

#### 1. PO Box Detection & Rejection (Domain Constraint)
- **Regex Rule**:
  ```regex
  /\b(?:P(?:OST)?\.?\s*O(?:FFICE)?\.?\s*BOX|P\.?O\.?B\.?|POST\s+OFFICE\s+DRAWER|PBOX)\b/i
  ```
- **Rationale**: 5G Fixed Wireless Gateways (T-Mobile Internet Gateway, Verizon Internet Gateway, AT&T All-Fi Hub) require a fixed physical rooftop location to verify cell tower radio frequency coverage and prevent unauthorized relocation outside the licensed cell sector. Carriers strictly refuse orders to PO Boxes.
- **HTTP Status**: `400 Bad Request`
- **Error Code**: `PO_BOX_NOT_SUPPORTED`

#### 2. Missing Street Number Detection
- **Rule**: If the raw address does not contain a house/building number, or if the geocoder matches only a street centerline, city centroid, or ZIP code polygon without an exact street number.
- **Rationale**: 5G mid-band signal propagation drops significantly over 100-meter variations; a precise building number is mandatory to evaluate tower distance and beam clearance.
- **HTTP Status**: `400 Bad Request`
- **Error Code**: `STREET_NUMBER_REQUIRED`

#### 3. Out of Bounds / Non-US Territory Validation
- **Rule**: Coordinates must fall within US boundaries:
  - Continental US / Lower 48: Lat `24.0` to `50.0`, Lng `-125.0` to `-66.0`
  - Alaska: Lat `51.0` to `72.0`, Lng `-180.0` to `-130.0`
  - Hawaii: Lat `18.0` to `23.0`, Lng `-161.0` to `-154.0`
  - Puerto Rico: Lat `17.8` to `18.6`, Lng `-67.3` to `-65.2`
  - Country code must resolve to `US` or `PR`.
- **HTTP Status**: `400 Bad Request`
- **Error Code**: `OUT_OF_COVERAGE_AREA`

#### 4. Unresolvable Address (Zero Matches Across Cascade)
- **Rule**: If the cascade executes all open tiers (Census, Photon, Nominatim) and receives zero valid parcel matches.
- **HTTP Status**: `400 Bad Request`
- **Error Code**: `ADDRESS_NOT_RESOLVED`

### 3.4 Geocoding Resolution Cascade Architecture

```
[ Incoming Request: GET /api/geocode/resolve?address=... ]
                             │
                             ▼
         [ Pre-validation: PO Box check & string length ]
         │ (Fails immediately with 400 if PO Box detected)
                             │
                             ▼
              [ Check L1 In-Memory Cache ] ───(HIT)───► Return HTTP 200 (< 5ms)
                             │ (MISS or fresh=true)
                             ▼
             [ Optional Commercial Geocoder ]
             (Google Places or Mapbox if env keys present)
                             │ (Not configured or failed)
                             ▼
         [ Stage 1: US Census Bureau Geocoder API ]
         (URL: /geocoder/locations/onelineaddress, timeout: 2500ms)
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
   [ Match Found (>0) ]             [ 0 Matches or Timeout ]
            │                                 │
            │                                 ▼
            │               [ Stage 2: Komoot Photon API ]
            │               (URL: /api?q=..., timeout: 2000ms)
            │                                 │
            │                       ┌─────────┴─────────┐
            │                       ▼                   ▼
            │              [ Match Found (>0) ]    [ 0 Matches or Error ]
            │                       │                   │
            │                       │                   ▼
            │                       │     [ Stage 3: OSM Nominatim API ]
            │                       │     (URL: /search?q=..., timeout: 2500ms)
            │                       │                   │
            │                       │         ┌─────────┴─────────┐
            │                       │         ▼                   ▼
            │                       │    [ Match Found ]    [ 0 Matches ]
            │                       │         │                   │
            ▼                       ▼         ▼                   ▼
     [ Address Normalization Layer: AddressNormalizer ]     [ Return HTTP 400 ]
     - Standardize street components & unit                 ADDRESS_NOT_RESOLVED
     - Map state to 2-letter USPS uppercase (e.g. DC, NY)
     - Separate 5-digit ZIP & 4-digit ZIP extension
     - Prevent x/y longitude/latitude inversion
     - Compute confidence score (0.0 - 1.0)
                             │
                             ▼
               [ Save to L1 In-Memory Cache ]
                             │
                             ▼
               [ Return HTTP 200 OK JSON ]
```

#### Coordinate Inversion Trap Prevention:
In the US Census Bureau Geocoder response:
```json
"coordinates": {
  "x": -77.03653,
  "y": 38.897675
}
```
`x` corresponds to **Longitude** (negative in Western hemisphere) and `y` corresponds to **Latitude**. The adapter MUST map:
```typescript
const lat = coordinates.y;
const lng = coordinates.x;
```
Swapping these would result in lat: -77 (Antarctica) and lng: 38 (Indian Ocean). The normalization layer validates that `lat > 0` for all US territories.

### 3.5 Postal Component Normalization Rules (`AddressNormalizer`)
- **Street Number**: Extracted building number (e.g. `"1600"`, `"742"`, or Queens-style hyphenated `"120-05"`, or half-numbers `"123 1/2"`).
- **Street Name**: Normalized street name with USPS standard suffix (e.g. `"Pennsylvania Ave NW"`, `"Main St"`, `"Evergreen Ter"`).
- **Secondary Unit Extraction**: Secondary designators (Apartment, Suite, Unit, Building, Floor) are segregated from the primary street line using regex:
  ```regex
  /(?:APT|APARTMENT|SUITE|STE|UNIT|BLDG|BUILDING|FL|FLOOR|RM|ROOM|DEPT|#)\s*([A-Z0-9-]+)/i
  ```
  Example: `"742 Evergreen Terrace Apt 4B"` $\rightarrow$ `streetName: "Evergreen Terrace"`, `unitNumber: "Apt 4B"`.
- **State Code Normalization**: All full state names or lowercase representations are converted to canonical 2-letter uppercase USPS codes via lookup dictionary:
  `"District of Columbia"` $\rightarrow$ `"DC"`, `"California"` $\rightarrow$ `"CA"`, `"Texas"` $\rightarrow$ `"TX"`.
- **ZIP Code Parsing**: Split into 5-digit `zip5` (e.g. `"20500"`) and optional 4-digit extension `zip4` (e.g. `"0003"`).
- **Standardized Single-Line String (`formattedAddress`)**:
  `${streetNumber} ${streetName}${unitNumber ? ' ' + unitNumber : ''}, ${city}, ${state} ${zip5}${zip4 ? '-' + zip4 : ''}`.

### 3.6 Exact JSON Payloads for `GET /api/geocode/resolve`

#### Success Response (`200 OK`)
```json
{
  "status": "success",
  "address": {
    "streetNumber": "1600",
    "streetName": "Pennsylvania Ave NW",
    "unitNumber": null,
    "city": "Washington",
    "state": "DC",
    "zip5": "20500",
    "zip4": "0003",
    "lat": 38.897675,
    "lng": -77.03653,
    "formattedAddress": "1600 Pennsylvania Ave NW, Washington, DC 20500-0003",
    "geocoderSource": "census",
    "confidenceScore": 0.98
  }
}
```

#### Success Response with Apartment Unit (`200 OK`)
```json
{
  "status": "success",
  "address": {
    "streetNumber": "742",
    "streetName": "Evergreen Ter",
    "unitNumber": "Apt 4B",
    "city": "Springfield",
    "state": "OR",
    "zip5": "97477",
    "zip4": null,
    "lat": 44.0531,
    "lng": -123.0189,
    "formattedAddress": "742 Evergreen Ter Apt 4B, Springfield, OR 97477",
    "geocoderSource": "photon",
    "confidenceScore": 0.88
  }
}
```

#### Error: PO Box Rejected (`400 Bad Request`)
```json
{
  "status": "error",
  "code": "PO_BOX_NOT_SUPPORTED",
  "message": "Fixed wireless home internet requires a physical residential street address. PO Boxes are not eligible.",
  "details": {
    "submittedAddress": "PO Box 1234, Dallas, TX 75201",
    "field": "address",
    "reason": "PO Boxes do not possess discrete physical rooftop coordinates for cellular RF line-of-sight analysis or home gateway delivery."
  }
}
```

#### Error: Missing Street Number (`400 Bad Request`)
```json
{
  "status": "error",
  "code": "STREET_NUMBER_REQUIRED",
  "message": "Please provide a full street address including building number.",
  "details": {
    "submittedAddress": "Main St, Springfield, IL 62701",
    "field": "address",
    "reason": "Building or house number is missing from the query."
  }
}
```

#### Error: Address Not Resolved (`400 Bad Request`)
```json
{
  "status": "error",
  "code": "ADDRESS_NOT_RESOLVED",
  "message": "Unable to geocode the submitted address into a valid US physical location.",
  "details": {
    "submittedAddress": "99999 Nonexistent Fantasy Road, Nowhere, ZZ 00000",
    "field": "address",
    "reason": "Zero matches returned across geocoding cascade (Census, Photon, Nominatim)."
  }
}
```

#### Error: Out of Coverage Area (`400 Bad Request`)
```json
{
  "status": "error",
  "code": "OUT_OF_COVERAGE_AREA",
  "message": "Address is outside the United States broadband coverage area.",
  "details": {
    "submittedAddress": "100 King St W, Toronto, ON M5X 1A9, Canada",
    "country": "CA",
    "reason": "Only US postal addresses are supported for 5G Home Internet availability."
  }
}
```

#### Error: Invalid Coordinates (`422 Unprocessable Entity`)
```json
{
  "status": "error",
  "code": "INVALID_COORDINATES",
  "message": "Provided latitude or longitude coordinate is outside valid geographical boundaries.",
  "details": {
    "lat": 105.42,
    "lng": -77.0365,
    "reason": "Latitude must be between -90.0 and 90.0 degrees."
  }
}
```

#### Error: Upstream Geocoder Outage / Timeout (`502 Bad Gateway` / `504 Gateway Timeout`)
```json
{
  "status": "error",
  "code": "GEOCODER_UPSTREAM_TIMEOUT",
  "message": "Upstream geocoding providers timed out. Please retry shortly.",
  "details": {
    "providersAttempted": ["census", "photon", "nominatim"],
    "timeoutMs": 7000
  }
}
```

---

## 4. HTTP Status Codes & Error Directory

| HTTP Status | Error Code | Trigger Condition | User / Client Remediation |
|---|---|---|---|
| `200 OK` | `null` | Successful suggestion list or resolved normalized address. | Render suggestions in dropdown or proceed to availability engine. |
| `400 Bad Request` | `MISSING_QUERY_PARAMETER` | `GET /api/geocode/suggest` called without `q` param. | Provide valid search text in query parameter. |
| `400 Bad Request` | `QUERY_TOO_LONG` | `q` parameter length exceeds 256 characters. | Shorten search string. |
| `400 Bad Request` | `MISSING_ADDRESS_PARAMETER` | `GET /api/geocode/resolve` called without `address` or `lat`/`lng`. | Provide complete street address string. |
| `400 Bad Request` | `ADDRESS_TOO_SHORT` | Address string has fewer than 5 characters. | Enter complete street address. |
| `400 Bad Request` | `ADDRESS_TOO_LONG` | Address string exceeds 500 characters. | Shorten address string. |
| `400 Bad Request` | `PO_BOX_NOT_SUPPORTED` | Input matches PO Box regex pattern. | Enter physical residential street address. |
| `400 Bad Request` | `STREET_NUMBER_REQUIRED` | Input lacks building number or matches only street line/city. | Enter street address with building number (e.g. "123 Main St"). |
| `400 Bad Request` | `OUT_OF_COVERAGE_AREA` | Resolved coordinates/country fall outside US territory. | Enter an address located within the United States. |
| `400 Bad Request` | `ADDRESS_NOT_RESOLVED` | Zero parcel matches returned by geocoding cascade. | Check spelling or verify address on USPS locator. |
| `422 Unprocessable Entity` | `INVALID_COORDINATES` | `lat` not in `[-90, 90]` or `lng` not in `[-180, 180]`. | Ensure valid WGS84 decimal degree format. |
| `429 Too Many Requests` | `RATE_LIMIT_EXCEEDED` | Client exceeds local rate limit (e.g. >30 req/min). | Back off request rate. |
| `502 Bad Gateway` | `GEOCODER_UPSTREAM_ERROR` | Upstream provider returns 5xx or unparseable malformed body. | Automatic cascade handles next provider; returned only if all fail. |
| `504 Gateway Timeout` | `GEOCODER_UPSTREAM_TIMEOUT`| All upstream providers exceed cascade timeout budgets. | Retry request after delay. |
| `500 Internal Server Error`| `INTERNAL_SERVER_ERROR` | Unhandled server exception during normalizer execution. | Inspect server logs. |

---

## 5. Features Discovered & Mined

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|---|---|---|---|---|---|---|
| 1 | API Route | `/api/geocode/suggest` Autocomplete | REST endpoint serving debounced address suggestions for search-as-you-type combobox. | `q` (string, required), `limit` (int, default 5), `lat`/`lng` (optional) | `200 OK` JSON with `suggestions: AddressSuggestion[]` | Returns `400` if `q` missing or length > 256; returns `200` with `[]` if length < 3. | ORIGINAL_REQUEST.md R1 & PROJECT.md |
| 2 | API Route | `/api/geocode/resolve` Geocode & Normalize | REST endpoint resolving free-form address strings into structured postal components & coordinates. | `address` (string) or `lat` & `lng` (float), `fresh` (bool) | `200 OK` JSON with `address: NormalizedAddress` | Returns `400` for PO Boxes, missing street numbers, or zero matches. | ORIGINAL_REQUEST.md R1 & PROJECT.md |
| 3 | Validation | PO Box Interception & Rejection | Regex-based detection preventing cellular availability checks on PO Boxes. | Raw address string | Allowed if physical address; rejected if PO Box | Emits `400 Bad Request` with `PO_BOX_NOT_SUPPORTED`. | 5G FWA carrier shipping and propagation rules |
| 4 | Validation | Street Number Enforcement | Validates presence of house/building number necessary for rooftop cellular radio propagation. | Raw address string / parsed components | Allowed if building number found; rejected if absent | Emits `400 Bad Request` with `STREET_NUMBER_REQUIRED`. | FCC BDC location fabric & cellular RF line-of-sight specs |
| 5 | Validation | Short Query Suppressor | Threshold check in `/api/geocode/suggest` preventing premature upstream API requests on 1-2 char inputs. | `q.trim().length < 3` | `200 OK` with `suggestions: []` | No upstream requests dispatched. | Komoot Photon & Nominatim API Usage Policies |
| 6 | Normalization | USPS State Abbreviation Mapping | Converts full state names (e.g. "District of Columbia") to standardized 2-letter uppercase codes ("DC"). | Raw state string from geocoder | Standard 2-letter postal code | Falls back to uppercase truncation or error if unrecognized. | USPS Publication 28 / Postal Addressing Standards |
| 7 | Normalization | Secondary Unit Disambiguation | Extracts Apartment, Suite, Floor, or Unit indicators and isolates them from the primary street line. | Raw address string | `unitNumber: string | null`, cleaned `streetName` | Does not corrupt primary street name for geocoding lookup. | USPS Postal Addressing Standards |
| 8 | Normalization | ZIP+4 Deconstruction | Parses 9-digit postal codes into base 5-digit `zip5` and 4-digit extension `zip4`. | `"20500-0003"` or `"20500 0003"` | `zip5: "20500"`, `zip4: "0003"` | Gracefully sets `zip4: null` if only 5 digits provided. | USPS ZIP Code Standards |
| 9 | Geocoder Cascade | US Census Bureau Open Primary | Zero-config, keyless REST geocoder providing high-confidence official US coordinates & TigerLine attributes. | One-line address string | Coordinates (x/y) and postal components | Falls back to Photon on 0 matches, 503, or timeout (>2.5s). | US Census Bureau Geocoding Services API |
| 10 | Geocoder Cascade | Komoot Photon Open Secondary | Free OpenStreetMap-based autocomplete & geocoding API with US bounding box filter. | Address string or query prefix | GeoJSON FeatureCollection | Falls back to Nominatim on failure or missing house number. | Photon Komoot API Specification |
| 11 | Geocoder Cascade | OSM Nominatim Tertiary Fallback | OpenStreetMap structured geocoder providing fallback address details with mandatory User-Agent. | Address string, format=jsonv2 | Array of geocoded places with address breakdown | Dispatches request with compliant User-Agent; falls back to 400. | OpenStreetMap Nominatim Usage Policy |
| 12 | Geocoder Cascade | Commercial Drop-in Adapters | Drop-in support for Google Places and Mapbox forward geocoding enabled via environment variables. | `GOOGLE_PLACES_API_KEY` or `MAPBOX_ACCESS_TOKEN` | Verified commercial geocoding payloads | Seamlessly falls through to Census/Photon if keys invalid or unconfigured. | Google Maps Platform & Mapbox Geocoding APIs |
| 13 | Reliability | Census Coordinate Inversion Guard | Guarantees proper mapping of Census `coordinates.x` to Longitude and `coordinates.y` to Latitude. | Census coordinates object | Inverted coordinate protection (`lng = x`, `lat = y`) | Prevents invalid negative latitude coordinates. | US Census Bureau API Documentation |
| 14 | Performance | L1 In-Memory Result Caching | High-speed in-memory LRU cache storing normalized geocoding responses for repeat queries. | Normalized address key | Sub-5ms resolved `NormalizedAddress` response | Cache miss transparently queries cascade; writes to cache on success. | High-throughput web API caching patterns |
| 15 | Performance | Edge & Client Cache Headers | Emits standard `Cache-Control` headers on both suggest and resolve routes to leverage CDN & browser cache. | HTTP GET request | `Cache-Control` header with max-age, s-maxage, and stale-while-revalidate | Allows stale while revalidating; caches suggestions for 1 hour. | RFC 7234 HTTP/1.1 Caching Specification |

---

## 6. Comprehensive Edge Cases & Observed Behaviors Table

| # | Feature | Input / Scenario | Expected / Observed Behavior |
|---|---|---|---|
| 1 | Resolve | `"PO Box 100, Dallas, TX 75201"` | Regex matches PO Box. Route immediately halts before upstream network calls and returns `HTTP 400 Bad Request` with `code: "PO_BOX_NOT_SUPPORTED"`. |
| 2 | Resolve | `"P.O. Box 456, Austin, TX 78701"` | Regex matches dotted PO Box abbreviation. Returns `HTTP 400 Bad Request` with `code: "PO_BOX_NOT_SUPPORTED"`. |
| 3 | Resolve | `"Post Office Box 789, Miami, FL 33101"` | Regex matches full words "Post Office Box". Returns `HTTP 400 Bad Request` with `code: "PO_BOX_NOT_SUPPORTED"`. |
| 4 | Resolve | `"POB 333, Denver, CO 80201"` | Regex matches "POB" shorthand. Returns `HTTP 400 Bad Request` with `code: "PO_BOX_NOT_SUPPORTED"`. |
| 5 | Resolve | `"Main St, Springfield, IL 62701"` | Address missing building number. Normalizer detects missing `streetNumber` and returns `HTTP 400 Bad Request` with `code: "STREET_NUMBER_REQUIRED"`. |
| 6 | Resolve | `"Broadway & 5th Ave, New York, NY 10001"` | Intersection query lacks discrete building number. Returns `HTTP 400 Bad Request` with `code: "STREET_NUMBER_REQUIRED"`. |
| 7 | Resolve | `"1600 Pennsylvania Ave NW, Washington, DC 20500"` | Census Geocoder matches rooftop. Coordinates `y: 38.897675, x: -77.03653` mapped to `lat: 38.897675, lng: -77.03653`. State `"District of Columbia"` mapped to `"DC"`. Returns `HTTP 200 OK`. |
| 8 | Resolve | `"742 Evergreen Terrace Apt 4B, Springfield, OR 97477"` | Apartment unit parsed into `unitNumber: "Apt 4B"`. Primary `streetName` isolated as `"Evergreen Terrace"`. Returns `HTTP 200 OK`. |
| 9 | Resolve | `"500 7th Ave Floor 12, New York, NY 10018"` | Floor designator parsed into `unitNumber: "Floor 12"`, `streetNumber: "500"`, `streetName: "7th Ave"`. Returns `HTTP 200 OK`. |
| 10 | Resolve | `"800 N Michigan Ave #3201, Chicago, IL 60611"` | Hash designator parsed into `unitNumber: "#3201"`. Street name preserved. Returns `HTTP 200 OK`. |
| 11 | Resolve | `"1600 Pennsylvania Avenue NW, Washington, DC 20500-0003"` | ZIP+4 formatted address. Splits into `zip5: "20500"` and `zip4: "0003"`. Returns `HTTP 200 OK`. |
| 12 | Resolve | `"120-05 84th Ave, Kew Gardens, NY 11415"` | Queens hyphenated house number. Normalizer preserves `"120-05"` as valid `streetNumber` and parses `"84th Ave"` as `streetName`. Returns `HTTP 200 OK`. |
| 13 | Resolve | `"123 1/2 Maple St, Seattle, WA 98101"` | Fractional building number. Normalizer preserves `"123 1/2"` as `streetNumber`. Returns `HTTP 200 OK`. |
| 14 | Resolve | `"14520 County Road 42, Joplin, MO 64801"` | Rural county road address with building number. Geocodes successfully; returns `HTTP 200 OK`. |
| 15 | Resolve | `"100 King St W, Toronto, ON M5X 1A9"` | Canadian address. Country resolved as `CA`. Coordinates fall outside US bounding box. Route returns `HTTP 400 Bad Request` with `code: "OUT_OF_COVERAGE_AREA"`. |
| 16 | Resolve | `"99999 Fantasy Road, Nowhere, ZZ 00000"` | Nonexistent address returns 0 matches on Census, Photon, and Nominatim. Route returns `HTTP 400 Bad Request` with `code: "ADDRESS_NOT_RESOLVED"`. |
| 17 | Resolve | Census Bureau API times out (> 2.5s) | Route cancels Census request via `AbortController` and falls back seamlessly to Komoot Photon. Resolves address within SLA; returns `HTTP 200 OK` with `X-Geocoder-Source: photon`. |
| 18 | Resolve | Census Bureau returns HTTP 503 Service Unavailable | Route intercepts HTTP 503, logs diagnostic warning, and cascades immediately to Komoot Photon. Returns `HTTP 200 OK`. |
| 19 | Resolve | Repeat query for same address within 1 hour | Request hits L1 in-memory cache. Resolves in `< 5ms`. Returns `HTTP 200 OK` with `X-Geocoder-Source: cache`. |
| 20 | Resolve | Query with `fresh=true` | Request bypasses L1 cache and queries upstream geocoding cascade directly. |
| 21 | Resolve | Missing `address` query parameter | Route returns `HTTP 400 Bad Request` with `code: "MISSING_ADDRESS_PARAMETER"`. |
| 22 | Resolve | `address` query string has 3 characters (`"abc"`) | Length validation fails (<5 chars). Route returns `HTTP 400 Bad Request` with `code: "ADDRESS_TOO_SHORT"`. |
| 23 | Suggest | `GET /api/geocode/suggest?q=1` | Length < 3. Route immediately returns `HTTP 200 OK` with `suggestions: []` without calling upstream APIs. |
| 24 | Suggest | `GET /api/geocode/suggest?q=1600+Penn` | Length >= 3. Route calls Komoot Photon with US bounding box filter. Returns `HTTP 200 OK` with array of matching suggestions. |
| 25 | Suggest | `GET /api/geocode/suggest?q=` (empty) | Route returns `HTTP 400 Bad Request` with `code: "MISSING_QUERY_PARAMETER"`. |
| 26 | Suggest | `GET /api/geocode/suggest?q=...` (> 256 characters) | Route returns `HTTP 400 Bad Request` with `code: "QUERY_TOO_LONG"`. |
| 27 | Suggest | `GET /api/geocode/suggest?q=1600+Main&limit=50` | `limit` exceeds max allowed (10). Route clamps limit to `10` and returns maximum 10 suggestions. |
| 28 | Suggest | Komoot Photon API returns HTTP 429 Too Many Requests | Route intercepts 429 and falls back to OSM Nominatim. Returns `HTTP 200 OK` with suggestions from Nominatim. |
| 29 | Suggest | Rapid typing triggers 5 requests within 200ms | Client-side debouncer absorbs first 4 keystrokes; only the 5th request is dispatched. `AbortController` cancels any stale in-flight response. |
| 30 | Resolve | Decimal coordinate inversion test: `coordinates.x = -77.0365, coordinates.y = 38.8976` | Normalizer enforces `lng = coordinates.x` and `lat = coordinates.y`, validating `lat > 0` and `lng < 0` for continental US. |

---

## 7. Verification Method

To verify these specifications independently:

1. **Unit Testing (`vitest`)**:
   - `tests/unit/geocoding/normalizer.test.ts`:
     - Test PO Box rejection regex across Edge Cases 1-4.
     - Test missing street number rejection across Edge Cases 5-6.
     - Test apartment unit extraction across Edge Cases 8-10.
     - Test ZIP+4 deconstruction across Edge Case 11.
     - Test Queens hyphenated and half numbers across Edge Cases 12-13.
     - Test state code normalization dictionary.
     - Test Census coordinate inversion protection (`x` as lng, `y` as lat).
2. **Integration Testing (`tests/integration/api-geocode.test.ts`)**:
   - Verify `GET /api/geocode/suggest`:
     - Test `q` length < 3 returns 200 with `suggestions: []`.
     - Test empty `q` returns 400 with `MISSING_QUERY_PARAMETER`.
     - Test valid `q="1600 Pennsylvania Ave"` returns 200 with populated suggestions array.
     - Test `limit=50` clamps to 10 suggestions.
   - Verify `GET /api/geocode/resolve`:
     - Test physical address returns 200 with valid `NormalizedAddress`.
     - Test PO Box returns 400 with `PO_BOX_NOT_SUPPORTED`.
     - Test missing street number returns 400 with `STREET_NUMBER_REQUIRED`.
     - Test out-of-US address returns 400 with `OUT_OF_COVERAGE_AREA`.
     - Test non-existent address returns 400 with `ADDRESS_NOT_RESOLVED`.
     - Test repeat query returns cached response in $< 10$ms.
