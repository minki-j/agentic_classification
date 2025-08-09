import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Loader2 } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import TokenManager from '@/lib/tokenManager';

const AuthCallback = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const { refreshAuth } = useAuth();
    const { toast } = useToast();

    useEffect(() => {
        const handleCallback = async () => {
            const error = searchParams.get('error');
            const accessToken = searchParams.get('access_token');
            const refreshToken = searchParams.get('refresh_token');

            if (error) {
                toast({
                    title: 'Authentication Failed',
                    description: 'Failed to authenticate with Google. Please try again.',
                    variant: 'destructive',
                });
                navigate('/login');
                return;
            }

            if (!accessToken || !refreshToken) {
                toast({
                    title: 'Authentication Failed',
                    description: 'Invalid authentication response.',
                    variant: 'destructive',
                });
                navigate('/login');
                return;
            }

            try {
                // Check if remember me was requested
                const rememberMe = sessionStorage.getItem('pending_remember_me') === 'true';
                sessionStorage.removeItem('pending_remember_me');

                // Store tokens using TokenManager
                TokenManager.setTokens(accessToken, refreshToken, rememberMe);

                // Refresh auth context
                await refreshAuth();

                // Redirect to home
                navigate('/');
            } catch (error) {
                console.error('Authentication callback failed:', error);
                toast({
                    title: 'Authentication Failed',
                    description: 'An error occurred during authentication. Please try again.',
                    variant: 'destructive',
                });
                navigate('/login');
            }
        };

        handleCallback();
    }, [searchParams, navigate, refreshAuth, toast]);

    return (
        <div className="min-h-screen flex items-center justify-center">
            <div className="text-center">
                <Loader2 className="h-12 w-12 animate-spin mx-auto mb-4" />
                <p className="text-lg text-gray-600 dark:text-gray-400">
                    Completing authentication...
                </p>
            </div>
        </div>
    );
};

export default AuthCallback; 