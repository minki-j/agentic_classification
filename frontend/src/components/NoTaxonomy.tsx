import React, { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from './ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { classificationApi } from '@/lib/api';
import {
    Sparkles,
    TreePine,
    Zap,
    Crown,
    Users,
    Bot,
    Loader2,
    CheckCircle,
    ArrowRight
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { useQueryClient } from '@tanstack/react-query';

const NoTaxonomy: React.FC = () => {
    const { user } = useAuth();
    const { toast } = useToast();
    const [isInitializing, setIsInitializing] = useState(false);
    const queryClient = useQueryClient();

    const handleTrialSetup = async () => {
        if (!user?.id) return;

        try {
            setIsInitializing(true);
            await classificationApi.initTrialSetup();
            toast({
                title: "Trial setup initialized",
                description: "You can now create a taxonomy and start classifying items",
            });
            queryClient.invalidateQueries({ queryKey: ['taxonomies'], exact: false });
            queryClient.invalidateQueries({ queryKey: ['items'], exact: false });
            queryClient.invalidateQueries({ queryKey: ['nodes'], exact: false });
        } catch (error) {
            console.error('Failed to initialize trial setup:', error);
        } finally {
            setIsInitializing(false);
        }
    };

    const features = [
        {
            icon: <Bot className="w-5 h-5" />,
            title: "AI-Powered Classification",
            description: "Intelligent item categorization using advanced LLM models"
        },
        {
            icon: <TreePine className="w-5 h-5" />,
            title: "Dynamic Taxonomies",
            description: "Self-evolving classification structures that adapt to your data"
        },
        {
            icon: <Zap className="w-5 h-5" />,
            title: "Real-time Processing",
            description: "Instant classification and taxonomy updates"
        }
    ];

    return (
        <div className="flex flex-col items-center justify-center h-full p-8 max-w-4xl mx-auto">
            {user?.is_paid_user ? (
                <Card className="w-full max-w-2xl">
                    <CardHeader className="text-center pb-8">
                        <div className="flex justify-center mb-4">
                            <div className="p-3 bg-primary/10 rounded-full">
                                <Crown className="w-8 h-8 text-primary" />
                            </div>
                        </div>
                        <CardTitle className="text-3xl font-bold">
                            Welcome back, {user?.name}!
                        </CardTitle>
                        <CardDescription className="text-lg mt-2">
                            You're all set with premium features. Create your first taxonomy to begin organizing your data.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="text-center">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                            {features.map((feature, index) => (
                                <div key={index} className="p-4 bg-muted/50 rounded-lg">
                                    <div className="flex justify-center mb-2 text-primary">
                                        {feature.icon}
                                    </div>
                                    <h4 className="font-semibold text-sm mb-1">{feature.title}</h4>
                                    <p className="text-xs text-muted-foreground">{feature.description}</p>
                                </div>
                            ))}
                        </div>
                        <Button size="lg" className="w-full">
                            <TreePine className="w-4 h-4 mr-2" />
                            Create Your First Taxonomy
                        </Button>
                    </CardContent>
                </Card>
            ) : (
                <div className="w-full max-w-3xl space-y-8">
                    <Card className="border-2 border-dashed">
                        <CardHeader className="text-center pb-6">
                            <div className="flex justify-center mb-4">
                                <div className="p-4 bg-gradient-to-br from-primary/10 to-primary/5 rounded-full">
                                    <Sparkles className="w-10 h-10 text-primary" />
                                </div>
                            </div>
                            <CardTitle className="text-3xl font-bold">
                                Welcome to the Beta, {user?.name}!
                            </CardTitle>
                            <CardDescription className="text-lg mt-2 max-w-2xl mx-auto">
                                Experience the future of AI-powered taxonomy management.
                                Start exploring with our curated sample data and discover how intelligent classification works.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <div className="flex justify-center">
                                <Badge variant="secondary" className="px-4 py-2 text-sm">
                                    <Users className="w-4 h-4 mr-2" />
                                    Beta Access • Free Trial
                                </Badge>
                            </div>

                            <div className="bg-muted/30 rounded-lg p-6 space-y-4">
                                <h3 className="font-semibold text-lg flex items-center">
                                    <CheckCircle className="w-5 h-5 mr-2 text-green-500" />
                                    What's included in your trial:
                                </h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div className="flex items-start space-x-3">
                                        <div className="p-1 bg-green-100 rounded-full mt-1">
                                            <CheckCircle className="w-3 h-3 text-green-600" />
                                        </div>
                                        <div>
                                            <p className="font-medium text-sm">Sample Dataset</p>
                                            <p className="text-xs text-muted-foreground">Only the curated items are available</p>
                                        </div>
                                    </div>
                                    <div className="flex items-start space-x-3">
                                        <div className="p-1 bg-green-100 rounded-full mt-1">
                                            <CheckCircle className="w-3 h-3 text-green-600" />
                                        </div>
                                        <div>
                                            <p className="font-medium text-sm">Core AI Models</p>
                                            <p className="text-xs text-muted-foreground">Only limited LLMs are available</p>
                                        </div>
                                    </div>
                                    <div className="flex items-start space-x-3">
                                        <div className="p-1 bg-green-100 rounded-full mt-1">
                                            <CheckCircle className="w-3 h-3 text-green-600" />
                                        </div>
                                        <div>
                                            <p className="font-medium text-sm">Real-time Classification</p>
                                            <p className="text-xs text-muted-foreground">Watch AI organize your data live</p>
                                        </div>
                                    </div>
                                    <div className="flex items-start space-x-3">
                                        <div className="p-1 bg-green-100 rounded-full mt-1">
                                            <CheckCircle className="w-3 h-3 text-green-600" />
                                        </div>
                                        <div>
                                            <p className="font-medium text-sm">Interactive Interface</p>
                                            <p className="text-xs text-muted-foreground">Full access to all UI features</p>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div className="text-center">
                                <Button
                                    size="lg"
                                    onClick={handleTrialSetup}
                                    disabled={isInitializing}
                                    className="w-full sm:w-auto px-8 py-3 text-base font-semibold"
                                >
                                    {isInitializing ? (
                                        <>
                                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                            Setting up your trial...
                                        </>
                                    ) : (
                                        <>
                                            <Sparkles className="w-4 h-4 mr-2" />
                                            Start Your Free Trial
                                            <ArrowRight className="w-4 h-4 ml-2" />
                                        </>
                                    )}
                                </Button>
                                <p className="text-xs text-muted-foreground mt-3">
                                    No credit card required • Explore all features with limited items and LLMs
                                </p>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}
        </div>
    );
}

export default NoTaxonomy;