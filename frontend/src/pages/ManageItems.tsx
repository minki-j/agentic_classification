import React, { useState, useEffect, useRef } from 'react';

import Layout from '@/components/Layout';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from '@/components/ui/pagination';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog';

import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import { taxonomiesApi, itemsApi, nodesApi } from '@/lib/api';
import { Taxonomy, TaxonomiesResponse, Item, ClassNode } from '@/models/types';
import { FileJson, Loader2, Download, Eye } from 'lucide-react';


const ITEMS_PER_PAGE = 20;

const ManageItems: React.FC = () => {
    const [taxonomies, setTaxonomies] = useState<Taxonomy[]>([]);
    const [selectedTaxonomyId, setSelectedTaxonomyId] = useState<string | null>(localStorage.getItem('selectedTaxonomyId'));
    const [items, setItems] = useState<Item[]>([]);
    const [nodes, setNodes] = useState<ClassNode[]>([]);
    const [totalItems, setTotalItems] = useState(0);
    const [unclassifiedItems, setUnclassifiedItems] = useState(0);
    const [currentPage, setCurrentPage] = useState(1);
    const [isLoading, setIsLoading] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [selectedItem, setSelectedItem] = useState<Item | null>(null);
    const [isDialogOpen, setIsDialogOpen] = useState(false);

    const fileInputRef = useRef<HTMLInputElement>(null);

    const { toast } = useToast();
    const { user } = useAuth();

    // Fetch taxonomies on mount
    useEffect(() => {
        fetchTaxonomies();
    }, []);

    // Fetch items when taxonomy changes or page changes
    useEffect(() => {
        fetchItems();
    }, [selectedTaxonomyId, currentPage]);

    // Fetch nodes when taxonomy changes
    useEffect(() => {
        if (selectedTaxonomyId) {
            fetchNodes();
            localStorage.setItem('selectedTaxonomyId', selectedTaxonomyId);
        }
    }, [selectedTaxonomyId]);

    const fetchTaxonomies = async () => {
        try {
            const response = await taxonomiesApi.list();
            const data: TaxonomiesResponse = response.data;
            setTaxonomies(data.taxonomies);

            // Validate saved taxonomy or select first if needed
            if (data.taxonomies.length > 0) {
                if (selectedTaxonomyId) {
                    const taxonomyExists = data.taxonomies.some(
                        t => t.id === selectedTaxonomyId
                    );
                    // If saved taxonomy doesn't exist anymore, clear it and set to first
                    if (!taxonomyExists) {
                        localStorage.removeItem('selectedTaxonomyId');
                        setSelectedTaxonomyId(data.taxonomies[0].id);
                    }
                } else {
                    // No saved taxonomy, set to first one
                    setSelectedTaxonomyId(data.taxonomies[0].id);
                }
            }
        } catch (error) {
            console.error('Failed to fetch taxonomies:', error);
        }
    };

    const fetchItems = async () => {
        if (!selectedTaxonomyId) {
            return;
        }
        setIsLoading(true);
        try {
            const skip = (currentPage - 1) * ITEMS_PER_PAGE;
            await itemsApi.list(selectedTaxonomyId, skip, ITEMS_PER_PAGE)
                .then(response => response.data)
                .then(data => {
                    setItems(data.items);
                    setTotalItems(data.count);
                    setUnclassifiedItems(data.unclassified_count);
                });
        } catch (error) {
            console.error('Failed to fetch items:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const fetchNodes = async () => {
        try {
            const response = await nodesApi.getNodes(selectedTaxonomyId);
            setNodes(response.nodes);
        } catch (error) {
            console.error('Failed to fetch nodes:', error);
        }
    };

    const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        if (!file.name.endsWith('.jsonl')) {
            toast({
                title: 'Invalid file type',
                description: 'Please upload a JSONL file',
                variant: 'destructive',
            });
            return;
        }

        setIsUploading(true);

        try {
            const text = await file.text();
            const lines = text.trim().split('\n');
            const items = [];
            const requiredFieldTypes = { content: 'string' };

            if (lines.length === 0) {
                toast({
                    title: 'File is empty',
                    description: 'It seems like you uploaded an empty file. Please check the file and try again.',
                    variant: 'destructive',
                });
                return;
            }

            for (const line of lines) {
                try {
                    const item = JSON.parse(line);
                    for (const [field, type] of Object.entries(requiredFieldTypes)) {
                        if (!item[field] || typeof item[field] !== type) {
                            toast({
                                title: 'Invalid item format',
                                description: `Invalid item: ${line}\nPlease make sure the items meet the following format: ${JSON.stringify(requiredFieldTypes)}`,
                                variant: 'destructive',
                            });
                            return;
                        }
                    }
                    items.push({ content: item.content });
                } catch (e) {
                    toast({
                        title: 'Error parsing line',
                        description: `Error parsing line: ${line}`,
                        variant: 'destructive',
                    });
                    return;
                }
            }

            await itemsApi.upload(items)
                .then((response) => response.data)
                .then((data) => {
                    setItems(prevItems => [...prevItems, ...data.items]);
                    setTotalItems(prevTotal => prevTotal + data.count);
                    const unclassifiedItems = data.unclassified_count;
                    setUnclassifiedItems(prevUnclassified => prevUnclassified + unclassifiedItems);
                });
        } catch (error) {
            console.error('Upload error:', error);
        } finally {
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
            setIsUploading(false);
        }
    };

    const handleExportAllItems = async () => {
        try {
            const response = await itemsApi.exportAll();
            const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');

            a.href = url;
            a.download = 'all_items.jsonl';
            a.click();

            URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Failed to export all items:', error);
        }
    };

    const handleItemClick = (item: Item) => {
        setSelectedItem(item);
        setIsDialogOpen(true);
    };

    const truncateContent = (content: string, maxLength = 150) => {
        if (content.length <= maxLength) return content;
        return content.substring(0, maxLength) + '...';
    };

    const totalPages = Math.ceil(totalItems / ITEMS_PER_PAGE);

    const getItemsForTaxonomy = (items: Item[], taxonomyId: string) => {
        // Currently, all items are shared across taxonomies
        // In the future, I need to filter based on classification
        return items;
    };

    const getNodeLabel = (nodeId: string) => {
        const node = nodes.find(n => n.id === nodeId);
        return node ? node.label : "Node Label Not Found";
    };

    return (
        <Layout>
            <h1 className="hidden">
                Manage Items
            </h1>
            <div className="space-y-6">
                <div className="flex justify-between items-end gap-2">
                    <div className="flex gap-2">
                        <TooltipProvider>
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <div>
                                        <AlertDialog>
                                            <AlertDialogTrigger asChild>
                                                <Button
                                                    variant="outline"
                                                    disabled={!user?.is_paid_user}
                                                >
                                                    Delete All Items
                                                </Button>
                                            </AlertDialogTrigger>
                                            {user?.is_paid_user && (
                                                <AlertDialogContent>
                                                    <AlertDialogHeader>
                                                        <AlertDialogTitle>
                                                            Delete All Items
                                                        </AlertDialogTitle>
                                                        <AlertDialogDescription>
                                                            Are you sure you want to delete all items in this taxonomy? This action cannot be undone.
                                                        </AlertDialogDescription>
                                                    </AlertDialogHeader>
                                                    <AlertDialogFooter>
                                                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                                                        <AlertDialogAction
                                                            className="bg-red-600 hover:bg-red-700"
                                                            onClick={async () => {
                                                                try {
                                                                    await itemsApi.deleteAll();
                                                                    setItems([]);
                                                                    setTotalItems(0);
                                                                    setUnclassifiedItems(0);
                                                                    toast({
                                                                        title: "Items deleted",
                                                                        description: "All items have been deleted successfully.",
                                                                    });
                                                                } catch (error) {
                                                                    toast({
                                                                        title: "Error deleting items",
                                                                        description: "Failed to delete items. Please try again.",
                                                                        variant: "destructive",
                                                                    });
                                                                }
                                                            }}
                                                        >
                                                            Delete All Items
                                                        </AlertDialogAction>
                                                    </AlertDialogFooter>
                                                </AlertDialogContent>
                                            )}
                                        </AlertDialog>
                                    </div>
                                </TooltipTrigger>
                                {!user?.is_paid_user && (
                                    <TooltipContent>
                                        <p>This feature is available for paid users only</p>
                                    </TooltipContent>
                                )}
                            </Tooltip>
                        </TooltipProvider>
                    </div>
                    <div className="flex gap-2">
                        <Select value={selectedTaxonomyId || undefined} onValueChange={setSelectedTaxonomyId}>
                            <SelectTrigger className="w-[350px]">
                                <SelectValue placeholder="Select a taxonomy" />
                            </SelectTrigger>
                            <SelectContent>
                                {taxonomies.map((taxonomy) => (
                                    <SelectItem key={taxonomy.id} value={taxonomy.id}>
                                        {taxonomy.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <TooltipProvider>
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <span>
                                        <Button
                                            variant="outline"
                                            onClick={handleExportAllItems}
                                            disabled={!user?.is_paid_user}
                                        >
                                            Export All Items
                                        </Button>
                                    </span>
                                </TooltipTrigger>
                                {!user?.is_paid_user && (
                                    <TooltipContent>
                                        <p>This feature is available for paid users only</p>
                                    </TooltipContent>
                                )}
                            </Tooltip>
                        </TooltipProvider>
                    </div>
                </div>

                <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                    <Card>
                        <CardHeader>
                            <CardTitle>Total Items</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <p className="text-2xl font-bold">{totalItems}</p>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Unclassified Items</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <p className="text-2xl font-bold">{unclassifiedItems}</p>
                        </CardContent>
                    </Card>

                    <Card >
                        <CardHeader>
                            <CardTitle>Add Items</CardTitle>
                            <CardDescription>
                                {user?.is_paid_user
                                    ? "Upload a JSONL file with items"
                                    : "Upgrade to upload items"
                                }
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-4">
                                <div className="flex items-center gap-2">
                                    <FileJson className="h-5 w-5 text-muted-foreground" />
                                    <Label htmlFor="file-upload" className="text-sm text-muted-foreground">
                                        Each line should be a JSON object with a "content" field
                                    </Label>
                                </div>
                                <div className="flex items-center gap-2 text-sm">
                                    <Download className="h-4 w-4 text-muted-foreground" />
                                    <a
                                        href="/sample-items.jsonl"
                                        download
                                        className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 underline"
                                    >
                                        Download sample JSONL file
                                    </a>
                                </div>
                                <TooltipProvider>
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <div>
                                                <Input
                                                    id="file-upload"
                                                    ref={fileInputRef}
                                                    type="file"
                                                    accept=".jsonl"
                                                    onChange={handleFileUpload}
                                                    disabled={isUploading || !user?.is_paid_user}
                                                    className={user?.is_paid_user ? "cursor-pointer" : "cursor-not-allowed opacity-50"}
                                                />
                                            </div>
                                        </TooltipTrigger>
                                        {!user?.is_paid_user && (
                                            <TooltipContent>
                                                <p>This feature is available for paid users only</p>
                                            </TooltipContent>
                                        )}
                                    </Tooltip>
                                </TooltipProvider>
                                {isUploading && (
                                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                        Uploading...
                                    </div>
                                )}
                                {!user?.is_paid_user && (
                                    <div className="text-sm text-muted-foreground italic">
                                        Upload feature is available for paid users only
                                    </div>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {selectedTaxonomyId ? (
                    <Card>
                        <CardHeader>
                            <CardTitle>Items List</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {isLoading ? (
                                <div className="flex items-center justify-center py-8">
                                    <Loader2 className="h-8 w-8 animate-spin" />
                                </div>
                            ) : items.length === 0 ? (
                                <Alert>
                                    <AlertDescription>
                                        No items found. Upload some items to get started.
                                    </AlertDescription>
                                </Alert>
                            ) : (
                                <>
                                    <div className="grid gap-4 md:grid-cols-2">
                                        {getItemsForTaxonomy(items, selectedTaxonomyId).map((item) => (
                                            <Card
                                                key={item.id}
                                                className="cursor-pointer hover:shadow-md transition-shadow"
                                                onClick={() => handleItemClick(item)}
                                            >
                                                <CardContent className="p-4">
                                                    <div className="space-y-3">
                                                        <div className="flex items-start justify-between">
                                                            <p className="text-sm text-gray-600 dark:text-gray-400 flex-1">
                                                                {truncateContent(item.content)}
                                                            </p>
                                                            <Eye className="h-4 w-4 text-gray-400 ml-2 flex-shrink-0" />
                                                        </div>

                                                        {item.classified_as.length > 0 ? (
                                                            <div className="flex flex-wrap gap-2">
                                                                {item.classified_as.slice(0, 2).map((classification, index) => (
                                                                    <Badge key={index} variant="secondary" className="text-xs">
                                                                        {getNodeLabel(classification.node_id)}
                                                                    </Badge>
                                                                ))}
                                                                {item.classified_as.length > 2 && (
                                                                    <Badge variant="outline" className="text-xs">
                                                                        +{item.classified_as.length - 2} more
                                                                    </Badge>
                                                                )}
                                                            </div>
                                                        ) : (
                                                            <Badge variant="outline" className="text-xs">
                                                                Unclassified
                                                            </Badge>
                                                        )}
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))}
                                    </div>

                                    {totalPages > 1 && (
                                        <Pagination className="mt-6">
                                            <PaginationContent>
                                                <PaginationItem>
                                                    <PaginationPrevious
                                                        onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                                                        className={currentPage === 1 ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                                                    />
                                                </PaginationItem>

                                                {[...Array(totalPages)].map((_, i) => (
                                                    <PaginationItem key={i}>
                                                        <PaginationLink
                                                            onClick={() => setCurrentPage(i + 1)}
                                                            isActive={currentPage === i + 1}
                                                            className="cursor-pointer"
                                                        >
                                                            {i + 1}
                                                        </PaginationLink>
                                                    </PaginationItem>
                                                ))}

                                                <PaginationItem>
                                                    <PaginationNext
                                                        onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                                                        className={currentPage === totalPages ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                                                    />
                                                </PaginationItem>
                                            </PaginationContent>
                                        </Pagination>
                                    )}
                                </>
                            )}
                        </CardContent>
                    </Card>
                ) : (
                    <Card className="flex flex-col items-center justify-center h-full p-10">
                        <CardHeader>
                            <CardTitle>No taxonomy selected</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <p>Please select a taxonomy to view items</p>
                        </CardContent>
                    </Card>
                )}
            </div>

            {/* Item Detail Dialog */}
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>Item Details</DialogTitle>
                        <DialogDescription>
                            Full content and classification information
                        </DialogDescription>
                    </DialogHeader>

                    {selectedItem && (
                        <div className="space-y-6">
                            {/* Item Content */}
                            <div>
                                <h3 className="font-semibold mb-2">Content</h3>
                                <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                                    <p className="text-sm whitespace-pre-wrap">{selectedItem.content}</p>
                                </div>
                            </div>

                            {/* Classifications */}
                            <div>
                                <h3 className="font-semibold mb-2">Classifications</h3>
                                {selectedItem.classified_as.length > 0 ? (
                                    <div className="space-y-3">
                                        {selectedItem.classified_as.map((classification, index) => (
                                            <div key={index} className="flex items-center justify-between p-3 border rounded-lg">
                                                <div>
                                                    <span className="font-medium">{getNodeLabel(classification.node_id)}</span>
                                                </div>
                                                <Badge variant="secondary">
                                                    {(classification.confidence_score * 100).toFixed(1)}% confidence
                                                </Badge>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="p-4 border rounded-lg text-center text-muted-foreground">
                                        <p>This item has not been classified yet.</p>
                                    </div>
                                )}
                            </div>

                            {/* Item Metadata */}
                            <div>
                                <h3 className="font-semibold mb-2">Metadata</h3>
                                <div className="grid grid-cols-2 gap-4 text-sm">
                                    <div>
                                        <span className="font-medium">Item ID:</span>
                                        <p className="text-muted-foreground break-all">{selectedItem.id}</p>
                                    </div>
                                    <div>
                                        <span className="font-medium">Classifications:</span>
                                        <p className="text-muted-foreground">{selectedItem.classified_as.length}</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </DialogContent>
            </Dialog>
        </Layout>
    );
};

export default ManageItems; 