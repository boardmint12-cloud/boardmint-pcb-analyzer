import React, { createContext, useContext, useEffect, useState, useRef } from 'react';
import { supabase, User, Organization } from '../lib/supabase';
import { Session } from '@supabase/supabase-js';

interface AuthContextType {
  user: User | null;
  organization: Organization | null;
  session: Session | null;
  loading: boolean;
  signUp: (email: string, password: string, fullName: string, organizationName: string) => Promise<void>;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  
  // Use refs to prevent infinite loops (refs persist across renders without causing re-renders)
  const fetchingRef = useRef(false);
  const lastFetchedUserIdRef = useRef<string | null>(null);
  const initializedRef = useRef(false);

  // Fetch user profile and organization data
  const fetchUserData = async (userId: string, force: boolean = false) => {
    // Prevent duplicate fetches
    if (fetchingRef.current) {
      console.log('⏳ Already fetching user data, skipping...');
      return;
    }
    
    if (!force && lastFetchedUserIdRef.current === userId) {
      console.log('✓ User data already loaded for this user');
      return;
    }

    fetchingRef.current = true;
    
    try {
      console.log('🔍 Fetching user data for ID:', userId);
      
      // Fetch user from public.users table
      const { data: userData, error: userError } = await supabase
        .from('users')
        .select('*')
        .eq('id', userId)
        .single();

      if (userError) {
        console.error('❌ Error fetching user:', userError);
        throw userError;
      }

      if (!userData) {
        throw new Error('User not found in database');
      }

      // Fetch organization
      const { data: orgData, error: orgError } = await supabase
        .from('organizations')
        .select('*')
        .eq('id', userData.organization_id)
        .single();

      if (orgError) {
        console.error('❌ Error fetching organization:', orgError);
        throw orgError;
      }

      if (!orgData) {
        throw new Error('Organization not found in database');
      }

      console.log('✅ Successfully loaded user and organization');
      lastFetchedUserIdRef.current = userId;
      setUser(userData);
      setOrganization(orgData);
    } catch (error) {
      console.error('❌ Error in fetchUserData:', error);
      lastFetchedUserIdRef.current = null;
      setUser(null);
      setOrganization(null);
      throw error;
    } finally {
      fetchingRef.current = false;
    }
  };

  // Initialize auth state - runs only once
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;
    
    // Get initial session
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      setSession(session);
      if (session?.user) {
        try {
          await fetchUserData(session.user.id);
        } catch (error) {
          console.error('Failed to load user data on init:', error);
        }
      }
      setLoading(false);
    });

    // Listen for auth changes
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (event, session) => {
      console.log('🔐 Auth state changed:', event);
      
      // Only process sign out
      if (event === 'SIGNED_OUT') {
        setSession(null);
        setUser(null);
        setOrganization(null);
        lastFetchedUserIdRef.current = null;
        setLoading(false);
        return;
      }
      
      // For sign in, only fetch if we don't have the user yet
      if (event === 'SIGNED_IN' && session?.user) {
        setSession(session);
        if (lastFetchedUserIdRef.current !== session.user.id) {
          try {
            await fetchUserData(session.user.id);
          } catch (error) {
            console.error('Failed to load user data on auth change:', error);
          }
        }
        setLoading(false);
      }
    });

    return () => {
      subscription.unsubscribe();
    };
  }, []);

  const signUp = async (
    email: string,
    password: string,
    fullName: string,
    organizationName: string
  ) => {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          full_name: fullName,
          organization_name: organizationName,
        },
      },
    });

    if (error) throw error;

    // Fetch user data after signup (force refresh)
    if (data.user) {
      await fetchUserData(data.user.id, true);
    }
  };

  const signIn = async (email: string, password: string) => {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (error) throw error;

    // Fetch user data after login (force refresh)
    if (data.user) {
      await fetchUserData(data.user.id, true);
    }
  };

  const signOut = async () => {
    const { error } = await supabase.auth.signOut();
    if (error) throw error;
    setUser(null);
    setOrganization(null);
    setSession(null);
    lastFetchedUserIdRef.current = null;
  };

  const refreshUser = async () => {
    if (session?.user) {
      await fetchUserData(session.user.id, true); // Force refresh
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        organization,
        session,
        loading,
        signUp,
        signIn,
        signOut,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
