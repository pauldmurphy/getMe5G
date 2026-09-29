# Adversarial Stress Testing & Empirical Challenge Report

**Subagent**: `challenger_m1_1` (`teamwork_preview_challenger`)  
**Parent / Recipient**: `097744dd-87b6-414e-a580-658af286e0dd` (`parent`)  
**Target Code**: `src/lib/geocoding/normalizer.ts`  
**Milestone**: M1 (Address Intake & Pluggable Geocoding System)  
**Date**: 2026-09-29T22:15:45Z  
**Verdict**: **`CHALLENGE_FAILED`**  

---

## 1. Observation

Adversarial stress-testing was executed against `src/lib/geocoding/normalizer.ts` across four mandated categories:
1. PO Box variations and non-rejection of "Boxwood Ln" / "Boxford St".
2. Weird/unusual addresses: Fractional numbers ("123 1/2 Main St"), grid addresses ("N12W34560 Lake Dr"), highway routes ("Route 66"), unit numbers ("Apt 4B", "Ste 100", "#5").
3. Security/Injection payloads: SQL injection syntax (`'; DROP TABLE brands;--`), XSS script tags (`<script>alert(1)</script>`), buffer length limits.
4. Missing components: Missing street number, missing zip code, missing city/state.

Direct observations and execution outputs:

### 1.1 PO Box Detection (`src/lib/geocoding/normalizer.ts:141`)
- Regex definition:
  ```typescript
  export const PO_BOX_REGEX = /\b(?:P(?:OST)?\.?\s*O(?:FFICE)?\.?\s*BOX|P\.?\s*O\.?\s*B(?:\.|\b)|POST\s+OFFICE\s+DRAWER|PBOX)\b/i;
  ```
- Command executed:
  ```bash
  python3 -c '
  import re
  r = re.compile(r"\b(?:P(?:OST)?\.?\s*O(?:FFICE)?\.?\s*BOX|P\.?\s*O\.?\s*B(?:\.|\b)|POST\s+OFFICE\s+DRAWER|PBOX)\b", re.IGNORECASE)
  print(r.search("P BOX 10"))
  '
  ```
  Result: `None`.
- Passing `"P BOX 10, Dallas, TX 75201"` to `normalizeAddress()` throws `MissingStreetNumberError` rather than `PoBoxError`.
- Passing `{ streetNumber: '10', streetName: 'P BOX', city: 'Dallas', state: 'TX', zip5: '75201' }` to `AddressNormalizer.normalizeFromComponents()` produces `formattedAddress: "10 P Box, Dallas, TX 75201"` without raising `PoBoxError`.
- Non-rejection cases verified correctly: `"123 Boxwood Ln, Houston, TX 77001"` and `"100 Boxford St, Boston, MA 02108"` both returned `false` (not flagged).

### 1.2 Unit Number Extraction with `#` Symbol (`src/lib/geocoding/normalizer.ts:142`)
- Regex definition:
  ```typescript
  const UNIT_REGEX = /(?:,\s*)?\b(?:(APT|APARTMENT|SUITE|STE|UNIT|BLDG|BUILDING|FL|FLOOR|RM|ROOM|LOT|DEPT)\.?\s*([A-Za-z0-9\-#\/]+)|#\s*([A-Za-z0-9\-]+))\b/i;
  ```
- Command executed:
  ```bash
  python3 -c '
  import re
  r = re.compile(r"(?:,\s*)?\b(?:(APT|APARTMENT|SUITE|STE|UNIT|BLDG|BUILDING|FL|FLOOR|RM|ROOM|LOT|DEPT)\.?\s*([A-Za-z0-9\-#\/]+)|#\s*([A-Za-z0-9\-]+))\b", re.IGNORECASE)
  print(r.search("100 Pine St #304"))
  print(r.search("100 Pine St #5"))
  '
  ```
  Result: `None` for both inputs.
- Consequence: In `extractUnitNumber('100 Pine St #304')`, `unitNumber` is returned as `null` and `baseStreet` remains `'100 Pine St #304'`.
- This invalidates the unit test in `tests/unit/geocoding/normalizer.test.ts:73` (`it('should extract "#" unit symbol indicator')`).

### 1.3 Comma-Delimited Secondary Unit Corruption (`src/lib/geocoding/normalizer.ts:251-260`)
- Code:
  ```typescript
  const segments = cleaned.split(',').map((s) => s.trim().replace(/\s+/g, ' ')).filter(Boolean);
  let rawStreet = segments[0] || '';
  let city = '';
  let rawStateZip = '';

  if (segments.length >= 3) {
    city = segments[1];
    rawStateZip = segments.slice(2).join(' ');
  } else if (segments.length === 2) {
    rawStateZip = segments[1];
  }
  ```
- Command executed:
  ```bash
  python3 tests/stress/normalizer_stress.py
  ```
  Result for input `"123 Main St, Apt 4B, New York, NY 10001"`:
  - `city`: `'Apt 4B'`
  - `state`: `'NEW YORK NY'`
  - `unitNumber`: `null`
  - `formattedAddress`: `'123 Main St, Apt 4B, NEW YORK NY 10001'`
  Result for input `"100 Pine St, Ste 100, San Francisco, CA 94111"`:
  - `city`: `'Ste 100'`
  - `state`: `'SAN FRANCISCO CA'`
  - `unitNumber`: `null`

### 1.4 State Pollution in Missing ZIP Code Handling (`src/lib/geocoding/normalizer.ts:380-392`)
- Code:
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
      return { zip5: zipInput.trim(), zip4: null }; // <--- Line 390
    }
    ...
  ```
- Command executed:
  ```bash
  python3 -c '
  from tests.stress.normalizer_stress import normalize_address
  res = normalize_address("123 Main St, New York, NY")
  print(res)
  '
  ```
  Result:
  `{'streetNumber': '123', 'streetName': 'Main St', 'unitNumber': None, 'city': 'New York', 'state': 'NY', 'zip5': 'NY', 'zip4': None, 'formattedAddress': '123 Main St, New York, NY NY', ...}`
  `zip5` is assigned `'NY'`, corrupting the structured postal record and duplicating the state in `formattedAddress`.

### 1.5 Security & Injection Sanitization (`src/lib/geocoding/normalizer.ts:230-234`)
- Code:
  ```typescript
  let cleaned = input.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '').trim();
  cleaned = cleaned.replace(/['";]\s*(?:DROP|SELECT|INSERT|DELETE|UPDATE|ALTER|CREATE|EXEC|UNION)[\s\S]*?--/gi, '').trim();
  ```
- Result:
  - XSS payload with `<img>` tag: `"123 Main St <img src=x onerror=alert(1)>, Miami, FL 33101"` results in `streetName: "Main St <img Src=x Onerror=alert(1)>"`. The script-only regex fails to sanitize alternative HTML/DOM injection vectors.
  - SQL injection payload without `--` marker: `"123 Main St'; DROP TABLE brands;, Boston, MA 02108"` leaves the raw SQL injection fragment intact inside `streetName`.

### 1.6 Successful Adversarial Validations (Robust Areas)
- Fractional house numbers (`"123 1/2 Maple St"`): Correctly parsed as `streetNumber: "123 1/2"`, `streetName: "Maple St"`.
- Wisconsin grid coordinates (`"N12W34560 Lake Dr"`): Correctly parsed as `streetNumber: "N12W34560"`, `streetName: "Lake Dr"`.
- Rural route boxes (`"Route 1 Box 42, Big Piney, WY 83113"`): Correctly parsed as `streetName: "Route 1"`, `streetNumber: "Box 42"`.
- Highway route without house number (`"Route 66, Flagstaff, AZ 86001"`): Correctly rejected with `MissingStreetNumberError`.
- Highway route with house number (`"100 Route 66, Flagstaff, AZ 86001"`): Correctly parsed.
- Empty / whitespace-only inputs: Throws `AddressValidationError`.
- Buffer limit test (50,000 characters): Completed in 0.0029 seconds without catastrophic backtracking.

---

## 2. Logic Chain

1. **PO Box Detection**:
   - `PO_BOX_REGEX` defines branches: `P(?:OST)?\.?\s*O(?:FFICE)?\.?\s*BOX`, `P\.?\s*O\.?\s*B(?:\.|\b)`, `POST\s+OFFICE\s+DRAWER`, and `PBOX`.
   - The first branch requires letter `O` (`O(?:FFICE)?`), and the fourth branch requires `PBOX` without spaces.
   - Therefore, the spaced variant `"P BOX 10"` satisfies none of the branches and returns `false`.
   - In `normalizeAddress()`, this causes an incorrect `MissingStreetNumberError` rather than `PoBoxError`, and in `AddressNormalizer.normalizeFromComponents()`, it permits `"10 P Box"` to pass into production data, violating Requirement 1.

2. **Unit Symbol Extraction**:
   - In `UNIT_REGEX`, `\b` is placed outside the alternation: `\b(?:(APT|...)|#\s*([A-Za-z0-9\-]+))\b`.
   - In standard regular expressions, `#` is a non-word character (`\W`). The character preceding `#` in `"100 Pine St #304"` is a space (`\W`).
   - A word boundary `\b` requires a transition between `\w` and `\W`. Between a space (`\W`) and `#` (`\W`), no word boundary exists.
   - Consequently, `\b#` cannot match unless `#` is immediately glued to a word character (e.g. `St#304`). All standard space-separated `#5` or `#304` unit notations are completely missed, breaking Requirement 2.

3. **Comma-Delimited Segment Parsing**:
   - The parser assumes that whenever `segments.length >= 3`, `segments[1]` is the city and `segments.slice(2)` is the state/ZIP.
   - When users enter addresses in common multi-line postal format (`Line 1: 123 Main St, Line 2: Apt 4B, Line 3: New York, Line 4: NY 10001`), `segments[1]` is `'Apt 4B'`, `segments[2]` is `'New York'`, and `segments[3]` is `'NY 10001'`.
   - As a result, `'Apt 4B'` is assigned to `city`, and `'New York NY 10001'` is assigned to `rawStateZip`, yielding `city: 'Apt 4B'` and `state: 'NEW YORK NY'`, causing severe postal data corruption.

4. **Missing ZIP Code Fallback**:
   - In `AddressNormalizer.parseZip(zipInput)`, line 390 returns `{ zip5: zipInput.trim(), zip4: null }` when fewer than 5 digits are found.
   - When an address omits a ZIP code (e.g. `'123 Main St, New York, NY'`), the remaining token passed to `parseZip` is `'NY'`.
   - Instead of recognizing that no ZIP was supplied, line 390 sets `zip5 = 'NY'`, which duplicates the state code into the 5-digit ZIP code column.

5. **Security Sanitization**:
   - Regex sanitizers target narrow substrings (`<script...>` and `DROP...--`). Attackers can bypass these filters with event handlers (`<img onerror>`) or SQL constructs without double dashes.

---

## 3. Caveats

- Node.js is not present in the container path, preventing direct `npx vitest run` execution from this shell.
- Verification was conducted empirically by:
  1. Executing Python and Perl test harnesses matching ECMAScript regex and string semantics.
  2. Directly reading `src/lib/geocoding/normalizer.ts` and extracting the verbatim regular expressions into automated test scripts (`tests/stress/normalizer_stress.py`).
  3. Authoring the complete TypeScript test specification in `tests/unit/geocoding/normalizer.adversarial.test.ts`.

---

## 4. Conclusion

**Verdict: `CHALLENGE_FAILED`**

The normalizer logic in `src/lib/geocoding/normalizer.ts` has 8 confirmed empirical test failures across core requirements:
1. Fails to identify `"P BOX 10"` as a PO Box.
2. Fails to extract unit designations with `#` symbols (`#5`, `#304`) due to misplaced `\b` anchor in `UNIT_REGEX`.
3. Corrupts `city` and `state` when addresses contain comma-separated secondary units (`123 Main St, Apt 4B, New York, NY 10001`).
4. Corrupts `zip5` with state strings (`zip5: "NY"`) when ZIP code is omitted.
5. Incomplete sanitization of XSS `<img onerror>` tags and SQL injection payloads lacking `--`.

### Required Mitigations for Worker:
1. Update `PO_BOX_REGEX` in `src/lib/geocoding/normalizer.ts`:
   ```typescript
   export const PO_BOX_REGEX = /\b(?:P(?:OST)?\.?\s*(?:O(?:FFICE)?\.?\s*)?BOX|P\.?\s*O\.?\s*B(?:\.|\b)|POST\s+OFFICE\s+DRAWER|PBOX)\b/i;
   ```
2. Move `\b` inside `UNIT_REGEX` to only precede word-character unit tokens:
   ```typescript
   const UNIT_REGEX = /(?:,\s*)?(?:\b(APT|APARTMENT|SUITE|STE|UNIT|BLDG|BUILDING|FL|FLOOR|RM|ROOM|LOT|DEPT)\.?\s*([A-Za-z0-9\-#\/]+)|#\s*([A-Za-z0-9\-]+))\b/i;
   ```
3. In `normalizeAddress()`, inspect segments for unit designations before assuming segment 1 is the city, or support 4-part segments (`[street, unit, city, state_zip]`).
4. In `AddressNormalizer.parseZip()`, return `{ zip5: '', zip4: null }` if fewer than 5 digits are present rather than returning `zipInput.trim()`.
5. Strip all HTML tags `/<[^>]*>/g` for XSS prevention.

---

## 5. Verification Method

To independently verify these findings:

1. **Run the Stress Test Suite**:
   ```bash
   python3 tests/stress/normalizer_stress.py
   ```
   *Observed Output*: Exactly 28 tests pass and 8 tests fail with explicit failure messages and values.

2. **Verify Verbatim Extracted Regexes**:
   ```bash
   python3 -c "
   with open('src/lib/geocoding/normalizer.ts') as f:
       c = f.read()
   import re
   po = re.search(r'export const PO_BOX_REGEX = /(.*?)/i;', c).group(1)
   unit = re.search(r'const UNIT_REGEX = /(.*?)/i;', c).group(1)
   print('P BOX match:', bool(re.search(po, 'P BOX 10', re.I)))
   print('#304 match:', bool(re.search(unit, '100 Pine St #304', re.I)))
   "
   ```
   *Expected Output*: Both print `False`.

3. **Vitest Adversarial Suite** (when Node is available):
   ```bash
   npx vitest run tests/unit/geocoding/normalizer.adversarial.test.ts
   ```
