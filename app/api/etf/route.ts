import { NextResponse } from 'next/server' // For sending API responses in Next.js
import { createClient } from '@/app/utils/supabase/server' // Import our Supabase client creator

// This is the handler for GET requests to /api/etf
export async function GET(request: Request) {
  // Create a Supabase client for this request
  const supabase = await createClient();

  try {
    // Parse the URL to get the ISIN query parameter (if present)
    const { searchParams } = new URL(request.url)
    const isin = searchParams.get('isin')?.trim().toUpperCase() // Clean up ISIN

    // Check if the Supabase environment variables are set
    if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY) {
      return NextResponse.json(
        { error: 'Database configuration is missing' },
        { status: 500 }
      )
    }

    // If no ISIN is provided, return a list of up to 10 ETFs (for browsing/testing)
    if (!isin) {
      const { data, error } = await supabase
        .from('etf_ausschuettend') // Table name
        .select('isin, dividendenrendite') // Only select these columns
        .limit(10)

      if (error) {
        // If there was a database error, return a 500 error
        return NextResponse.json(
          { error: 'Database query failed' },
          { status: 500 }
        )
      }

      // Return the list of ETFs as JSON
      return NextResponse.json({ etfs: data })
    }

    // If an ISIN is provided, fetch all columns for that ETF
    const { data, error } = await supabase
      .from('etf_ausschuettend')
      .select('*') // Select all columns
      .eq('isin', isin) // Where ISIN matches
      .maybeSingle() // Return a single object or null

    if (error) {
      // If there was a database error, return a 500 error
      return NextResponse.json(
        { error: 'Database query failed' },
        { status: 500 }
      )
    }

    if (!data) {
      // If no ETF was found, return a 404 error
      return NextResponse.json(
        { error: `No ETF found with ISIN: ${isin}` },
        { status: 404 }
      )
    }

    // Return the ETF data as JSON
    return NextResponse.json(data)
  } catch (error) {
    // Catch any unexpected errors and return a 500 error
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}