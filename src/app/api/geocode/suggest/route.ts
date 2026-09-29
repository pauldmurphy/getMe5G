import { NextRequest, NextResponse } from 'next/server';
import { geocodingService } from '@/lib/geocoding/service';

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const rawQ = searchParams.get('q');

  // Rule 1: Missing or empty query
  if (rawQ === null || rawQ.trim().length === 0) {
    return NextResponse.json(
      {
        status: 'error',
        code: 'MISSING_QUERY_PARAMETER',
        message: "Query parameter 'q' is required and cannot be empty.",
        details: {
          parameter: 'q',
        },
      },
      { status: 400 }
    );
  }

  // Rule 3: Maximum length enforcement
  if (rawQ.length > 256) {
    return NextResponse.json(
      {
        status: 'error',
        code: 'QUERY_TOO_LONG',
        message: "Query parameter 'q' exceeds maximum allowable length of 256 characters.",
        details: {
          parameter: 'q',
          maxLength: 256,
          receivedLength: rawQ.length,
        },
      },
      { status: 400 }
    );
  }

  const q = rawQ.replace(/[\0\r\n]/g, '').trim();

  // Rule 2: Short query threshold (< 3 chars) — no upstream call
  if (q.length < 3) {
    return NextResponse.json(
      {
        status: 'success',
        query: q,
        count: 0,
        suggestions: [],
      },
      {
        status: 200,
        headers: {
          'Cache-Control': 'public, s-maxage=3600, max-age=1800, stale-while-revalidate=86400',
        },
      }
    );
  }

  // Parse limit (clamped between 1 and 10)
  const limitParam = searchParams.get('limit');
  let limit = 5;
  if (limitParam) {
    const parsed = parseInt(limitParam, 10);
    if (!isNaN(parsed)) {
      limit = Math.min(Math.max(parsed, 1), 10);
    }
  }

  // Parse optional proximity lat/lng
  const latParam = searchParams.get('lat');
  const lngParam = searchParams.get('lng');
  let proximity: { lat: number; lng: number } | undefined;

  if (latParam !== null && lngParam !== null) {
    const lat = parseFloat(latParam);
    const lng = parseFloat(lngParam);
    if (!isNaN(lat) && !isNaN(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
      proximity = { lat, lng };
    }
  }

  try {
    const suggestions = await geocodingService.suggest(q, {
      limit,
      proximity,
    });

    const primarySource = suggestions[0]?.source || 'photon';

    return NextResponse.json(
      {
        status: 'success',
        query: q,
        count: suggestions.length,
        suggestions,
      },
      {
        status: 200,
        headers: {
          'Cache-Control': 'public, s-maxage=3600, max-age=1800, stale-while-revalidate=86400',
          'X-Geocoder-Source': primarySource,
        },
      }
    );
  } catch (err: unknown) {
    console.error('[/api/geocode/suggest] Error:', err);
    return NextResponse.json(
      {
        status: 'error',
        code: 'INTERNAL_SERVER_ERROR',
        message: 'Failed to retrieve address suggestions.',
      },
      { status: 500 }
    );
  }
}
