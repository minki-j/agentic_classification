import React, { useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from '@/hooks/use-toast';
import { ChevronLeft, ChevronRight, Activity, Loader2, CheckCircle } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { SelectableList, SelectableItem, SelectableItemHeader, SelectableItemFooter, SelectableItemContent } from '@/components/SelectableList';

import { classificationApi } from '@/lib/api';
import { Item, NodesResponse } from '@/models/types';

interface ClassificationLiveUpdatePanelProps {
    items: Item[];
    nodesData: NodesResponse;
    taxonomyId: string;
    currentPage: number;
    classificationCompleted: boolean;
    itemToCurrentParentIdsMap: Map<string, string[]>;
    setCurrentPage: React.Dispatch<React.SetStateAction<number>>;
    onNodeClick?: (nodeId: string) => void;
    onHighlightNodes: (nodeIds: string[]) => void;
    onVerify: (itemId: string, nodeIds: string[]) => void;
}

export const ClassificationLiveUpdatePanel: React.FC<ClassificationLiveUpdatePanelProps> = ({
    items: items,
    nodesData,
    taxonomyId,
    classificationCompleted,
    itemToCurrentParentIdsMap,
    currentPage,
    setCurrentPage,
    onNodeClick,
    onHighlightNodes,
    onVerify,
}) => {
    const queryClient = useQueryClient();

    const [completedItemIds, setCompletedItemIds] = useState<string[]>([]);

    useEffect(() => {
        // When classification is completed, set isCompleteForEachItem to true for all items
        if (classificationCompleted) {
            setCompletedItemIds(items.map(item => item.id));
        }
    }, [classificationCompleted]);

    // Highlight nodes when current item changes
    useEffect(() => {
        const nodeIds = items[currentPage]?.classified_as.map(c => c.node_id) || [];
        onHighlightNodes(nodeIds);
    }, [items, currentPage]);

    const handleNodeClick = (nodeId: string) => {
        if (onNodeClick) {
            onNodeClick(nodeId);
        }
    };

    const handleVerify = () => {
        onVerify(items[currentPage].id, items[currentPage].classified_as.map(c => c.node_id));
        if (items.length === currentPage + 1) {
            setCurrentPage(currentPage - 1);
        }
    };

    const handleRemoveClassifications = async (nodeIds: string[]) => {
        if (nodeIds.length > 0) {
            try {
                // Remove classification for each selected node
                await Promise.all(
                    nodeIds.map(nodeId =>
                        classificationApi.removeClassification({
                            taxonomy_id: taxonomyId!,
                            item_id: items[currentPage].id,
                            node_id_to_remove: nodeId,
                        })
                    )
                );

                // Invalidate items query to refetch from database
                queryClient.invalidateQueries({ queryKey: ['itemsClassificationLiveUpdate'], exact: false });
                queryClient.invalidateQueries({ queryKey: ['itemsOfSelectedNode'], exact: false });
                queryClient.invalidateQueries({ queryKey: ['nodes'], exact: false });

                // Update local state to reflect the changes immediately
                const updatedClassifications = items[currentPage].classified_as.filter(
                    c => !nodeIds.includes(c.node_id)
                );

                // Update the items array to reflect the change
                items[currentPage] = {
                    ...items[currentPage],
                    classified_as: updatedClassifications
                };

            } catch (error) {
                toast({
                    title: "Failed to remove classifications",
                    description: "An error occurred while removing classifications",
                    variant: "destructive",
                });
            }
        }
    };

    const goToPrevious = () => {
        setCurrentPage(prev => Math.max(0, prev - 1));
    };

    const goToNext = () => {
        setCurrentPage(prev => Math.min(items.length - 1, prev + 1));
    };

    if (!items.length) {
        return (
            <Card className="h-full flex flex-col">
                <CardHeader className="pb-4">
                    <div className="flex items-center gap-2">
                        <Activity className="h-5 w-5 text-blue-500" />
                        <CardTitle className="text-lg">Classification Progress</CardTitle>
                    </div>
                </CardHeader>
                <CardContent className="flex-1 flex items-center justify-center">
                    <p className="text-muted-foreground text-center">
                        No items being classified.<br />
                        Click "Classify Items" to start.
                    </p>
                </CardContent>
            </Card>
        );
    }

    const isCurrentItemFinishedClassification = completedItemIds.includes(items[currentPage].id) || itemToCurrentParentIdsMap.get(items[currentPage].id)?.length === 0;

    // Map classifications with node details
    const classificationsWithNodes = items[currentPage]?.classified_as.map(classification => ({
        classification,
        node: nodesData?.nodes.find(n => n.id === classification.node_id)
    })) || [];

    return (
        <Card className="h-full flex flex-col">
            {/* Header */}
            <CardHeader className="pb-4">
                <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                        <Activity className="h-5 w-5 text-green-500" />
                        <CardTitle className="text-lg">Classification Progress</CardTitle>
                    </div>
                    <div className="text-sm text-muted-foreground">
                        Item {currentPage + 1} of {items.length}
                    </div>
                </div>
                <CardDescription className="text-xs">
                    Item ID: {items[currentPage]?.id || 'N/A'}
                </CardDescription>

            </CardHeader>

            {/* Content */}
            <CardContent className="flex-1 flex flex-col p-0 overflow-hidden">
                {items[currentPage] && (
                    <>
                        {/* Item content */}
                        <div className="px-6 pb-4">
                            <h4 className="text-sm font-semibold mb-3">Content</h4>
                            {items[currentPage] ? (
                                <ScrollArea className="rounded-md border p-4">
                                    <p className="text-sm whitespace-pre-wrap">
                                        {items[currentPage].content || 'Error fetching item content'}
                                    </p>
                                </ScrollArea>
                            ) : (
                                <div className="flex items-center gap-2 text-sm text-muted-foreground p-4 border rounded-md">
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    Loading item content...
                                </div>
                            )}
                        </div>

                        <Separator />

                        {/* Classification results */}
                        <div className="px-6 py-4 flex-1 flex flex-col overflow-hidden">
                            <h4 className="text-sm font-semibold mb-3">
                                Classified Under ({items[currentPage].classified_as.length} nodes)
                            </h4>


                            <ScrollArea className="flex-1">
                                <SelectableList
                                    items={classificationsWithNodes}
                                    getItemId={item => item.classification.node_id}
                                    onRemoveSelected={handleRemoveClassifications}
                                    showSelectAll={true}
                                    renderItem={(item, isSelected, onToggle) => (
                                        <SelectableItem
                                            isSelected={isSelected}
                                            onToggle={onToggle}
                                            variant="card"
                                            checkboxPosition="embedded"
                                        >
                                            <SelectableItemHeader isSelected={isSelected} onToggle={onToggle}>
                                                <Badge variant="outline" className="text-xs">
                                                    {Math.round(item.classification.confidence_score * 100)}%
                                                </Badge>
                                            </SelectableItemHeader>

                                            <SelectableItemContent>
                                                <h5 className="text-sm font-medium line-clamp-1">
                                                    {item.node.label}
                                                </h5>
                                                <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                                                    {item.node.description}
                                                </p>
                                            </SelectableItemContent>

                                            <SelectableItemFooter
                                                onItemClick={handleNodeClick}
                                                item={item.node.id}
                                                message="View node details"
                                            />
                                        </SelectableItem>

                                    )}
                                />

                                {isCurrentItemFinishedClassification && items[currentPage].classified_as.length === 0 && (
                                    <p className="text-sm text-muted-foreground">
                                        Doesn't belong to any category.
                                    </p>
                                )}
                            </ScrollArea>
                        </div>

                        <Separator />

                        {/* Bottom action buttons */}
                        <div className="px-6 py-4">
                            <div className="flex items-center justify-between">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={goToPrevious}
                                    disabled={currentPage === 0}
                                >
                                    <ChevronLeft className="h-4 w-4" />
                                    Previous
                                </Button>

                                {isCurrentItemFinishedClassification ?
                                    <Button
                                        size="sm"
                                        variant="default"
                                        onClick={handleVerify}
                                        className="bg-green-600 hover:bg-green-700"
                                    >
                                        <CheckCircle className="h-4 w-4 mr-1" />
                                        Verify
                                    </Button>
                                    : <Loader2 className="h-4 w-4 animate-spin" />}

                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={goToNext}
                                    disabled={currentPage === items.length - 1}
                                >
                                    Next
                                    <ChevronRight className="h-4 w-4" />
                                </Button>
                            </div>
                        </div>
                    </>
                )}
            </CardContent>
        </Card>
    );
};

export default ClassificationLiveUpdatePanel;
