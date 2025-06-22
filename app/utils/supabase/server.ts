// Import the function to create a Supabase client for server-side use
import { createServerClient } from '@supabase/ssr'
// Import Next.js cookies API for handling cookies on the server
import { cookies } from 'next/headers'

// Export a function to create and return a Supabase client instance
export const createClient = async () => {
  // Get the cookies object (used for authentication/session)
  const cookieStore = await cookies();

  // Create and return the Supabase client, passing in the project URL, anon key, and cookie methods
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,      // Supabase project URL from environment variable
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!, // Supabase anon/public key from environment variable
    {
      cookies: {
        // Return all cookies (needed for Supabase session management)
        getAll: () => cookieStore.getAll(),
        // Set all cookies (needed for Supabase session management)
        setAll: (cookiesToSet) => {
          cookiesToSet.forEach(({ name, value, options }) => {
            cookieStore.set(name, value, options)
          })
        }
      }
    }
  )
}
