import React, { useState, useRef, useEffect } from 'react';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Loader2, GitForkIcon } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';

import { useToast } from '@/hooks/use-toast';
import { nodesApi, wsConnection } from '@/lib/api';
import { AI_MODELS } from '@/models/types';

interface InitializeNodesProps {
    selectedTaxonomyId: string | null;
    onInitializationComplete?: () => void;
}

const InitializeNodes: React.FC<InitializeNodesProps> = ({
    selectedTaxonomyId,
    onInitializationComplete
}) => {
    const { toast } = useToast();
    const queryClient = useQueryClient();

    // Dialog state
    const [dialogOpen, setDialogOpen] = useState(false);
    const [numOfItems, setNumOfItems] = useState<number>(50);
    const [llmName, setLlmName] = useState<string>("gpt-5-2025-08-07");

    // Initialization loader states
    const [initializationInProgress, setInitializationInProgress] = useState(false);
    const [initializationProgress, setInitializationProgress] = useState(0);
    const [initializationMessage, setInitializationMessage] = useState('');
    const initializationSessionRef = useRef<string | null>(null);
    const progressIntervalRef = useRef<number | null>(null);
    const timeoutRef = useRef<number | null>(null);

    // Function to start fake progress animation
    const startFakeProgress = () => {
        setInitializationProgress(0);
        setInitializationInProgress(true);

        let currentProgress = 0;

        // Progress animation with varying speeds
        progressIntervalRef.current = window.setInterval(() => {
            // Weighted random: 1 (70%), 2 (20%), 3 (5%), 4 (2.5%), 5 (2.5%)
            const rand = Math.random();
            let increment;
            if (rand < 0.7) {
                increment = 0;
            } else if (rand < 0.8) {
                increment = 0.5;
            } else if (rand < 0.9) {
                increment = 1;
            } else if (rand < 0.95) {
                increment = 2;
            } else {
                increment = 4;
            }

            if (currentProgress + increment > 85) {
                if (rand < 0.8) {
                    increment = 0;
                } else if (rand < 0.9) {
                    increment = 0.5;
                } else {
                    increment = 1;
                }
            }

            currentProgress = currentProgress + increment

            setInitializationProgress(currentProgress);
        }, 500); // Update every 0.5 seconds

        // Set 5-minute timeout
        timeoutRef.current = window.setTimeout(() => {
            // Clean up and reload page
            if (progressIntervalRef.current) {
                clearInterval(progressIntervalRef.current);
            }
            toast({
                title: "Initialization timeout",
                description: "The process took too long. Reloading the page...",
                variant: "destructive",
            });
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        }, 5 * 60 * 1000); // 5 minutes
    };

    // Function to stop fake progress and complete
    const completeFakeProgress = () => {
        if (progressIntervalRef.current) {
            clearInterval(progressIntervalRef.current);
            progressIntervalRef.current = null;
        }
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
            timeoutRef.current = null;
        }
        setInitializationInProgress(false);
        setInitializationProgress(0);
        setInitializationMessage('');
        initializationSessionRef.current = null;
    };

    // Mutation for initializing nodes
    const initializeNodesMutation = useMutation({
        mutationFn: async ({ taxonomyId, numOfItems, llmName }: { taxonomyId: string; numOfItems: number; llmName: string }) => {
            await nodesApi.createInitialNodes(taxonomyId, numOfItems, llmName);
        },
        onSuccess: (data) => {
            // Close dialog
            setDialogOpen(false);

            // Start fake progress
            startFakeProgress();
        },
        onError: (error: any) => {
            toast({
                title: "Failed to initialize nodes",
                description: error.response?.data?.detail || "An error occurred",
                variant: "destructive",
            });
        },
    });

    // WebSocket listener for initialization updates
    useEffect(() => {
        const handleInitializationUpdate = (data: any) => {
            if (data.completed) {
                completeFakeProgress();

                toast({
                    title: "Your taxonomy is initialized successfully!",
                    description: `Total ${data.nodes_created || ""} nodes are created.`,
                });

                queryClient.invalidateQueries({ queryKey: ['nodes', selectedTaxonomyId] });

                // Call completion callback if provided
                onInitializationComplete?.();
            } else {
                setInitializationMessage(data?.message);
            }
        };

        const handleError = (data: any) => {
            // Complete the fake progress on error
            completeFakeProgress();

            toast({
                title: data.title || "Error",
                description: data.detail || "An error occurred during node initialization",
                variant: "destructive",
            });
        };

        wsConnection.on('initialization_update', handleInitializationUpdate);
        wsConnection.on('error', handleError);

        return () => {
            wsConnection.off('initialization_update', handleInitializationUpdate);
            wsConnection.off('error', handleError);
        };
    }, [selectedTaxonomyId, onInitializationComplete]);

    // Cleanup effect for initialization progress
    useEffect(() => {
        return () => {
            if (progressIntervalRef.current) {
                clearInterval(progressIntervalRef.current);
            }
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }
        };
    }, []);

    return (
        <>
            {/* Initialize Button */}
            <Button onClick={() => setDialogOpen(true)}>
                Initialize Nodes
            </Button>

            {/* Initialization Progress Overlay */}
            {initializationInProgress && (
                <div className="fixed inset-0 z-50">
                    {/* Gradient, semi-transparent backdrop with blur */}
                    <div className="absolute inset-0 bg-gradient-to-br from-white/60 via-white/30 to-transparent dark:from-gray-900/80 dark:via-gray-900/40 dark:to-transparent backdrop-blur-md" />

                    {/* Centered container */}
                    <div className="relative flex min-h-full items-center justify-center p-4">
                        <div className="bg-white dark:bg-gray-800 rounded-xl p-10 shadow-2xl w-full mx-4 space-y-6 max-w-xl md:max-w-2xl">
                            <div className="text-center space-y-3">
                                <GitForkIcon className="h-14 w-14 mx-auto text-primary" />
                                <h3 className="text-2xl font-bold">Initializing Nodes</h3>
                                <p className="text-base text-muted-foreground" dangerouslySetInnerHTML={{ __html: initializationMessage }} />
                            </div>
                            <div className="space-y-2">
                                <Progress value={initializationProgress} className="h-3" />
                                <p className="text-sm text-center text-muted-foreground">
                                    {initializationProgress.toFixed(1)}%
                                </p>
                            </div>
                            <p className="text-sm text-center text-muted-foreground">
                                This process could take a while. Hold on!
                            </p>
                        </div>
                    </div>
                </div>
            )}

            {/* Initialize Nodes Dialog */}
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Initialize Nodes</DialogTitle>
                        <DialogDescription>
                            Choose how many items to use for creating initial taxonomy nodes.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="flex flex-col gap-6 mt-4">
                        <div className="flex flex-col gap-3">
                            <Label htmlFor="numItems" className="">
                                Number of items
                            </Label>
                            <Select value={numOfItems.toString()} onValueChange={(value) => setNumOfItems(parseInt(value))}>
                                <SelectTrigger className="col-span-3">
                                    <SelectValue placeholder="Select number of items" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="50">50</SelectItem>
                                    <SelectItem value="100">100</SelectItem>
                                    <SelectItem value="200">200</SelectItem>
                                    <SelectItem value="300">300</SelectItem>
                                    <SelectItem value="500">500</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="flex flex-col gap-3">
                            <Label htmlFor="llmName" className="">
                                Model
                            </Label>
                            <Select value={llmName} onValueChange={setLlmName}>
                                <SelectTrigger className="col-span-3">
                                    <SelectValue placeholder="Select a model" />
                                </SelectTrigger>
                                <SelectContent>
                                    {AI_MODELS.map((model) => (
                                        <SelectItem key={model.value} value={model.value}>
                                            {model.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => setDialogOpen(false)}
                        >
                            Cancel
                        </Button>
                        <Button
                            variant="default"
                            onClick={() => {
                                if (selectedTaxonomyId) {
                                    initializeNodesMutation.mutate({
                                        taxonomyId: selectedTaxonomyId,
                                        numOfItems: numOfItems,
                                        llmName: llmName,
                                    });
                                }
                            }}
                            disabled={initializeNodesMutation.isPending || !selectedTaxonomyId}
                        >
                            {initializeNodesMutation.isPending ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Initializing...
                                </>
                            ) : (
                                'Start Initialization'
                            )}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
};

export default InitializeNodes;
