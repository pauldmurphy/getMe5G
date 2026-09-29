# Technical Analysis: Address Normalizer Code Fixes

**Agent**: `explorer_m1_r2_1`  
**Target File**: `src/lib/geocoding/normalizer.ts`  
**Milestone**: M1 (Round 2)  
**Date**: 2026-09-29T22:21:00Z  
**Status**: Investigation Complete — Fixes Formulated & Verified (100% Pass)

---

## 1. Executive Summary

Empirical review by `reviewer_m1_1` and adversarial stress-testing by `challenger_m1_1` identified critical defects in `src/lib/geocoding/normalizer.ts`:
1. `UNIT_REGEX` failed to match `#304` and `#5` when preceded by whitespace or comma, failing `tests/unit/geocoding/normalizer.test.ts:72`.
2. Prefix ordering in `UNIT_REGEX` evaluated `FL` before `FLOOR`, causing `"Floor 14"` to be parsed as unit `"Fl oor"` with lingering street corruption.
3. Suffix abbreviation in `standardizeStreetName` was position-agnostic, causing proper street names such as `"Court Street"`, `"Parkway Lane"`, and `"Terrace Avenue"` to be mangled into `"Ct St"`, `"Pkwy Ln"`, and `"Ter Ave"`.
4. Comma-separated addresses (e.g. `"123 Main St, Apt 4B, New York, NY 10001"`) assigned the secondary unit (`"Apt 4B"`) to `city`, and polluted `state` with `"NEW YORK NY"`.
5. Missing ZIP handling in `AddressNormalizer.parseZip` returned `zipInput.trim()` when fewer than 5 digits were present, corrupting `zip5` with the state abbreviation (e.g. `zip5: "NY"`).
6. `PO_BOX_REGEX` failed to detect the spaced variant `"P BOX 10"`, allowing PO Boxes through or throwing `MissingStreetNumberError` instead of `PoBoxError`.

All 6 issues (plus security sanitization for non-script HTML vectors and unclosed SQL comments) have been analyzed, resolved, and verified using Python test runners matching ECMAScript regex semantics against all 69 unit tests and 36 adversarial stress tests with 0 failures.

---

## 2. Root Cause Analysis & Exact Fixes

### 2.1 Issue 1 & 2: `UNIT_REGEX` Word Boundary & Prefix Ordering

#### Root Cause
In `src/lib/geocoding/normalizer.ts:142`:
```typescript
const UNIT_REGEX = /(?:,\s*)?\b(?:(APT|APARTMENT|SUITE|STE|UNIT|BLDG|BUILDING|FL|FLOOR|RM|ROOM|LOT|DEPT)\.?\s*([A-Za-z0-9\-#\/]+)|#\s*([A-Za-z0-9\-]+))\b/i;
```
1. **Word Boundary on `#`**: In ECMAScript/PCRE, a word boundary `\b` asserts `(?<=\w)(?!\w)|(?<!\w)(?=\w)`. The `#` character is `\W`. In `"100 Pine St #304"`, the character preceding `#` is `' '` (space), which is `\W`. Because both space and `#` are `\W`, there is no word boundary transition. Consequently, `\b#` never matches when preceded by space or comma.
2. **Prefix Ordering**: In `(APT|APARTMENT|...|FL|FLOOR...)`, `FL` is listed before `FLOOR`. Because the trailing delimiter `\.?\s*` allows zero length, the regex engine greedily matches `FL` against `"Floor"`, capturing `"Fl"` as group 1 and `"oor"` as group 2 (the unit number), leaving `"  14"` on the street line.
3. Similar prefix shadowing exists for `APT` vs `APARTMENT`, `STE` vs `SUITE`, `BLDG` vs `BUILDING`, and `RM` vs `ROOM`.

#### Exact Code Fix
Relocate `\b` inside the first group to only enforce word boundaries around alphabetic keywords, append `\b` after the keyword list, and place longer prefixes before shorter prefixes:
```typescript
const UNIT_REGEX = /(?:,\s*)?(?:\b(APARTMENT|APT|SUITE|STE|UNIT|BUILDING|BLDG|FLOOR|FL|ROOM|RM|LOT|DEPT)\b\.?\s*([A-Za-z0-9\-#\/]+)|#\s*([A-Za-z0-9\-]+))\b/i;
```

---

### 2.2 Issue 3: Street Suffix Replacement in `standardizeStreetName`

#### Root Cause
In `src/lib/geocoding/normalizer.ts:447-462`:
```typescript
public static standardizeStreetName(streetName: string): string {
  const tokens = streetName.trim().split(/\s+/);
  const normalizedTokens = tokens.map((token, index) => {
    const lower = token.toLowerCase().replace(/[.,]/g, '');
    if ((index === 0 || index === tokens.length - 1) && DIRECTIONAL_MAP[lower]) {
      return DIRECTIONAL_MAP[lower];
    }
    if (STREET_SUFFIX_MAP[lower]) {
      return STREET_SUFFIX_MAP[lower];
    }
    return token.charAt(0).toUpperCase() + token.slice(1);
  });
  return normalizedTokens.join(' ');
}
```
Every token present in `STREET_SUFFIX_MAP` was unconditionally replaced regardless of its position in the street name. For `"Court Street"`, `"Court"` became `"Ct"` and `"Street"` became `"St"`, yielding `"Ct St"`.

#### Exact Code Fix
Per USPS Publication 28 standards, street suffixes appear exclusively at the terminal position, or the penultimate position if followed by a cardinal post-directional (e.g. `"Avenue NW"`):
```typescript
  public static standardizeStreetName(streetName: string): string {
    const tokens = streetName.trim().split(/\s+/);
    const len = tokens.length;
    const hasPostDirectional = len > 1 && Boolean(DIRECTIONAL_MAP[tokens[len - 1].toLowerCase().replace(/[.,]/g, '')]);
    const suffixIndex = hasPostDirectional ? len - 2 : len - 1;

    const normalizedTokens = tokens.map((token, index) => {
      const lower = token.toLowerCase().replace(/[.,]/g, '');
      // Check directional (at beginning or end of street name)
      if ((index === 0 || index === len - 1) && DIRECTIONAL_MAP[lower]) {
        return DIRECTIONAL_MAP[lower];
      }
      // Check street suffix only at designated suffix position
      if (index === suffixIndex && STREET_SUFFIX_MAP[lower]) {
        return STREET_SUFFIX_MAP[lower];
      }
      return token.charAt(0).toUpperCase() + token.slice(1);
    });

    return normalizedTokens.join(' ');
  }
```

---

### 2.3 Issue 4: Comma-Separated Unit Parsing in `normalizeAddress`

#### Root Cause
In `src/lib/geocoding/normalizer.ts:251-263`:
```typescript
const segments = cleaned.split(',').map((s) => s.trim().replace(/\s+/g, ' ')).filter(Boolean);
let rawStreet = segments[0] || '';
let city = '';
let rawStateZip = '';

if (segments.length >= 3) {
  city = segments[1];
  rawStateZip = segments.slice(2).join(' ');
}
```
When an address is entered in standard multi-line postal format (`"123 Main St, Apt 4B, New York, NY 10001"`), `segments` has 4 items: `["123 Main St", "Apt 4B", "New York", "NY 10001"]`. The naive index mapping assigned `segments[1]` (`"Apt 4B"`) to `city`, and `segments.slice(2)` (`"New York NY 10001"`) to `rawStateZip`.

#### Exact Code Fix
Inspect subsequent segments after the street line. If `remainingSegments[0]` represents a standalone unit indicator (i.e. `candidateUnit.unitNumber` is non-null and `candidateUnit.baseStreet === ''`), consume it as `unitNumber` before assigning `city` and `rawStateZip`:
```typescript
  // Parse comma-delimited segments or freeform string
  const segments = cleaned.split(',').map((s) => s.trim().replace(/\s+/g, ' ')).filter(Boolean);
  if (!segments.length) {
    throw new AddressValidationError('Please enter a valid street address.');
  }

  const remainingSegments = [...segments];
  let rawStreet = remainingSegments.shift() || '';

  // Extract unit if present on the street line
  const extractedUnit = extractUnitNumber(rawStreet);
  rawStreet = extractedUnit.baseStreet;
  let unitNumber: string | null = extractedUnit.unitNumber;

  // Check if subsequent comma segment is a standalone unit (e.g. "123 Main St, Apt 4B, New York, NY 10001")
  if (remainingSegments.length > 0) {
    const candidateUnit = extractUnitNumber(remainingSegments[0]);
    if (candidateUnit.unitNumber && candidateUnit.baseStreet === '') {
      if (!unitNumber) {
        unitNumber = candidateUnit.unitNumber;
      }
      remainingSegments.shift();
    }
  }

  let city = '';
  let rawStateZip = '';

  if (remainingSegments.length >= 2) {
    city = remainingSegments[0];
    rawStateZip = remainingSegments.slice(1).join(' ');
  } else if (remainingSegments.length === 1) {
    rawStateZip = remainingSegments[0];
  }
```
Also update the fallback city extractor to use `remainingSegments.length === 1`:
```typescript
  // If city was not extracted from comma segments, attempt fallback parsing
  if (!city && remainingSegments.length === 1) {
    const words = remainingSegments[0].split(' ').filter(Boolean);
    if (words.length > 2) {
      city = words.slice(0, words.length - 2).join(' ');
      state = normalizeState(words[words.length - 2]);
    }
  }
```

---

### 2.4 Issue 5: Missing ZIP Handling in `parseZip`

#### Root Cause
In `src/lib/geocoding/normalizer.ts:380-392`:
```typescript
const match = zipInput.trim().match(ZIP_REGEX);
if (!match) {
  const digits = zipInput.replace(/\D/g, '');
  if (digits.length >= 5) {
    return {
      zip5: digits.slice(0, 5),
      zip4: digits.length >= 9 ? digits.slice(5, 9) : null,
    };
  }
  return { zip5: zipInput.trim(), zip4: null }; // <--- BUG!
}
```
When ZIP is omitted (e.g. `"123 Main St, New York, NY"`), the remaining state string `"NY"` was passed to `parseZip`. Because `"NY"` has 0 digits, line 390 returned `{ zip5: 'NY', zip4: null }`, setting `zip5: 'NY'` and creating duplicates like `"123 Main St, New York, NY NY"`.

#### Exact Code Fix
When fewer than 5 digits are found and `ZIP_REGEX` fails, return `{ zip5: '', zip4: null }`:
```typescript
  public static parseZip(zipInput: string): { zip5: string; zip4: string | null } {
    if (!zipInput) {
      return { zip5: '', zip4: null };
    }
    const match = zipInput.trim().match(ZIP_REGEX);
    if (!match) {
      const digits = zipInput.replace(/\D/g, '');
      if (digits.length >= 5) {
        return {
          zip5: digits.slice(0, 5),
          zip4: digits.length >= 9 ? digits.slice(5, 9) : null,
        };
      }
      return { zip5: '', zip4: null };
    }

    return {
      zip5: match[1],
      zip4: match[2] || null,
    };
  }
```

---

### 2.5 Issue 6: `PO_BOX_REGEX` Missing "P BOX 10"

#### Root Cause
In `src/lib/geocoding/normalizer.ts:141`:
```typescript
export const PO_BOX_REGEX = /\b(?:P(?:OST)?\.?\s*O(?:FFICE)?\.?\s*BOX|P\.?\s*O\.?\s*B(?:\.|\b)|POST\s+OFFICE\s+DRAWER|PBOX)\b/i;
```
Branch 1 strictly required the letter `O` (`O(?:FFICE)?`), and Branch 4 required unspaced `PBOX`. Therefore `"P BOX 10"` did not match any branch.

#### Exact Code Fix
Make the `O` component optional in the first branch:
```typescript
export const PO_BOX_REGEX = /\b(?:P(?:OST)?\.?\s*(?:O(?:FFICE)?\.?\s*)?BOX|P\.?\s*O\.?\s*B(?:\.|\b)|POST\s+OFFICE\s+DRAWER|PBOX)\b/i;
```
Additionally, check `streetNumber` in `normalizeFromComponents`:
```typescript
if (this.isPoBox(rawStreetName) || this.isPoBox(components.rawAddress || '') || this.isPoBox(streetNumber)) {
  throw new PoBoxError(rawStreetName || components.rawAddress || streetNumber);
}
```

---

### 2.6 Security Sanitization Hardening

#### Improvements Applied
In `src/lib/geocoding/normalizer.ts:230-234`:
1. Strips all HTML elements (`/<[^>]+>/g`) after stripping `<script>...</script>` blocks to neutralize `<img>`, `<svg>`, and event handler injection vectors.
2. Expands SQL injection removal to terminate on `;` or end-of-string in addition to `--`:
```typescript
  // Sanitize script tags (XSS prevention)
  let cleaned = input.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '').trim();
  // Strip any remaining HTML tags (e.g. img onerror vectors)
  cleaned = cleaned.replace(/<[^>]+>/g, '').trim();

  // Sanitize SQL injection meta-characters
  cleaned = cleaned.replace(/['";]+\s*(?:DROP|SELECT|INSERT|DELETE|UPDATE|ALTER|CREATE|EXEC|UNION)[\s\S]*?(?:--|;|$)/gi, '').trim();
```

---

## 3. Verification & Empirical Test Results

Testing was conducted using two independent suites:
1. `.agents/teamwork/reviewer_m1_1/test_runner.py` (running all test cases from `tests/unit/geocoding/normalizer.test.ts`)
2. `tests/stress/normalizer_stress.py` (running all 36 adversarial boundary conditions)

| Test Suite | Pre-Fix Status | Post-Fix Status | Result |
|---|---|---|---|
| Reviewer Unit Suite (`normalizer.test.ts`) | 67 passed, 2 failed | **69 passed, 0 failed** | **100% PASS** |
| Challenger Adversarial Suite (`normalizer_stress.py`) | 28 passed, 8 failed | **36 passed, 0 failed** | **100% PASS** |

### Key Test Case Verifications
- `extractUnitNumber('100 Pine St #304')`: `unitNumber: "#304"`, `baseStreet: "100 Pine St"` (PASS)
- `extractUnitNumber('100 Pine St #5')`: `unitNumber: "#5"`, `baseStreet: "100 Pine St"` (PASS)
- `extractUnitNumber('101 Ocean Ave Floor 14')`: `unitNumber: "Fl 14"`, `baseStreet: "101 Ocean Ave"` (PASS)
- `standardizeStreetName('Court Street')`: `"Court St"` (PASS)
- `standardizeStreetName('Court Street NW')`: `"Court St NW"` (PASS)
- `standardizeStreetName('Parkway Lane')`: `"Parkway Ln"` (PASS)
- `normalizeAddress('123 Main St, Apt 4B, New York, NY 10001')`: `unitNumber: "Apt 4B"`, `city: "New York"`, `state: "NY"`, `zip5: "10001"` (PASS)
- `normalizeAddress('100 Pine St, Ste 100, San Francisco, CA 94111')`: `unitNumber: "Suite 100"`, `city: "San Francisco"`, `state: "CA"`, `zip5: "94111"` (PASS)
- `normalizeAddress('123 Main St, New York, NY')`: `state: "NY"`, `zip5: ""`, `formattedAddress: "123 Main St, New York, NY"` (PASS)
- `isPoBox('P BOX 10')`: `true` (PASS)
- `normalizeAddress('P BOX 10, Dallas, TX 75201')`: throws `PoBoxError` (PASS)

---

## 4. Artifacts Produced

The following files are available in `.agents/teamwork/explorer_m1_r2_1/`:
1. `proposed_normalizer.ts`: Full drop-in replacement file for `src/lib/geocoding/normalizer.ts`.
2. `normalizer.patch`: Unified diff patch against `src/lib/geocoding/normalizer.ts`.
3. `verify_patch.py`: Complete test harness verifying 69/69 unit tests and 36/36 stress tests.
4. `analysis.md`: This comprehensive analysis document.
5. `handoff.md`: 5-component formal handoff report.
