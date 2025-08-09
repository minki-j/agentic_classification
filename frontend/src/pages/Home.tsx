import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ReactFlowProvider } from 'reactflow';
import { Loader2, Play, LogOut, Home as HomeIcon, Package, GitForkIcon, Activity, Network, FolderTree, Settings } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';

import NoTaxonomy from '@/components/NoTaxonomy';
import NoNodes from '@/components/NoNodes';
import InfiniteCanvas from '@/components/InfiniteCanvas';
import NodeDetailPanel from '@/components/NodeDetailPanel';
import ItemDetailPanel from '@/components/ItemDetailPanel';
import ClassificationLiveUpdatePanel from '@/components/ClassificationLiveUpdatePanel';

import { useAuth } from '@/contexts/AuthContext';

import { cn } from '@/lib/utils';
import { taxonomiesApi, nodesApi, itemsApi, wsConnection, classificationApi } from '@/lib/api';

import { ClassNode, Item, ClassifierState, ROOT_NODE_ID, AI_MODELS, getModelsByProvider, getTierColor } from '@/models/types';

const Home: React.FC = () => {
    // Basic states
    const [isLayoutVertical, setIsLayoutVertical] = useState<boolean>(true);
    const [showSettingsDialog, setShowSettingsDialog] = useState<boolean>(false);
    const [classificationSettings, setClassificationSettings] = useState<Record<string, any> | null>(null);

    // States for node and item display
    const [selectedTaxonomyId, setSelectedTaxonomyId] = useState<string | null>(localStorage.getItem('selectedTaxonomyId'));
    const [selectedItem, setSelectedItem] = useState<Item | null>(null);
    const [selectedNode, setSelectedNode] = useState<ClassNode | null>(null);
    const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
    const [highlightedNodeIds, setHighlightedNodeIds] = useState<string[]>([]);

    // States for classification
    const [showLiveUpdatePanel, setShowLiveUpdatePanel] = useState<boolean>(false);
    const [liveUpdateCompleted, setLiveUpdateCompleted] = useState<boolean>(true);
    const [liveUpdateState, setLiveUpdateState] = useState<Item[]>([]);
    const [liveUpdateCurrentPage, setLiveUpdateCurrentPage] = useState(0);
    const [itemToCurrentParentIdsMap, setItemToCurrentParentIdsMap] = useState<Map<string, string[]>>(new Map());

    // States for manually adding classifications 
    const [isNodePickingMode, setIsNodePickingMode] = useState<boolean>(false);
    const [nodePickingItem, setNodePickingItem] = useState<Item | null>(null);
    const [isDspyRunning, setIsDspyRunning] = useState<boolean>(false);

    // Hooks
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const { user, logout } = useAuth();
    const { toast } = useToast();

    // Fetch taxonomies
    const { data: taxonomiesData, isLoading: loadingTaxonomies, error: taxonomiesError } = useQuery({
        queryKey: ['taxonomies'],
        queryFn: async () => {
            const response = await taxonomiesApi.list();
            return response.data;
        },
        refetchOnWindowFocus: false,
    });

    useEffect(() => {
        if (taxonomiesData?.taxonomies.length) {
            // Check if the saved taxonomy ID is still valid
            if (selectedTaxonomyId) {
                const taxonomyExists = taxonomiesData.taxonomies.some(
                    t => t.id === selectedTaxonomyId
                );
                // If saved taxonomy doesn't exist anymore, clear it and set to first
                if (!taxonomyExists) {
                    localStorage.removeItem('selectedTaxonomyId');
                    setSelectedTaxonomyId(taxonomiesData.taxonomies[0].id);
                }
            } else {
                // No saved taxonomy, set to first one
                setSelectedTaxonomyId(taxonomiesData.taxonomies[0].id);
            }
        } else {
            // If no taxonomies exist from the db, clear the selected taxonomy ID
            localStorage.removeItem('selectedTaxonomyId');
            setSelectedTaxonomyId(null);
        }
    }, [taxonomiesData]);

    // Save selected taxonomy to localStorage whenever it changes
    useEffect(() => {
        if (selectedTaxonomyId) {
            localStorage.setItem('selectedTaxonomyId', selectedTaxonomyId);
        }
    }, [selectedTaxonomyId]);

    // Update classification settings from taxonomy when it changes
    useEffect(() => {
        if (selectedTaxonomyId && taxonomiesData?.taxonomies) {
            const currentTaxonomy = taxonomiesData.taxonomies.find(
                t => t.id === selectedTaxonomyId
            );
            if (currentTaxonomy?.classifier_state) {
                setClassificationSettings({
                    batch_size: currentTaxonomy.classifier_state.batch_size,
                    models: currentTaxonomy.classifier_state.models,
                    majority_threshold: currentTaxonomy.classifier_state.majority_threshold,
                    total_invocations: currentTaxonomy.classifier_state.total_invocations
                });
            }
        }
    }, [selectedTaxonomyId, taxonomiesData]);

    // Fetch all nodes for selected taxonomy
    const { data: nodesData, isLoading: loadingNodes, error: nodesError } = useQuery({
        queryKey: ['nodes', selectedTaxonomyId],
        queryFn: async () => {
            if (!selectedTaxonomyId || taxonomiesData.count === 0) {
                throw new Error('No taxonomy selected');
            }
            const response = await nodesApi.getNodes(selectedTaxonomyId);
            return response;
        },
        enabled: !!selectedTaxonomyId,
        refetchOnWindowFocus: false,
    });

    // Fetch items of the selected node
    const { data: itemsOfSelectedNode, isLoading: loadingItemsOfSelectedNode } = useQuery({
        queryKey: ['itemsOfSelectedNode', selectedTaxonomyId, selectedNode],
        queryFn: async () => {
            if (selectedNode.items.length === 0) return [];
            const itemIdsOfSelectedNode = selectedNode?.items.map(item => item.item_id) || [];
            const response = await itemsApi.getMany(selectedTaxonomyId,
                itemIdsOfSelectedNode);
            return response.data.items;
        },
        enabled: !!selectedTaxonomyId && !!selectedNodeId && !!selectedNode,
        refetchOnWindowFocus: false,
    });

    // WebSocket connection
    useEffect(() => {
        wsConnection.connect();
        wsConnection.on('classification_update', websocketClassificationUpdate);
        wsConnection.on('dspy_update', websocketDspyUpdate);
        wsConnection.on('error', websocketError);

        return () => {
            wsConnection.off('classification_update', websocketClassificationUpdate);
            wsConnection.off('dspy_update', websocketDspyUpdate);
            wsConnection.off('error', websocketError);
            wsConnection.disconnect();
        };
    }, []);


    const websocketClassificationUpdate = async (data: any) => {
        if (data.display_type === 'none') {
            if (data.classification_completed) {
                setLiveUpdateCompleted(true);
            }
            if (data.classification_failed) {
                setLiveUpdateCompleted(true);
                console.error("classification failed: ", data);
            }
            // Refetch nodes and items when classification is completed or failed
            console.info("invalidating nodes and items");
            queryClient.invalidateQueries({ queryKey: ['nodes'], exact: false });
            queryClient.invalidateQueries({ queryKey: ['itemsOfSelectedNode'], exact: false });
        } else if (data.display_type === 'toast') {
            toast({
                title: data.title,
                description: data.description,
                variant: data.toast_type || 'default',
            });
        } else if (data.display_type === 'classify_items') {
            // classification updates from the backend via websocket to display the progress in real time
            if ('item_ids_to_classify' in data) {
                // In the beginning of classification, we get the item ids being classified from the backend.
                const existingItemIds = new Set(liveUpdateState.map(item => item.id));
                const new_item_ids = data.item_ids_to_classify.filter(item_id => !existingItemIds.has(item_id));
                setItemToCurrentParentIdsMap(prev => {
                    const map = new Map();
                    new_item_ids.forEach(item_id => {
                        map.set(item_id, [ROOT_NODE_ID]);
                    });
                    return map;
                });
                // Fetch items to get content
                const response = await itemsApi.getMany(selectedTaxonomyId,
                    new_item_ids);
                const items = response.data.items;

                setLiveUpdateState(prevState => {
                    const newItems: Item[] = new_item_ids
                        .map((item_id: string): Item => ({
                            id: item_id,
                            content: items.find(item => item.id === item_id)?.content || '',
                            classified_as: [],
                            created_at: '',
                            updated_at: '',
                        }));

                    // Append new items to existing state
                    return [...newItems, ...prevState];
                });
                setLiveUpdateCurrentPage(0)
            }

            // When classification is ongoing, we get the classified_as from the backend.
            // Each classified_as contains the the result for an item in the current hierarchy level.
            // If there are more levels to be classified or there are more items to be classified, we'll get more of this updates.
            if ('classified_as' in data && 'item_id' in data) {
                setLiveUpdateState(prevState =>
                    prevState.map((item) => {
                        if (item.id === data.item_id) {
                            return {
                                ...item,
                                classified_as: [...item.classified_as, ...data.classified_as],
                            };
                        }
                        return item;
                    })
                );
            }

            // We get item to parent_ids map, which is used to display the animated edges to indicate the branches that are being classified at the momment.
            if ('new_parent_ids' in data && 'item_id' in data) {
                setItemToCurrentParentIdsMap(prevState => {
                    const map = new Map(prevState);
                    map.set(data.item_id, data.new_parent_ids);
                    return map;
                });
            }
        } else {
            console.error('WS >>> Unknown display type: ', data);
        }
    };

    const websocketDspyUpdate = async (data: any) => {
        if ("demos" in data) {
            toast({
                title: "DSPy optimizer is done successfully!",
                description: data.message,
            });
            await updateExamplesWithDspyDemos(data.demos, data.node_id);
            setIsDspyRunning(false);
        } else {
            toast({
                title: "DSPy optimizer is running",
                description: data.message,
            });
        }

    }

    const websocketError = (data: any) => {
        toast({
            title: "Error",
            description: data.detail,
            variant: 'destructive',
        });
    };

    // Handle starting classification
    const handleStartClassification = async (taxonomyId: string) => {
        try {
            setLiveUpdateCompleted(false);
            setShowLiveUpdatePanel(true); // Auto-show panel when classification starts
            if (!classificationSettings) {
                toast({
                    title: "Classification Settings",
                    description: "Please set the classification settings first",
                });
                return;
            }
            await classificationApi.classify({
                taxonomy_id: taxonomyId,
                batch_size: classificationSettings.batch_size,
                models: classificationSettings.models,
                majority_threshold: classificationSettings.majority_threshold,
                total_invocations: classificationSettings.total_invocations,
            });
        } catch (error) {
            setLiveUpdateCompleted(true);
        }
    };

    const handleVerifyClassification = async (itemId: string, nodeIds: string[]) => {
        setLiveUpdateState(prevState =>
            prevState.filter(item => item.id !== itemId)
        );

        await Promise.all(
            nodeIds.map(nodeId =>
                classificationApi.verifyClassification({
                    taxonomy_id: selectedTaxonomyId,
                    node_id: nodeId,
                    item_ids_to_verify: [itemId],
                })
            )
        );

        queryClient.invalidateQueries({ queryKey: ['itemsOfSelectedNode'], exact: false });
        queryClient.invalidateQueries({ queryKey: ['nodes'], exact: false });
    };


    // Update selected node when nodesData or selectedNodeId changes.
    useEffect(() => {
        // selectedNode is passed to the node detail panel and we need to update it when we delete an item from the node detail panel, which will update nodesData.
        if (nodesData?.nodes.length) {
            setSelectedNode(nodesData.nodes.find(n => n.id === selectedNodeId) || null);
        }
    }, [nodesData, selectedNodeId]);

    // Update selected item when itemsOfSelectedNode changes. This happens when the item is deleted from the node detail panel
    useEffect(() => {
        if (selectedItem) {
            const fetchItem = async () => {
                const response = await itemsApi.getOne(selectedTaxonomyId, selectedItem.id);
                setSelectedItem(response.data.item);
            }
            fetchItem();
        }
    }, [itemsOfSelectedNode]);

    // Clear node picking mode when selected item changes or is cleared
    useEffect(() => {
        if (!selectedItem && isNodePickingMode) {
            handleCancelNodePicking();
        }
    }, [selectedItem, isNodePickingMode]);

    const handleNodeClick = useCallback((nodeId: string) => {
        if (isNodePickingMode && nodePickingItem) {
            // In node picking mode, add classification instead of selecting the node
            handleAddManualClassification(nodeId);
        } else {
            // Normal node selection
            setSelectedNodeId(nodeId);
        }
    }, [isNodePickingMode, nodePickingItem]);

    const handleItemClick = useCallback((item: Item) => {
        setShowLiveUpdatePanel(false);
        setSelectedItem(item);
    }, []);

    const handleStartNodePicking = useCallback(() => {
        // This is for the manual classification in item detail panel
        if (selectedItem) {
            setIsNodePickingMode(true);
            setNodePickingItem(selectedItem);
        }
    }, [selectedItem]);

    const handleCancelNodePicking = useCallback(() => {
        setIsNodePickingMode(false);
        setNodePickingItem(null);
    }, []);

    const handleNodeDetailClose = useCallback(() => {
        setSelectedNodeId(null);
    }, []);

    const handleItemDetailClose = useCallback(() => {
        setSelectedItem(null);
    }, []);

    const handleAddManualClassification = async (nodeId: string) => {
        if (!nodePickingItem || !selectedTaxonomyId) return;

        await classificationApi.addClassification({
            taxonomy_id: selectedTaxonomyId,
            item_id: nodePickingItem.id,
            node_id: nodeId,
            confidence_score: 1.0, // 100% confidence for manual classification
        });

        // Invalidate queries to refetch data
        queryClient.invalidateQueries({ queryKey: ['itemsOfSelectedNode'], exact: false });
        queryClient.invalidateQueries({ queryKey: ['nodes'], exact: false });

        // Cancel picking mode
        handleCancelNodePicking();

        // Show success toast
        toast({
            title: "Classification added",
            description: "Node has been added to this item's classifications",
        });

    };

    // Handler for creating a new node when connection is dropped on canvas
    const handleNodeCreate = async (parentNodeId: string, position: { x: number; y: number }) => {
        if (!selectedTaxonomyId) return;

        const savedNode = await nodesApi.createNode(selectedTaxonomyId, {
            parent_node_id: parentNodeId,
            label: '',
            description: '',
        });

        // Refresh nodes to include the new node
        await queryClient.invalidateQueries({ queryKey: ['nodes', selectedTaxonomyId] });

        // Select the new node for editing
        setSelectedNodeId(savedNode.id);
        setSelectedNode(savedNode);
        setSelectedItem(null);
    };

    // Handler for connecting nodes (updating parent)
    const handleEdgeConnect = async (parentId: string, childId: string) => {
        if (!selectedTaxonomyId) return;

        await nodesApi.updateNode(selectedTaxonomyId, childId, {
            parent_node_id: parentId,
        });

        // Refresh nodes
        queryClient.invalidateQueries({ queryKey: ['nodes', selectedTaxonomyId] });
    };

    // Handler for deleting edges (removing parent)
    const handleEdgeDelete = async (parentId: string, childId: string) => {
        await nodesApi.updateNode(selectedTaxonomyId, childId, {
            parent_node_id: "",
        });

        queryClient.invalidateQueries({ queryKey: ['nodes', selectedTaxonomyId] });
    };


    const updateExamplesWithDspyDemos = async (demos: string[], nodeId: string) => {
        const item_ids_to_add = await itemsApi.getIdsByListOfContent({
            content_list: demos,
        });

        await classificationApi.updateFewShotExamples({
            taxonomy_id: selectedTaxonomyId,
            node_id: nodeId,
            item_ids_to_add: item_ids_to_add.data,
            item_ids_to_remove: [],
        });

        queryClient.invalidateQueries({ queryKey: ['nodes', selectedTaxonomyId] });
        queryClient.invalidateQueries({ queryKey: ['itemsOfSelectedNode'] });
    };

    const getInitials = (name: string) => {
        return name
            .split(' ')
            .map((n) => n[0])
            .join('')
            .toUpperCase()
            .slice(0, 2);
    };

    const navigationItems = [
        { name: 'Home', href: '/', icon: HomeIcon },
        { name: 'Items', href: '/items', icon: Package },
        { name: 'Taxonomies', href: '/taxonomies', icon: GitForkIcon },
    ];

    return (
        <div className="h-screen flex flex-col bg-gray-50 dark:bg-gray-900">
            <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700 shrink-0" >
                <div className="px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-between items-center h-16">
                        <div className="flex items-center space-x-8">
                            <h1 className="text-xl font-semibold text-gray-900 dark:text-white whitespace-nowrap">
                                Classification Swarm
                            </h1>

                            <nav className="hidden md:flex items-center space-x-1">
                                {navigationItems.map((item) => {
                                    const Icon = item.icon;
                                    const isActive = item.href === '/';
                                    return (
                                        <Button
                                            key={item.href}
                                            variant="ghost"
                                            className={cn(
                                                "flex items-center px-3 py-2",
                                                isActive && "bg-gray-100 dark:bg-gray-700"
                                            )}
                                            onClick={() => navigate(item.href)}
                                        >
                                            <Icon className="h-4 w-4" />
                                            <span className="ml-1">{item.name}</span>
                                        </Button>
                                    );
                                })}
                            </nav>
                        </div>

                        <div className="flex items-center space-x-4">
                            {taxonomiesData?.taxonomies.length > 0 && (
                                <div className="flex items-center gap-4">
                                    <div className="flex items-center gap-4">
                                        <Select value={selectedTaxonomyId || undefined} onValueChange={setSelectedTaxonomyId}>
                                            <SelectTrigger className="w-[200px]">
                                                <SelectValue placeholder="Select a taxonomy" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {taxonomiesData?.taxonomies?.map((taxonomy) => (
                                                    <SelectItem key={taxonomy.id} value={taxonomy.id}>
                                                        {taxonomy.name}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="flex items-center gap-4">
                                        <Button variant="outline" size="sm" onClick={() => setIsLayoutVertical(!isLayoutVertical)}>
                                            {isLayoutVertical ? <Network className="h-4 w-4" /> : <FolderTree className="h-4 w-4" />}
                                        </Button>
                                        <Button
                                            variant={showLiveUpdatePanel ? "default" : "outline"}
                                            size="sm"
                                            onClick={() => setShowLiveUpdatePanel(!showLiveUpdatePanel)}
                                            disabled={!selectedTaxonomyId}
                                            className="relative"
                                        >
                                            <Activity className={cn(
                                                "h-4 w-4",
                                                !liveUpdateCompleted && "animate-pulse"
                                            )} />
                                            <span>Progress</span>
                                            {liveUpdateState.length > 0 && (
                                                <Badge
                                                    variant="destructive"
                                                    className="absolute -top-2 -right-2 h-5 w-5 p-0 flex items-center justify-center"
                                                >
                                                    {liveUpdateState.length}
                                                </Badge>
                                            )}
                                        </Button>
                                        <Button
                                            onClick={() => {
                                                if (selectedTaxonomyId) {
                                                    handleStartClassification(selectedTaxonomyId)
                                                }
                                            }}
                                            disabled={!selectedTaxonomyId || !liveUpdateCompleted}
                                        >
                                            <Play className="h-4 w-4" />
                                            <span>Classify Items</span>
                                        </Button>
                                        <Button
                                            variant="outline"
                                            size="icon"
                                            onClick={() => setShowSettingsDialog(true)}
                                            title="Classification Settings"
                                        >
                                            <Settings className="h-4 w-4" />
                                        </Button>
                                    </div>
                                </div>
                            )}
                            <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                    <Button variant="ghost" className="relative h-10 w-10 rounded-full">
                                        <Avatar className="h-10 w-10">
                                            <AvatarImage src={user.picture} alt={user.name} />
                                            <AvatarFallback>{getInitials(user.name)}</AvatarFallback>
                                        </Avatar>
                                    </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent className="w-56" align="end" forceMount>
                                    <DropdownMenuItem className="flex flex-col items-start">
                                        <div className="text-sm font-medium">{user.name}</div>
                                        <div className="text-xs text-gray-500">{user.email}</div>
                                    </DropdownMenuItem>
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem onClick={logout} className="text-red-600 dark:text-red-400">
                                        <LogOut className="mr-2 h-4 w-4" />
                                        <span>Log out</span>
                                    </DropdownMenuItem>
                                </DropdownMenuContent>
                            </DropdownMenu>
                        </div>
                    </div>
                </div>
            </header >

            {/* Main Content */}
            <div className="flex-1 overflow-hidden">
                {loadingTaxonomies ? (
                    <div className="flex items-center justify-center h-full">
                        <Loader2 className="h-8 w-8 animate-spin" />
                    </div>
                ) : taxonomiesError ? (
                    <div className="flex items-center justify-center h-full">
                        <Card className="">
                            <CardHeader>
                                <CardTitle>Failed to load taxonomies</CardTitle>
                            </CardHeader>
                            <CardDescription>
                                Failed to load taxonomies. Please try again.
                            </CardDescription>
                        </Card>
                    </div>
                ) : !taxonomiesData?.taxonomies.length ? (
                    <NoTaxonomy />
                ) : loadingNodes ? (
                    <div className="flex items-center justify-center h-full">
                        <Loader2 className="h-8 w-8 animate-spin" />
                    </div>
                ) : nodesError ? (
                    <div className="flex items-center justify-center h-full">
                        <Card className="">
                            <CardHeader>
                                <CardTitle>Failed to load nodes</CardTitle>
                            </CardHeader>
                            <CardDescription>
                                Failed to load nodes. Please try again.
                            </CardDescription>
                        </Card>
                    </div>
                ) : !nodesData?.nodes.length ? (
                    <NoNodes selectedTaxonomyId={selectedTaxonomyId} />
                ) : (
                    <ResizablePanelGroup direction="horizontal" className="h-full">
                        {/* Left Panel */}
                        <ResizablePanel
                            id="left-panel"
                            order={1}
                            defaultSize={25}
                            minSize={2}
                            maxSize={80}
                            collapsible={true}
                        >
                            <div className="h-full relative">
                                <NodeDetailPanel
                                    node={selectedNode}
                                    items={itemsOfSelectedNode || []}
                                    loadingItems={loadingItemsOfSelectedNode}
                                    taxonomyId={selectedTaxonomyId || ''}
                                    isDspyRunning={isDspyRunning}
                                    onClose={handleNodeDetailClose}
                                    onItemClick={handleItemClick}
                                    setIsDspyRunning={setIsDspyRunning}
                                />
                            </div>
                        </ResizablePanel>

                        <ResizableHandle withHandle />

                        {/* Center Canvas */}
                        <ResizablePanel id="center-panel" order={2} defaultSize={50}>
                            <ReactFlowProvider>
                                <InfiniteCanvas
                                    nodes={nodesData.nodes}
                                    selectedNodeId={selectedNodeId}
                                    selectedItem={selectedItem}
                                    highlightedNodeIds={highlightedNodeIds}
                                    showClassificationPanel={showLiveUpdatePanel}
                                    isLayoutVertical={isLayoutVertical}
                                    parentNodeIdsNeedAnimatedEdges={itemToCurrentParentIdsMap.get(liveUpdateState[liveUpdateCurrentPage]?.id) || []}
                                    onNodeClick={handleNodeClick}
                                    onNodeCreate={handleNodeCreate}
                                    onEdgeConnect={handleEdgeConnect}
                                    onEdgeDelete={handleEdgeDelete}
                                />
                            </ReactFlowProvider>
                        </ResizablePanel>

                        <ResizableHandle withHandle />

                        {/* Right Panels */}
                        {showLiveUpdatePanel ? (
                            <>
                                <ResizablePanel
                                    id="right-classification-panel"
                                    order={3}
                                    defaultSize={25}
                                    minSize={2}
                                    maxSize={40}
                                    collapsible={true}
                                >
                                    <div className="h-full relative">
                                        <ClassificationLiveUpdatePanel
                                            items={liveUpdateState}
                                            nodesData={nodesData}
                                            taxonomyId={selectedTaxonomyId}
                                            currentPage={liveUpdateCurrentPage}
                                            classificationCompleted={liveUpdateCompleted}
                                            itemToCurrentParentIdsMap={itemToCurrentParentIdsMap}
                                            setCurrentPage={setLiveUpdateCurrentPage}
                                            onNodeClick={handleNodeClick}
                                            onHighlightNodes={setHighlightedNodeIds}
                                            onVerify={handleVerifyClassification}
                                        />
                                    </div>
                                </ResizablePanel>
                                <ResizableHandle withHandle />
                            </>
                        ) : (
                            <ResizablePanel
                                id="right-item-panel"
                                order={3}
                                defaultSize={showLiveUpdatePanel ? 20 : 25}
                                minSize={2}
                                maxSize={40}
                                collapsible={true}
                            >
                                <div className="h-full relative">
                                    <ItemDetailPanel
                                        item={selectedItem}
                                        nodes={nodesData?.nodes || []}
                                        taxonomyId={selectedTaxonomyId || ''}
                                        onClose={handleItemDetailClose}
                                        onNodeClick={handleNodeClick}
                                        isNodePickingMode={isNodePickingMode}
                                        onStartNodePicking={handleStartNodePicking}
                                        onCancelNodePicking={handleCancelNodePicking}
                                    />
                                </div>
                            </ResizablePanel>
                        )}
                    </ResizablePanelGroup>
                )}
            </div>

            {/* Settings Dialog */}
            <Dialog open={showSettingsDialog} onOpenChange={setShowSettingsDialog}>
                <DialogContent className="sm:max-w-[525px]">
                    <DialogHeader>
                        <DialogTitle>Classification Settings</DialogTitle>
                        <DialogDescription>
                            Configure parameters for the classification process.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-6 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="settings-batch-size">
                                Batch Size
                            </Label>
                            <Select
                                value={classificationSettings?.batch_size?.toString() || "1"}
                                onValueChange={(value) => {
                                    setClassificationSettings(prev => ({
                                        ...prev,
                                        batch_size: parseInt(value, 10)
                                    }));
                                }}
                                disabled={!user?.is_paid_user}
                            >
                                <SelectTrigger>
                                    <SelectValue placeholder="Select batch size" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="1">1</SelectItem>
                                    <SelectItem value="2">2</SelectItem>
                                    <SelectItem value="4">4</SelectItem>
                                    <SelectItem value="8">8</SelectItem>
                                    <SelectItem value="16">16</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="settings-majority-threshold">
                                Majority Threshold
                            </Label>
                            <Select
                                value={classificationSettings?.majority_threshold?.toString() || "0.5"}
                                onValueChange={(value) => {
                                    setClassificationSettings(prev => ({
                                        ...prev,
                                        majority_threshold: parseFloat(value)
                                    }));
                                }}
                                disabled={!user?.is_paid_user}
                            >
                                <SelectTrigger>
                                    <SelectValue placeholder="Select majority threshold" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="0.1">0.1</SelectItem>
                                    <SelectItem value="0.2">0.2</SelectItem>
                                    <SelectItem value="0.3">0.3</SelectItem>
                                    <SelectItem value="0.4">0.4</SelectItem>
                                    <SelectItem value="0.5">0.5</SelectItem>
                                    <SelectItem value="0.6">0.6</SelectItem>
                                    <SelectItem value="0.7">0.7</SelectItem>
                                    <SelectItem value="0.8">0.8</SelectItem>
                                    <SelectItem value="0.9">0.9</SelectItem>
                                    <SelectItem value="1.0">1.0</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="settings-total-invocations">
                                Total LLM Calls
                            </Label>
                            <Select
                                value={classificationSettings?.total_invocations?.toString() || "4"}
                                onValueChange={(value) => {
                                    setClassificationSettings(prev => ({
                                        ...prev,
                                        total_invocations: parseInt(value, 10)
                                    }));
                                }}
                                disabled={!user?.is_paid_user}
                            >
                                <SelectTrigger>
                                    <SelectValue placeholder="Select total invocations" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="1">1</SelectItem>
                                    <SelectItem value="2">2</SelectItem>
                                    <SelectItem value="4">4</SelectItem>
                                    <SelectItem value="8">8</SelectItem>
                                    <SelectItem value="16">16</SelectItem>
                                    <SelectItem value="32">32</SelectItem>
                                    <SelectItem value="64">64</SelectItem>
                                    <SelectItem value="128">128</SelectItem>
                                    <SelectItem value="256">256</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-2">
                            <div className="flex items-center">
                                <Label>
                                    Models
                                </Label>
                                <p className="text-xs text-muted-foreground ml-2">
                                    {classificationSettings?.models?.length || 0} model(s) selected
                                </p>
                            </div>

                            <div className="space-y-4">

                                <div className="space-y-2">
                                    <div className="flex items-center justify-between">
                                        {user?.is_paid_user && <div className="flex gap-2">
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="sm"
                                                className="h-6 text-xs"
                                                onClick={() => {
                                                    const model_values = AI_MODELS.map(m => m.value);
                                                    setClassificationSettings(prev => ({
                                                        ...prev,
                                                        models: [...new Set([...prev.models, ...model_values])]
                                                    }));
                                                }}
                                            >
                                                Select All
                                            </Button>
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="sm"
                                                className="h-6 text-xs"
                                                onClick={() => {
                                                    const model_values = AI_MODELS.map(m => m.value);
                                                    setClassificationSettings(prev => ({
                                                        ...prev,
                                                        models: prev.models.filter(m => !model_values.includes(m))
                                                    }));
                                                }}
                                            >
                                                Clear All
                                            </Button>
                                        </div>}
                                    </div>
                                    <div className="grid grid-cols-2">
                                        {AI_MODELS.map((model) => (
                                            <div key={model.value} className="flex items-center justify-start space-x-2">
                                                <Checkbox
                                                    id={model.value}
                                                    checked={classificationSettings?.models?.includes(model.value)}
                                                    onCheckedChange={(checked) => {
                                                        if (checked) {
                                                            setClassificationSettings(prev => ({
                                                                ...prev,
                                                                models: [...prev.models, model.value]
                                                            }));
                                                        } else {
                                                            setClassificationSettings(prev => ({
                                                                ...prev,
                                                                models: prev.models.filter(m => m !== model.value)
                                                            }));
                                                        }
                                                    }}
                                                    disabled={!user?.is_paid_user && model.isPaidOnly}
                                                    className="mt-1"
                                                />
                                                <div className="flex-1">
                                                    <Label htmlFor={model.value} className="font-normal cursor-pointer block">
                                                        {model.label}
                                                    </Label>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button
                            onClick={async () => {
                                if (selectedTaxonomyId && classificationSettings && taxonomiesData?.taxonomies) {
                                    try {
                                        // Get current taxonomy to preserve existing values
                                        const currentTaxonomy = taxonomiesData.taxonomies.find(
                                            t => t.id === selectedTaxonomyId
                                        );

                                        // Create classifier_state object, preserving existing values we're not changing
                                        const classifierState: ClassifierState = {
                                            batch_size: classificationSettings.batch_size,
                                            models: classificationSettings.models,
                                            majority_threshold: classificationSettings.majority_threshold,
                                            total_invocations: classificationSettings.total_invocations,
                                            initial_batch_size: currentTaxonomy?.classifier_state?.initial_batch_size || 50,
                                            use_human_in_the_loop: currentTaxonomy?.classifier_state?.use_human_in_the_loop || false,
                                            node_ids_not_to_examine: currentTaxonomy?.classifier_state?.node_ids_not_to_examine || [],
                                            examined_node_ids: currentTaxonomy?.classifier_state?.examined_node_ids || []
                                        };

                                        // Update taxonomy with new classifier_state
                                        await taxonomiesApi.update(selectedTaxonomyId, {
                                            classifier_state: classifierState
                                        });

                                        // Refresh taxonomies data
                                        await queryClient.invalidateQueries({ queryKey: ['taxonomies'] });

                                        setShowSettingsDialog(false);
                                        toast({
                                            title: "Settings saved",
                                            description: "Your classification settings have been saved to the database.",
                                        });
                                    } catch (error) {
                                        toast({
                                            title: "Error saving settings",
                                            description: "Failed to save classification settings. Please try again.",
                                            variant: "destructive"
                                        });
                                    }
                                }
                            }}
                            disabled={!user?.is_paid_user}
                        >
                            {user?.is_paid_user ? "Save Settings" : "Only paid users can customize these settings."}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div >
    );
};

export default Home;
