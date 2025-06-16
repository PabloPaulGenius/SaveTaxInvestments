import { NextResponse } from 'next/server'
import { createClient } from '@/app/utils/supabase/server'

export async function GET(request: Request) {
  const supabase = await createClient();
  // console.log('Supabase client:', supabase);


    // const { data: allEtfs } = await supabase.from('etf_ausschuettend').select('isin');
    // console.log('All ISINs in DB:', allEtfs);

  try {
    const { searchParams } = new URL(request.url)
    const isin = searchParams.get('isin')?.trim().toUpperCase()
    console.log('API received ISIN:', isin)

    if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY) {
      return NextResponse.json(
        { error: 'Database configuration is missing' },
        { status: 500 }
      )
    }

    // If no ISIN provided, return all ETFs
    if (!isin) {
      const { data, error } = await supabase
        .from('etf_ausschuettend')
        .select('isin, dividendenrendite')
        .limit(10)

      if (error) {
        console.error('Supabase error:', error)
        return NextResponse.json(
          { error: 'Database query failed' },
          { status: 500 }
        )
      }

      return NextResponse.json({ etfs: data })
    }

    // If ISIN provided, search for specific ETF
    const { data, error } = await supabase
        .from('etf_ausschuettend')
        .select('*')
        .eq('isin', isin)
        .maybeSingle()

    if (error) {
      console.error('Supabase error:', error)
      return NextResponse.json(
        { error: 'Database query failed' },
        { status: 500 }
      )
    }

    if (!data) {
      return NextResponse.json(
        { error: `No ETF found with ISIN: ${isin}` },
        { status: 404 }
      )
    }

    return NextResponse.json(data)
  } catch (error) {
    console.error('API error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
} 