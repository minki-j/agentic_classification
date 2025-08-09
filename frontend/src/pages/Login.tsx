import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Loader2, Users, Shield, Target, TrendingUp } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';


const Login = () => {
    const navigate = useNavigate();
    const { user, isLoading, login } = useAuth();

    const [rememberMe, setRememberMe] = useState(true);

    useEffect(() => {
        if (user) {
            navigate('/');
        }
    }, [user, navigate]);

    const handleLogin = () => {
        login(rememberMe);
    };

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-amber-50">
                <Loader2 className="h-8 w-8 animate-spin text-amber-600" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-amber-50 overflow-hidden relative">
            {/* Content Container */}
            <div className="relative z-10 min-h-screen flex flex-col">
                {/* Hero Section */}
                <div className="flex-1 flex items-center justify-center px-4 py-16">
                    <div
                        className="text-center max-w-4xl mx-auto"
                    >
                        {/* Badge */}
                        <div className="inline-flex items-center gap-2 bg-amber-200 text-black px-6 py-3 rounded-full text-sm font-bold mb-8 border border-black">
                            <Users className="h-4 w-4" />
                            TRUE SWARM INTELLIGENCE
                        </div>

                        {/* Main Heading */}
                        <h1 className="text-6xl md:text-8xl font-black text-black mb-6 leading-tight">
                            SWARM
                            <span className="block text-amber-600">CLASSIFICATION AGENT</span>
                        </h1>

                        <p className="text-xl text-black/80 mb-12 max-w-2xl mx-auto font-medium">
                            The truly bottom-up collective AI system.
                        </p>

                        {/* Get Started Card */}
                        <Card className="max-w-md mx-auto border-2 border-black bg-white shadow-lg">
                            <CardHeader className="pb-4">
                                <CardTitle className="text-2xl font-black text-black">GET STARTED</CardTitle>
                                <CardDescription className="text-black/60 font-medium">
                                    Join the hive now for free
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <Button
                                    onClick={handleLogin}
                                    className="w-full bg-amber-400 hover:bg-amber-500 text-black border-2 border-black font-bold text-lg h-12 shadow-lg transition-all duration-200 hover:shadow-xl"
                                    size="lg"
                                >
                                    Continue with Google
                                    <svg className="w-7 h-7" viewBox="0 0 48 48">
                                        <path fill="#fbc02d" d="M43.611,20.083H42V20H24v8h11.303c-1.649,4.657-6.08,8-11.303,8c-6.627,0-12-5.373-12-12s5.373-12,12-12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C12.955,4,4,12.955,4,24s8.955,20,20,20s20-8.955,20-20C44,22.659,43.862,21.35,43.611,20.083z"></path>
                                        <path fill="#e53935" d="M6.306,14.691l6.571,4.819C14.655,15.108,18.961,12,24,12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C16.318,4,9.656,8.337,6.306,14.691z"></path>
                                        <path fill="#4caf50" d="M24,44c5.166,0,9.86-1.977,13.409-5.192l-6.19-5.238C29.211,35.091,26.715,36,24,36c-5.202,0-9.619-3.317-11.283-7.946l-6.522,5.025C9.505,39.556,16.227,44,24,44z"></path>
                                        <path fill="#1565c0" d="M43.611,20.083L43.595,20L42,20H24v8h11.303c-0.792,2.237-2.231,4.166-4.087,5.571c0.001-0.001,0.002-0.001,0.003-0.002l6.19,5.238C36.971,39.205,44,34,44,24C44,22.659,43.862,21.35,43.611,20.083z"></path>
                                    </svg>
                                </Button>

                                <div className="flex items-center justify-center space-x-2">
                                    <Checkbox
                                        id="remember-me"
                                        checked={rememberMe}
                                        onCheckedChange={(checked) => setRememberMe(checked === true)}
                                        className="border-black data-[state=checked]:bg-amber-400 data-[state=checked]:border-black data-[state=checked]:text-black"
                                    />
                                    <Label
                                        htmlFor="remember-me"
                                        className="text-sm text-black/70 font-medium cursor-pointer hover:text-black"
                                    >
                                        Remember me
                                    </Label>
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                </div>

                {/* Youtube Video */}
                <div className="py-10 px-4">
                    <div className="max-w-4xl mx-auto">
                        <div className="w-full px-20 aspect-video">
                            <iframe
                                className="w-full h-full"
                                src="https://www.youtube.com/embed/szEeaPVBYSo"
                                title="YouTube video player"
                                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                                referrerPolicy="strict-origin-when-cross-origin"
                                allowFullScreen
                            ></iframe>
                        </div>
                    </div>
                </div>

                {/* Footer */}
                <div className="py-8 px-4">
                    <div className="max-w-4xl mx-auto">
                        <p className="text-sm text-center text-black/30">
                            Built by Minki Jung
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Login;