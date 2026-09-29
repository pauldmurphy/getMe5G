import { NextRequest, NextResponse } from 'next/server';
import { geocodingService } from '@/lib/geocoding/service';
import { AddressNormalizer } from '@/lib/geocoding/normalizer';
import {
  AddressNotFoundError,
  AddressValidationError,
  GeocodingError,
  InvalidCoordinatesError,
  MissingStreetNumberError,
  OutOfBoundsError,
  PoBoxError,
} from '@/lib/geocoding/types';

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const rawAddress = searchParams.get('address');
  const latParam = searchParams.get('lat');
  const lngParam = searchParams.get('lng');
  const fresh = searchParams.get('fresh') === 'true' || searchParams.get('fresh') === '1';

  // Rule: Must provide address or coordinates
  if (!rawAddress && (latParam === null || lngParam === null)) {
    return NextResponse.json(
      {
        status: 'error',
        code: 'MISSING_ADDRESS_PARAMETER',
        message: "Query parameter 'address' or 'lat'/'lng' is required.",
        details: {
          parameter: 'address',
        },
      },
      { status: 400 }
    );
  }

  // Handle address resolution
  if (rawAddress !== null) {
    const address = rawAddress.trim();

    // Length checks
    if (address.length < 5) {
      return NextResponse.json(
        {
          status: 'error',
          code: 'ADDRESS_TOO_SHORT',
          message: 'Address string must be at least 5 characters.',
          details: {
            address,
            minLength: 5,
          },
        },
        { status: 400 }
      );
    }

    if (address.length > 500) {
      return NextResponse.json(
        {
          status: 'error',
          code: 'ADDRESS_TOO_LONG',
          message: 'Address string exceeds maximum length of 500 characters.',
          details: {
            address,
            maxLength: 500,
          },
        },
        { status: 400 }
      );
    }

    // PO Box rejection check
    if (AddressNormalizer.isPoBox(address)) {
      return NextResponse.json(
        {
          status: 'error',
          code: 'PO_BOX_NOT_SUPPORTED',
          message:
            'Fixed wireless home internet requires a physical residential street address. PO Boxes are not eligible.',
          details: {
            submittedAddress: address,
            field: 'address',
            reason:
              'PO Boxes do not possess discrete physical rooftop coordinates for cellular RF line-of-sight analysis or home gateway delivery.',
          },
        },
        { status: 400 }
      );
    }

    try {
      const normalized = await geocodingService.resolve(address, { fresh });
      return NextResponse.json(
        {
          status: 'success',
          address: normalized,
        },
        {
          status: 200,
          headers: {
            'Cache-Control': 'public, s-maxage=3600, max-age=1800, stale-while-revalidate=86400',
            'X-Geocoder-Source': normalized.geocoderSource || 'census',
          },
        }
      );
    } catch (err: unknown) {
      return handleGeocodeError(err, address);
    }
  }

  // Handle reverse geocoding via lat / lng
  const lat = parseFloat(latParam!);
  const lng = parseFloat(lngParam!);

  if (isNaN(lat) || isNaN(lng) || lat < -90 || lat > 90 || lng < -180 || lng > 180) {
    return NextResponse.json(
      {
        status: 'error',
        code: 'INVALID_COORDINATES',
        message: 'Provided latitude or longitude coordinate is outside valid geographical boundaries.',
        details: {
          lat,
          lng,
          reason: 'Latitude must be between -90.0 and 90.0 degrees and Longitude between -180.0 and 180.0 degrees.',
        },
      },
      { status: 422 }
    );
  }

  try {
    const normalized = await geocodingService.resolveCoordinates(lat, lng, { fresh });
    return NextResponse.json(
      {
        status: 'success',
        address: normalized,
      },
      {
        status: 200,
        headers: {
          'Cache-Control': 'public, s-maxage=3600, max-age=1800, stale-while-revalidate=86400',
          'X-Geocoder-Source': normalized.geocoderSource || 'nominatim',
        },
      }
    );
  } catch (err: unknown) {
    return handleGeocodeError(err, `(${lat}, ${lng})`);
  }
}

function handleGeocodeError(err: unknown, addressContext: string) {
  if (err instanceof PoBoxError) {
    return NextResponse.json(
      {
        status: 'error',
        code: err.code || 'PO_BOX_NOT_SUPPORTED',
        message: err.message,
        details: err.details || {
          submittedAddress: addressContext,
          field: 'address',
        },
      },
      { status: 400 }
    );
  }

  if (err instanceof MissingStreetNumberError) {
    return NextResponse.json(
      {
        status: 'error',
        code: err.code || 'STREET_NUMBER_REQUIRED',
        message: 'Please provide a full street address including building number.',
        details: err.details || {
          submittedAddress: addressContext,
          field: 'address',
          reason: 'Building or house number is missing from the query.',
        },
      },
      { status: 400 }
    );
  }

  if (err instanceof OutOfBoundsError) {
    return NextResponse.json(
      {
        status: 'error',
        code: err.code || 'OUT_OF_COVERAGE_AREA',
        message: 'Address is outside the United States broadband coverage area.',
        details: err.details || {
          submittedAddress: addressContext,
          reason: 'Only US postal addresses are supported for 5G Home Internet availability.',
        },
      },
      { status: 400 }
    );
  }

  if (err instanceof AddressNotFoundError) {
    return NextResponse.json(
      {
        status: 'error',
        code: err.code || 'ADDRESS_NOT_RESOLVED',
        message: 'Unable to geocode the submitted address into a valid US physical location.',
        details: err.details || {
          submittedAddress: addressContext,
          field: 'address',
          reason: 'Zero matches returned across geocoding cascade (Census, Photon, Nominatim).',
        },
      },
      { status: 400 }
    );
  }

  if (err instanceof InvalidCoordinatesError) {
    return NextResponse.json(
      {
        status: 'error',
        code: err.code,
        message: err.message,
        details: err.details,
      },
      { status: 422 }
    );
  }

  if (err instanceof AddressValidationError) {
    return NextResponse.json(
      {
        status: 'error',
        code: err.code,
        message: err.message,
        details: err.details,
      },
      { status: 400 }
    );
  }

  if (err instanceof GeocodingError) {
    return NextResponse.json(
      {
        status: 'error',
        code: err.code,
        message: err.message,
        details: err.details,
      },
      { status: err.statusCode }
    );
  }

  console.error('[/api/geocode/resolve] Unhandled error:', err);
  return NextResponse.json(
    {
      status: 'error',
      code: 'INTERNAL_SERVER_ERROR',
      message: 'Internal server error while resolving address.',
    },
    { status: 500 }
  );
}
