import { createClient, SupabaseClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

// Create a mock supabase client if credentials are not configured
let supabase

if (supabaseUrl && supabaseAnonKey && supabaseUrl.startsWith('https://')) {
    supabase = createClient(supabaseUrl, supabaseAnonKey)
} else {
    // Create a mock client for demo/offline mode
    supabase = {
        auth: {
            getSession: async () => ({ data: { session: null }, error: null }),
            onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => { } } } }),
            signUp: async () => ({ data: { user: null }, error: { message: 'Supabase not configured' } }),
            signInWithPassword: async () => ({ data: { user: null, session: null }, error: { message: 'Supabase not configured' } }),
            signInWithOAuth: async () => ({ data: { url: null }, error: { message: 'Supabase not configured' } }),
            signOut: async () => ({ error: null }),
            getUser: async () => ({ data: { user: null }, error: { message: 'Supabase not configured' } })
        }
    }
    console.warn('Supabase credentials not configured. Running in demo mode.')
}

export { supabase }
