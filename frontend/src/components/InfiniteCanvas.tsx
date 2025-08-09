import React, { useEffect, useCallback, useMemo, useRef } from 'react';
import ReactFlow, {
    Node,
    Edge,
    useNodesState,
    useEdgesState,
    Controls,
    Background,
    BackgroundVariant,
    NodeTypes,
    MarkerType,
    Connection,
    useReactFlow,
    reconnectEdge,
} from 'reactflow';
import 'reactflow/dist/style.css';
import NodeCard from './NodeCard';
import { ClassNode, Item } from '@/models/types';
import dagre from 'dagre';

interface InfiniteCanvasProps {
    nodes: ClassNode[];
    selectedNodeId: string | null;
    selectedItem: Item | null;
    highlightedNodeIds?: string[];
    showClassificationPanel: boolean;
    isLayoutVertical: boolean;
    parentNodeIdsNeedAnimatedEdges: string[];
    onNodeClick: (nodeId: string) => void;
    onNodeCreate?: (parentNodeId: string, position: { x: number; y: number }) => void;
    onEdgeConnect?: (sourceNodeId: string, targetNodeId: string) => void;
    onEdgeDelete?: (sourceNodeId: string, targetNodeId: string) => void;
}

const nodeTypes: NodeTypes = {
    custom: NodeCard,
};

// Helper function to create a hierarchical layout
const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = 'TB') => {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));
    // ranksep: distance between ranks, nodesep: distance between nodes in the same rank
    dagreGraph.setGraph({ rankdir: direction, ranksep: 80, nodesep: 20 });

    nodes.forEach((node) => {
        dagreGraph.setNode(node.id, { width: 350, height: 120 });
    });

    edges.forEach((edge) => {
        dagreGraph.setEdge(edge.source, edge.target);
    });

    dagre.layout(dagreGraph);

    const layoutedNodes = nodes.map((node) => {
        const nodeWithPosition = dagreGraph.node(node.id);
        return {
            ...node,
            position: {
                x: nodeWithPosition.x - 175, // Center the node (half of 350)
                y: nodeWithPosition.y - 60,  // Center the node (half of 120)
            },
        };
    });

    return { nodes: layoutedNodes, edges };
};

const InfiniteCanvas: React.FC<InfiniteCanvasProps> = ({
    nodes,
    selectedNodeId,
    selectedItem,
    highlightedNodeIds,
    showClassificationPanel,
    isLayoutVertical,
    parentNodeIdsNeedAnimatedEdges,
    onNodeClick,
    onNodeCreate,
    onEdgeConnect,
    onEdgeDelete,
}) => {
    const edgeReconnectSuccessful = useRef(true);
    const { screenToFlowPosition } = useReactFlow();

    // Track connection state
    const connectingParentNodeId = useRef<string | null>(null);
    const isReconnecting = useRef(false);


    const nodeIdsOfSelectedItem = useMemo(() => {
        return nodes.filter((node) => selectedItem?.classified_as.some(
            (nc) => nc.node_id === node.id
        )).map((node) => node.id);
    }, [nodes, selectedItem]);


    // Convert ClassNode array to ReactFlow nodes and edges
    const { flowNodes, flowEdges } = useMemo(() => {
        const flowNodes: Node[] = nodes.map((node) => {
            // Check if this node contains the selected item or is in the highlighted list
            let isHighlighted = false;
            if (showClassificationPanel) {
                isHighlighted = highlightedNodeIds.includes(node.id) || false;
            } else {
                isHighlighted = nodeIdsOfSelectedItem.includes(node.id) || false;
            }

            // Calculate average confidence score
            const verifiedItems = node.items.filter(item => !item.is_verified);
            const avgConfidence = verifiedItems.length > 0
                ? verifiedItems.reduce((sum, item) => sum + item.confidence_score, 0) / verifiedItems.length
                : 0;

            return {
                id: node.id,
                type: 'custom',
                position: { x: 0, y: 0 }, // Will be calculated by layout
                data: {
                    id: node.id,
                    label: node.label,
                    description: node.description,
                    itemCount: node.items.length,
                    isHighlighted,
                    avgConfidence,
                    isLayoutVertical,
                },
                selected: node.id === selectedNodeId,
            };
        });

        const flowEdges: Edge[] = nodes
            .filter((node) => node.parent_node_id)
            .map((node) => {
                // Check if this edge connects two highlighted nodes (both parent and child are highlighted)
                let isConnectedToHighlighted = false;
                if (showClassificationPanel) {
                    isConnectedToHighlighted = highlightedNodeIds.includes(node.id);
                } else {
                    isConnectedToHighlighted = nodeIdsOfSelectedItem.includes(node.id);
                }

                const isNeedAnimatedEdge = parentNodeIdsNeedAnimatedEdges.includes(node.parent_node_id) || false;

                const needHighlighted = isConnectedToHighlighted || isNeedAnimatedEdge;

                return {
                    id: `${node.parent_node_id}-${node.id}`,
                    source: node.parent_node_id,
                    target: node.id,
                    type: 'smoothstep',
                    animated: isNeedAnimatedEdge,
                    selected: needHighlighted,
                    markerEnd: {
                        type: MarkerType.ArrowClosed,
                        width: 10,
                        height: 10,
                        color: needHighlighted ? '#000000' : '#9CA3AF',
                    },
                    style: {
                        strokeWidth: needHighlighted ? 4 : 2,
                        stroke: needHighlighted ? '#000000' : '#9CA3AF',
                    },
                };
            });

        // Apply hierarchical layout
        const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
            flowNodes,
            flowEdges,
            isLayoutVertical ? 'LR' : 'TB'
        );

        return { flowNodes: layoutedNodes, flowEdges: layoutedEdges };
    }, [nodes, selectedNodeId, selectedItem, highlightedNodeIds, showClassificationPanel, isLayoutVertical]);

    const [reactFlowNodes, setNodes, onNodesChange] = useNodesState(flowNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(flowEdges);

    // Update nodes when selection changes
    useEffect(() => {
        setNodes(flowNodes);
    }, [flowNodes, setNodes]);

    useEffect(() => {
        setEdges(flowEdges);
    }, [flowEdges, setEdges]);

    const onNodeClickHandler = useCallback(
        (event: React.MouseEvent, node: Node) => {
            onNodeClick(node.id);
        },
        [onNodeClick]
    );


    // New Connection handlers
    const onConnectStart = useCallback(
        (event: React.MouseEvent | React.TouchEvent, params: { nodeId: string | null; handleId: string | null }) => {
            if (!isReconnecting.current) {
                // Only store the parent node ID if this is a new connection, not a reconnection
                connectingParentNodeId.current = params.nodeId;
            }
        },
        []
    );
    const onConnect = useCallback(
        (params: Connection) => {
            if (params.source && params.target && onEdgeConnect) {
                onEdgeConnect(params.source, params.target);

                // We must reset parent node id 
                // because we don't want to create a new node when onConnectEnd is called
                connectingParentNodeId.current = null;
            }
        },
        [onEdgeConnect]
    );
    const onConnectEnd = useCallback(
        (event: MouseEvent | TouchEvent) => {
            // If connection was dropped on the pane (not on a node) and we have a source node
            // we create a new node at the position of the connection
            if (connectingParentNodeId.current && onNodeCreate) {
                const { clientX, clientY } =
                    'changedTouches' in event ? event.changedTouches[0] : event;

                const position = screenToFlowPosition({
                    x: clientX,
                    y: clientY,
                });
                onNodeCreate(connectingParentNodeId.current, position);
            }
            // Reset the connecting node
            connectingParentNodeId.current = null;
            // Reset reconnecting flag in case it was set
            isReconnecting.current = false;
        },
        [screenToFlowPosition, onNodeCreate]
    );

    // Existing Connection handlers
    const onReconnectStart = useCallback(() => {
        edgeReconnectSuccessful.current = false;
        isReconnecting.current = true;
    }, []);
    const onReconnect = useCallback((oldEdge: Edge, newConnection: Connection) => {
        // This is called only when an edge is reconnected to a node.
        // Meaning it won't be t
        edgeReconnectSuccessful.current = true;
        setEdges((els) => reconnectEdge(oldEdge, newConnection, els));
        // Update parent relationship if reconnected
        if (newConnection.source && newConnection.target && onEdgeConnect) {
            onEdgeConnect(newConnection.source, newConnection.target);
        }
    }, [onEdgeConnect]);
    const onReconnectEnd = useCallback((event: MouseEvent | TouchEvent, edge: Edge | undefined) => {
        if (!edgeReconnectSuccessful.current && edge && onEdgeDelete) {
            // The edge was dropped on the pane, so we delete it
            onEdgeDelete(edge.source, edge.target);
        }
        edgeReconnectSuccessful.current = true;
        isReconnecting.current = false;
    }, [onEdgeDelete]);

    return (
        <div className="w-full h-full">
            <ReactFlow
                nodes={reactFlowNodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClickHandler}
                onConnect={onConnect}
                onConnectStart={onConnectStart}
                onConnectEnd={onConnectEnd}
                onReconnect={onReconnect}
                onReconnectStart={onReconnectStart}
                onReconnectEnd={onReconnectEnd}
                nodeTypes={nodeTypes}
                elevateEdgesOnSelect={true}
                fitView
                fitViewOptions={{ padding: 0.2 }}
                minZoom={0.1}
                maxZoom={2}
            >
                <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
                <Controls />
            </ReactFlow>
        </div>
    );
};

export default InfiniteCanvas; 