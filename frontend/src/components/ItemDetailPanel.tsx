import React, { useState } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { X, Plus, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Item, ClassNode } from '@/models/types';
import {
    SelectableList,
    SelectableItem,
    SelectableItemHeader,
    SelectableItemContent,
    SelectableItemFooter
} from '@/components/SelectableList';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { toast } from '@/hooks/use-toast';
import { classificationApi } from '@/lib/api';
import { useQueryClient } from '@tanstack/react-query';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { getConfidenceBackgroundStyle, getConfidenceTextColor } from '@/lib/utils';
import { cn } from '@/lib/utils';


interface ItemDetailPanelProps {
    item: Item | null;
    nodes: ClassNode[];
    taxonomyId: string;
    onClose: () => void;
    onNodeClick: (nodeId: string) => void;
    isNodePickingMode: boolean;
    onStartNodePicking: () => void;
    onCancelNodePicking: () => void;
    onAddClassification?: (nodeId: string) => void; // Direct callback for adding classification
}

type SortOption = 'confidence-high' | 'confidence-low' | 'none';


const ItemDetailPanel: React.FC<ItemDetailPanelProps> = React.memo(({
    item,
    nodes,
    taxonomyId,
    onClose,
    onNodeClick,
    isNodePickingMode,
    onStartNodePicking,
    onCancelNodePicking,
    onAddClassification
}) => {
    console.info("item detail panel remounted");
    const queryClient = useQueryClient();
    const [sortBy, setSortBy] = useState<SortOption>('none');

    if (!item) {
        return (
            <Card className="h-full flex items-center justify-center">
                <CardContent>
                    <p className="text-muted-foreground">Select an item to view details</p>
                </CardContent>
            </Card>
        );
    }

    // Get nodes this item is classified under
    let classifiedNodes = item.classified_as.map(nc => {
        const node = nodes.find(n => n.id === nc.node_id);
        return node ? { node, confidence: nc.confidence_score } : null;
    }).filter(Boolean) as { node: ClassNode; confidence: number }[];

    // Sort nodes based on selected option with secondary sort by updated_at
    classifiedNodes = classifiedNodes.sort((a, b) => {
        // Primary sort based on selected option
        if (sortBy !== 'none') {
            let primarySort = 0;
            switch (sortBy) {
                case 'confidence-high':
                    primarySort = b.confidence - a.confidence;
                    break;
                case 'confidence-low':
                    primarySort = a.confidence - b.confidence;
                    break;
            }
            // If primary sort values are different, use primary sort
            if (primarySort !== 0) {
                return primarySort;
            }
        }
        // Secondary sort by node's updated_at (latest first)
        // Convert to Date objects for proper comparison
        const dateA = new Date(a.node.updated_at).getTime();
        const dateB = new Date(b.node.updated_at).getTime();
        return dateB - dateA; // Descending order (latest first)
    });

    const handleRemoveClassifications = async (nodeIds: string[]) => {
        if (item && nodeIds.length > 0) {
            try {
                // Remove classification for each selected node
                await Promise.all(
                    nodeIds.map(nodeId =>
                        classificationApi.removeClassification({
                            taxonomy_id: taxonomyId,
                            item_id: item.id,
                            node_id_to_remove: nodeId,
                        })
                    )
                );

                // Invalidate items query to refetch from database
                queryClient.invalidateQueries({ queryKey: ['itemsOfSelectedNode'], exact: false });
                queryClient.invalidateQueries({ queryKey: ['nodes'], exact: false });
            } catch (error) {
                toast({
                    title: "Failed to remove classifications",
                    description: "An error occurred while removing classifications",
                    variant: "destructive",
                });
            }
        }
    };


    const handleVerify = async (nodeIds: string[]) => {
        console.log("handleVerify", nodeIds);
        for (const nodeId of nodeIds) {
            await classificationApi.verifyClassification({
                taxonomy_id: taxonomyId,
                node_id: nodeId,
                item_ids_to_verify: [item.id],
                item_ids_to_unverify: [],
            });
        }
        queryClient.invalidateQueries({ queryKey: ['nodes', taxonomyId], exact: false });
        queryClient.invalidateQueries({ queryKey: ['itemsOfSelectedNode'], exact: false });
        queryClient.invalidateQueries({ queryKey: ['items'], exact: false });
    };

    return (
        <Card className="h-full flex flex-col">
            <CardHeader className="pb-4">
                <div className="flex items-start justify-between">
                    <div>
                        <CardTitle className="text-lg">Item Details</CardTitle>
                        <CardDescription className="text-xs mt-1">
                            ID: {item.id}
                        </CardDescription>
                    </div>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={onClose}
                    >
                        <X className="h-4 w-4" />
                    </Button>
                </div>
            </CardHeader>

            <CardContent className="flex-1 flex flex-col p-0 overflow-hidden">
                <div className="px-6 pb-4">
                    <h4 className="text-sm font-semibold mb-3">Content</h4>
                    <ScrollArea className="h-48 rounded-md border p-4">
                        <p className="text-sm whitespace-pre-wrap">
                            {item.content}
                        </p>
                    </ScrollArea>
                </div>

                <Separator />

                <div className="px-6 py-4 flex flex-col flex-1 overflow-hidden">
                    <div className="flex items-center justify-between mb-3">
                        <h4 className="text-sm font-semibold mb-3">
                            Classified Under ({classifiedNodes.length} nodes)
                        </h4>
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="sm" className="h-8 text-xs">
                                    <ArrowUpDown className="h-3 w-3 mr-1" />
                                    Sort
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                                <DropdownMenuItem
                                    onClick={() => setSortBy('confidence-high')}
                                    className="text-xs"
                                >
                                    <ArrowDown className="h-3 w-3 mr-2" />
                                    Confidence: High to Low
                                    {sortBy === 'confidence-high' && (
                                        <span className="ml-auto">✓</span>
                                    )}
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                    onClick={() => setSortBy('confidence-low')}
                                    className="text-xs"
                                >
                                    <ArrowUp className="h-3 w-3 mr-2" />
                                    Confidence: Low to High
                                    {sortBy === 'confidence-low' && (
                                        <span className="ml-auto">✓</span>
                                    )}
                                </DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenu>
                    </div>

                    <ScrollArea className="flex-1">
                        <SelectableList
                            items={classifiedNodes}
                            getItemId={item => item.node.id}
                            onRemoveSelected={handleRemoveClassifications}
                            onVerify={handleVerify}
                            showSelectAll={classifiedNodes.length > 0}
                            emptyMessage="No classifications found"
                            renderItem={(classifiedNode, isSelected, onToggle) => {
                                const classification = item.classified_as.find(c => c.node_id === classifiedNode.node.id);
                                const isVerified = classification?.is_verified || false;
                                const confidenceScore = Math.round(classifiedNode.confidence * 100);

                                return (
                                    <SelectableItem
                                        isSelected={isSelected}
                                        onToggle={onToggle}
                                        variant="card"
                                        checkboxPosition="embedded"
                                    >
                                        <SelectableItemHeader isSelected={isSelected} onToggle={onToggle}>
                                            {isVerified ? <Badge
                                                variant="outline"
                                                className="text-xs"
                                            >
                                                Verified
                                            </Badge> : <Badge className={cn(
                                                "text-xs font-medium",
                                                getConfidenceTextColor(classification?.confidence_score || 0)
                                            )}
                                                style={{
                                                    ...getConfidenceBackgroundStyle(classification?.confidence_score || 0, 1),
                                                }}>
                                                {confidenceScore}%
                                            </Badge>}
                                        </SelectableItemHeader>

                                        <SelectableItemContent>
                                            <h5 className="text-sm font-medium line-clamp-1">
                                                {classifiedNode.node.label}
                                            </h5>
                                            <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                                                {classifiedNode.node.description}
                                            </p>
                                        </SelectableItemContent>

                                        <SelectableItemFooter
                                            onItemClick={onNodeClick}
                                            item={classifiedNode.node.id}
                                            message="View node details"
                                        />
                                    </SelectableItem>
                                );
                            }}
                        />
                    </ScrollArea>

                    {isNodePickingMode && (
                        <Alert className="mt-4 pt-4" variant='default'>
                            <AlertDescription className="flex items-center justify-between">
                                <span>Pick a node that you want to add</span>
                                <Button
                                    variant="destructive"
                                    size="sm"
                                    onClick={onCancelNodePicking}
                                >
                                    Cancel
                                </Button>
                            </AlertDescription>
                        </Alert>
                    )}

                    {!isNodePickingMode && (
                        <div className="mt-4 pt-4 border-t">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={onStartNodePicking}
                                className="w-full"
                            >
                                <Plus className="h-4 w-4 mr-2" />
                                Add Classification
                            </Button>
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}, (prevProps, nextProps) => {
    // Custom comparison function for React.memo
    return (
        prevProps.item?.id === nextProps.item?.id &&
        prevProps.item?.content === nextProps.item?.content &&
        prevProps.nodes.length === nextProps.nodes.length &&
        prevProps.taxonomyId === nextProps.taxonomyId &&
        prevProps.isNodePickingMode === nextProps.isNodePickingMode &&
        // Compare item's classified_as array for changes
        JSON.stringify(prevProps.item?.classified_as) === JSON.stringify(nextProps.item?.classified_as) &&
        // Compare nodes array for changes (check if node IDs, labels, and descriptions are the same)
        JSON.stringify(prevProps.nodes.map(n => ({ id: n.id, label: n.label, description: n.description, updated_at: n.updated_at }))) ===
        JSON.stringify(nextProps.nodes.map(n => ({ id: n.id, label: n.label, description: n.description, updated_at: n.updated_at })))
    );
});

ItemDetailPanel.displayName = 'ItemDetailPanel';

export default ItemDetailPanel; 