import React from 'react';

import InitializeNodes from '@/pages/InitializeNodes';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { GitForkIcon } from 'lucide-react';

interface NoNodesProps {
    selectedTaxonomyId: string | null;
}

const NoNodes: React.FC<NoNodesProps> = ({ selectedTaxonomyId }) => {
    return (
        <div className="h-full w-full flex items-center justify-center px-4">
            <Card className="w-full max-w-xl border-2 border-dashed">
                <CardHeader className="text-center space-y-3">
                    <div className="flex justify-center">
                        <div className="p-3 bg-primary/10 rounded-full">
                            <GitForkIcon className="h-8 w-8 text-primary" />
                        </div>
                    </div>
                    <CardTitle className="text-2xl">This taxonomy has no class nodes</CardTitle>
                    <CardDescription>
                        Create the initial class nodes to start organizing and classifying your items.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <ul className="text-sm text-muted-foreground list-disc list-inside space-y-1">
                        <li>Choose how many items to sample for bootstrapping</li>
                        <li>Select an AI model to generate the initial structure</li>
                    </ul>
                    <div className="flex justify-center pt-2">
                        <InitializeNodes selectedTaxonomyId={selectedTaxonomyId} />
                    </div>
                </CardContent>
            </Card>
        </div>
    );
};

export default NoNodes;