import React, { useState, useEffect } from 'react';
import { QueryClient, useQuery, useQueryClient } from '@tanstack/react-query';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { X, Loader2, ArrowUpDown, ArrowUp, ArrowDown, Edit2, Save, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { ClassNode, Item } from '@/models/types';
import { classificationApi, nodesApi } from '@/lib/api';
import { getConfidenceBackgroundStyle, getConfidenceTextColor } from '@/lib/utils';
import { cn, sortItems, isRecentlyUpdated } from '@/lib/utils';
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
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { useToast } from '@/hooks/use-toast';

interface NodeDetailPanelProps {
    node: ClassNode | null;
    items: Item[];
    loadingItems: boolean;
    taxonomyId: string;
    isDspyRunning: boolean;
    onClose: () => void;
    onItemClick: (item: Item) => void;
    setIsDspyRunning: (isDspyRunning: boolean) => void;
}

type SortOption = 'confidence-high' | 'confidence-low' | 'none';

const MIN_VERIFIED_ITEMS_FOR_DSPY = 15;

const NodeDetailPanel: React.FC<NodeDetailPanelProps> = React.memo(({ node, items, loadingItems, taxonomyId, isDspyRunning, onClose, onItemClick, setIsDspyRunning }) => {
    console.info("node detail panel remounted");
    const [sortBy, setSortBy] = useState<SortOption>('none');
    const [sortedItems, setSortedItems] = useState<Item[]>([]);
    const [isDeleting, setIsDeleting] = useState(false);
    const [isEditMode, setIsEditMode] = useState(false);
    const [editedLabel, setEditedLabel] = useState('');
    const [editedDescription, setEditedDescription] = useState('');
    const [isSaving, setIsSaving] = useState(false);
    const [showDeleteDialog, setShowDeleteDialog] = useState(false);
    const [isDeletingNode, setIsDeletingNode] = useState(false);
    const [hasEnoughVerifiedItemsForDspy, setHasEnoughVerifiedItemsForDspy] = useState(false);

    const { toast } = useToast();
    const queryClient = useQueryClient();

    // Initialize edit form when node changes
    useEffect(() => {
        if (node) {
            setEditedLabel(node.label);
            setEditedDescription(node.description);
            // Automatically enter edit mode for new nodes
            if (node.label === '' && node.description === '') {
                setIsEditMode(true);
            } else {
                setIsEditMode(false);
            }
        }
        if (items && node) {
            setSortedItems(sortItems(items, sortBy, node));
        }
    }, [node, items, sortBy]);

    useEffect(() => {
        const hasEnoughVerifiedItemsForDspy = items?.filter(item => item.classified_as.find(c => c.node_id === node?.id)?.is_verified).length >= MIN_VERIFIED_ITEMS_FOR_DSPY;
        setHasEnoughVerifiedItemsForDspy(hasEnoughVerifiedItemsForDspy);
    }, [items, node]);

    // Auto-focus and select title when entering edit mode
    useEffect(() => {
        if (isEditMode) {
            // Small delay to ensure DOM is updated
            setTimeout(() => {
                const input = document.getElementById('node-label') as HTMLInputElement;
                if (input) {
                    input.focus();
                    input.select();
                }
            }, 0);
        }
    }, [isEditMode]);

    const handleSave = async () => {
        if (!node) return;

        try {
            setIsSaving(true);

            // Update existing node
            await nodesApi.updateNode(taxonomyId, node.id, {
                label: editedLabel,
                description: editedDescription,
            });

            toast({
                title: "Node updated",
                description: "Node details have been saved successfully",
            });

            // Invalidate queries to refresh data
            queryClient.invalidateQueries({ queryKey: ['nodes', taxonomyId] });

            setIsEditMode(false);
        } catch (error) {
            toast({
                title: "Failed to save node",
                description: "An error occurred while saving node details",
                variant: "destructive",
            });
        } finally {
            setIsSaving(false);
        }
    };

    const handleCancel = () => {
        if (node) {
            setEditedLabel(node.label);
            setEditedDescription(node.description);
        }
        setIsEditMode(false);
    };

    const hasChanges = node && (editedLabel !== node.label || editedDescription !== node.description);

    if (!node) {
        return (
            <Card className="h-full flex items-center justify-center">
                <CardContent>
                    <p className="text-muted-foreground">Select a node to view details</p>
                </CardContent>
            </Card>
        );
    }

    const handleRemoveItems = async (itemIds: string[]) => {
        if (itemIds.length > 0) {
            try {
                setIsDeleting(true);
                await Promise.all(
                    itemIds.map(itemId =>
                        classificationApi.removeClassification({
                            taxonomy_id: taxonomyId,
                            item_id: itemId,
                            node_id_to_remove: node.id,
                        })
                    )
                );

                // Invalidate items query to refetch from database
                queryClient.invalidateQueries({ queryKey: ['itemsOfSelectedNode'], exact: false });
                queryClient.invalidateQueries({ queryKey: ['nodes'], exact: false });

                // Show success toast
                toast({
                    title: "Items removed",
                    description: `Removed ${itemIds.length} item${itemIds.length > 1 ? 's' : ''} from this node`,
                });
                setIsDeleting(false);
            } catch (error) {
                toast({
                    title: "Failed to remove items",
                    description: "An error occurred while removing items",
                    variant: "destructive",
                });
                setIsDeleting(false);
            }
        }
    };

    const handleDeleteNode = async () => {
        if (!node) return;

        try {
            setIsDeletingNode(true);
            await nodesApi.deleteNode(taxonomyId, node.id);
            await classificationApi.removeClassificationItemsOnly({
                taxonomy_id: taxonomyId,
                item_ids: items.map(item => item.id),
                node_id_to_remove: node.id,
            })

            setIsDeletingNode(false);
            // Invalidate queries to refresh the data
            queryClient.invalidateQueries({ queryKey: ['nodes', taxonomyId], exact: false });
            queryClient.invalidateQueries({ queryKey: ['itemsOfSelectedNode'], exact: false });

            // Show success toast
            toast({
                title: "Node deleted",
                description: `Successfully deleted "${node.label}"`,
            });

            // Close the panel and dialog
            setShowDeleteDialog(false);
            onClose();
        } catch (error: any) {
            toast({
                title: "Failed to delete node",
                description: error.response?.data?.detail || "An error occurred while deleting the node",
                variant: "destructive",
            });
            setIsDeletingNode(false);
        }
    };

    const handleUseAsExample = async (itemIds: string[]) => {
        if (!node) return;
        await classificationApi.updateFewShotExamples({
            taxonomy_id: taxonomyId,
            node_id: node.id,
            item_ids_to_add: itemIds,
            item_ids_to_remove: [],
        });
        queryClient.invalidateQueries({ queryKey: ['nodes', taxonomyId], exact: false });
        queryClient.invalidateQueries({ queryKey: ['itemsOfSelectedNode'], exact: false });
    };

    const handleVerify = async (itemIds: string[]) => {
        if (!node) return;
        await classificationApi.verifyClassification({
            taxonomy_id: taxonomyId,
            node_id: node.id,
            item_ids_to_verify: itemIds,
            item_ids_to_unverify: [],
        });
        queryClient.invalidateQueries({ queryKey: ['nodes', taxonomyId], exact: false });
        queryClient.invalidateQueries({ queryKey: ['itemsOfSelectedNode'], exact: false });
    };

    const handleOptimizePromptWithDspy = async () => {
        if (!node) return;
        await classificationApi.optimizePromptWithDspy({
            taxonomy_id: taxonomyId,
            node_id: node.id,
        });
        toast({
            title: "Optimizing prompt with DSPy",
            description: "This may take a while. Please check back later.",
        });
    };

    return (
        <Card className="h-full flex flex-col">
            <CardHeader className="pb-4">
                <div className="flex items-start justify-between">
                    <div className="space-y-1 flex-1">
                        {isEditMode ? (
                            <div className="space-y-3">
                                <div>
                                    <Label htmlFor="node-label">Label</Label>
                                    <Input
                                        id="node-label"
                                        value={editedLabel}
                                        onChange={(e) => setEditedLabel(e.target.value)}
                                        className="mt-1"
                                        placeholder="Enter node label"
                                    />
                                </div>
                                <div>
                                    <Label htmlFor="node-description">Description</Label>
                                    <Textarea
                                        id="node-description"
                                        value={editedDescription}
                                        onChange={(e) => setEditedDescription(e.target.value)}
                                        className="mt-1 min-h-[80px]"
                                        placeholder="Enter node description"
                                    />
                                </div>
                                <div className="flex gap-2 justify-end">
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={handleCancel}
                                        disabled={isSaving}
                                    >
                                        Cancel
                                    </Button>
                                    <Button
                                        size="sm"
                                        onClick={handleSave}
                                        disabled={isSaving || !hasChanges}
                                    >
                                        {isSaving ? (
                                            <>
                                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                                Saving...
                                            </>
                                        ) : (
                                            <>
                                                <Save className="h-4 w-4 mr-2" />
                                                Save
                                            </>
                                        )}
                                    </Button>
                                </div>
                            </div>
                        ) : (
                            <>
                                <div className="flex items-start justify-between mb-3">
                                    <CardTitle className="text-lg">{node.label || 'No label'}</CardTitle>
                                    <div className="flex items-center gap-3 mt-1">
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-6 w-6"
                                            onClick={() => setIsEditMode(true)}
                                        >
                                            <Edit2 className="h-3 w-3" />
                                        </Button>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-6 w-6 text-destructive hover:text-destructive"
                                            onClick={() => setShowDeleteDialog(true)}
                                        >
                                            <Trash2 className="h-3 w-3" />
                                        </Button>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-6 w-6"
                                            onClick={onClose}
                                        >
                                            <X className="h-3 w-3" />
                                        </Button>
                                    </div>
                                </div>
                                <CardDescription className="mt-2">
                                    {node.description || 'No description'}
                                </CardDescription>
                            </>
                        )}
                    </div>
                </div>
            </CardHeader>
            <Separator />

            <CardContent className="flex flex-1 flex-col p-0 overflow-hidden">

                {loadingItems ? (
                    <div className="px-6 py-4 flex-1 flex flex-col items-center justify-center">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <p className="text-sm text-muted-foreground">Loading items...</p>
                    </div>
                ) : (
                    <div className="px-6 pt-4 flex flex-col flex-1 overflow-hidden">
                        <div className="flex items-center justify-between mb-3">
                            <h4 className="text-sm font-semibold">
                                Classified Items ({items?.length || 0})
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
                                items={sortedItems}
                                getItemId={item => item.id}
                                onRemoveSelected={handleRemoveItems}
                                onUseAsExample={handleUseAsExample}
                                onVerify={handleVerify}
                                isRemoving={isDeleting}
                                showSelectAll={sortedItems.length > 0}
                                emptyMessage="No items classified under this node"
                                renderItem={(sortedItems, isSelected, onToggle) => {
                                    const classification = sortedItems.classified_as.find(c => c.node_id === node.id);
                                    const confidenceScore = Math.round((classification?.confidence_score || 0) * 100);
                                    const isVerified = classification?.is_verified || false;
                                    const isExample = classification?.used_as_few_shot_example || false;
                                    const isRecent = isRecentlyUpdated(sortedItems, node.id);

                                    return (
                                        <SelectableItem
                                            isSelected={isSelected}
                                            onToggle={onToggle}
                                            variant="card"
                                            checkboxPosition="embedded"
                                        >
                                            <SelectableItemHeader isSelected={isSelected} onToggle={onToggle}>
                                                {isRecent && (
                                                    <Badge variant="outline" className="text-xs bg-blue-500 text-white">
                                                        New
                                                    </Badge>
                                                )}
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
                                                {isExample && (
                                                    <Badge variant="outline" className="text-xs">
                                                        Example
                                                    </Badge>
                                                )}
                                            </SelectableItemHeader>

                                            <SelectableItemContent>
                                                <p className="text-sm leading-relaxed line-clamp-3">
                                                    {sortedItems.content}
                                                </p>
                                            </SelectableItemContent>

                                            <SelectableItemFooter
                                                onItemClick={onItemClick}
                                                item={sortedItems}
                                                message="View item details"
                                            />
                                        </SelectableItem>
                                    );
                                }}
                            />
                        </ScrollArea>
                    </div>
                )}

                {/* <Separator className="" /> */}

                <div className="flex justify-end p-2 border-t border-gray-200 shadow-[0_-6px_12px_-4px_rgba(0,0,0,0.2)] z-10">
                    <Button variant="outline" size="sm" className="shadow-sm shadow-gray-200 border-gray-200 text-xs" onClick={() => {
                        handleOptimizePromptWithDspy();
                        setIsDspyRunning(true);
                    }} disabled={isDspyRunning || !hasEnoughVerifiedItemsForDspy}>
                        {isDspyRunning ? <div className="flex items-center"><Loader2 className="h-4 w-4 mr-2 animate-spin" />DSPy is running...</div> : hasEnoughVerifiedItemsForDspy ? "Optimize Few-Shot Examples with DSPy" : `Verify ${MIN_VERIFIED_ITEMS_FOR_DSPY} items to use DSPy`}
                    </Button>
                </div>
            </CardContent>

            <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Delete Node</AlertDialogTitle>
                        <AlertDialogDescription>
                            Are you sure you want to delete "{node?.label}"? This action cannot be undone.
                            {node && items?.length > 0 && (
                                <span className="block mt-2 font-semibold">
                                    Note: This node contains {items?.length} item{items?.length > 1 ? 's' : ''}.
                                    These items will no longer be classified under this node.
                                </span>
                            )}
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={isDeletingNode}>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={handleDeleteNode}
                            disabled={isDeletingNode}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                            {isDeletingNode ? (
                                <>
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    Deleting...
                                </>
                            ) : (
                                'Delete'
                            )}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </Card >
    );
}, (prevProps, nextProps) => {
    // Custom comparison function for React.memo
    return (
        prevProps.node?.id === nextProps.node?.id &&
        prevProps.node?.label === nextProps.node?.label &&
        prevProps.node?.description === nextProps.node?.description &&
        prevProps.items?.length === nextProps.items?.length &&
        prevProps.loadingItems === nextProps.loadingItems &&
        prevProps.taxonomyId === nextProps.taxonomyId &&
        prevProps.isDspyRunning === nextProps.isDspyRunning &&
        // Compare items array content by checking if all item IDs and contents are the same
        JSON.stringify(prevProps.items?.map(i => ({ id: i.id, content: i.content, classified_as: i.classified_as }))) ===
        JSON.stringify(nextProps.items?.map(i => ({ id: i.id, content: i.content, classified_as: i.classified_as })))
    );
});

NodeDetailPanel.displayName = 'NodeDetailPanel';

export default NodeDetailPanel; 