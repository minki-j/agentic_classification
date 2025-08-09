import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { api } from '@/lib/api';
import { useNavigate } from 'react-router-dom';
import TokenManager from '@/lib/tokenManager';

interface User {
    id: string;
    email: string;
    name: string;
    is_superuser: boolean;
    is_paid_user: boolean;
    picture?: string;
}

interface AuthContextType {
    user: User | null;
    isLoading: boolean;
    login: (rememberMe?: boolean) => void;
    logout: () => void;
    refreshAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};

interface AuthProviderProps {
    children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const navigate = useNavigate();

    // Fetch current user
    const fetchUser = async () => {
        try {
            const response = await api.get('/users/me');
            setUser(response.data.user);
        } catch (error) {
            console.error('Failed to fetch user:', error);
            setUser(null);
        }
    };

    // Check if user is authenticated on mount
    useEffect(() => {
        const checkAuth = async () => {
            const token = TokenManager.getAccessToken();
            if (token) {
                await fetchUser();
            }
            setIsLoading(false);
        };

        checkAuth();
    }, []);

    // Login function - redirects to Google OAuth
    const login = async (rememberMe: boolean = false) => {
        try {
            // Store remember me preference temporarily
            if (rememberMe) {
                sessionStorage.setItem('pending_remember_me', 'true');
            }
            // Redirect through backend to maintain session
            window.location.href = `${import.meta.env.VITE_API_URL}/api/v1/auth/google/login/redirect`;
        } catch (error) {
            console.error('Login failed:', error);
        }
    };

    // Logout function
    const logout = () => {
        TokenManager.clearTokens();
        setUser(null);
        localStorage.removeItem('selectedTaxonomyId');
        navigate('/login');
    };

    // Refresh authentication
    const refreshAuth = async () => {
        await fetchUser();
    };

    return (
        <AuthContext.Provider value={{ user, isLoading, login, logout, refreshAuth }}>
            {children}
        </AuthContext.Provider>
    );
}; 