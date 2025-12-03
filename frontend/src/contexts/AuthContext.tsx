import React, { createContext, useContext, useEffect, useState } from 'react';
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

  // Fetch user profile and organization data
  const fetchUserData = async (userId: string) => {
    try {
      console.log('🔍 Fetching user data for ID:', userId);
      
      // Fetch user from public.users table
      const { data: userData, error: userError } = await supabase
        .from('users')
        .select('*')
        .eq('id', userId)
        .single();

      console.log('📊 User data response:', { userData, userError });

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

      console.log('🏢 Organization data response:', { orgData, orgError });

      if (orgError) {
        console.error('❌ Error fetching organization:', orgError);
        throw orgError;
      }

      if (!orgData) {
        throw new Error('Organization not found in database');
      }

      console.log('✅ Successfully loaded user and organization');
      setUser(userData);
      setOrganization(orgData);
    } catch (error) {
      console.error('❌ Error in fetchUserData:', error);
      setUser(null);
      setOrganization(null);
      throw error; // Re-throw so signIn knows there was an error
    }
  };

  // Initialize auth state
  useEffect(() => {
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
    } = supabase.auth.onAuthStateChange(async (_event, session) => {
      console.log('🔐 Auth state changed:', _event);
      setSession(session);
      if (session?.user) {
        try {
          await fetchUserData(session.user.id);
        } catch (error) {
          console.error('Failed to load user data on auth change:', error);
        }
      } else {
        setUser(null);
        setOrganization(null);
      }
      setLoading(false);
    });

    return () => subscription.unsubscribe();
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

    // Fetch user data after signup
    if (data.user) {
      await fetchUserData(data.user.id);
    }
  };

  const signIn = async (email: string, password: string) => {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (error) throw error;

    // Fetch user data after login
    if (data.user) {
      await fetchUserData(data.user.id);
    }
  };

  const signOut = async () => {
    const { error } = await supabase.auth.signOut();
    if (error) throw error;
    setUser(null);
    setOrganization(null);
    setSession(null);
  };

  const refreshUser = async () => {
    if (session?.user) {
      await fetchUserData(session.user.id);
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
