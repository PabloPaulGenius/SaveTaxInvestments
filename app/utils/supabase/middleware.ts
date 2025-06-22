import { createServerClient, type CookieOptions } from "@supabase/ssr";
import { type NextRequest, NextResponse } from "next/server";

export const createClient = (request: NextRequest) => {
  // Create a Next.js response object, initially unmodified.
  // This is needed so we can set cookies on the response if Supabase needs to update them.
  let supabaseResponse = NextResponse.next({
    request: {
      headers: request.headers, // Pass along the request headers
    },
  });

  // Create the Supabase client for the server (middleware context)
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,      // Your Supabase project URL (from .env.local)
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!, // Your Supabase anon/public key (from .env.local)
    {
      // Define how cookies are handled in this context
      cookies: {
        // Get all cookies from the request
        getAll() {
          return request.cookies.getAll()
        },
        // Set all cookies on the request and response
        setAll(cookiesToSet) {
          // Set cookies on the request object
          cookiesToSet.forEach(({ name, value, options }) => request.cookies.set(name, value))
          // Create a new response object to update cookies
          supabaseResponse = NextResponse.next({
            request,
          })
          // Set cookies on the response object
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          )
        },
      },
    },
  );

  // Return the response object (with any updated cookies)
  return supabaseResponse
};

