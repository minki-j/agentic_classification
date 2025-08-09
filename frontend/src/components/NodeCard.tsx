import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CheckCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getConfidenceBackgroundStyle, getConfidenceTextColor } from '@/lib/utils';

interface NodeCardProps {
    data: {
        node_id: string;
        label: string;
        description: string;
        itemCount: number;
        isHighlighted?: boolean;
        avgConfidence?: number;
        isLayoutVertical?: boolean;
    };
    selected?: boolean;
}

const NodeCard: React.FC<NodeCardProps> = memo(({ data, selected }) => {
    const confidenceStyle = getConfidenceBackgroundStyle(data.avgConfidence, data.itemCount);

    return (
        <>
            <Handle
                type="target"
                position={data.isLayoutVertical ? Position.Left : Position.Top}
                className="w-2 h-2 bg-gray-400"
            />
            <Card
                className={cn(
                    "px-4 py-3 min-w-[350px] max-w-[350px] cursor-pointer transition-all border",
                    data.isHighlighted && "ring-4 ring-black"
                )}
                style={confidenceStyle}
            >
                <div className="space-y-2">
                    <div className="flex items-start justify-between">
                        <h3 className="font-semibold text-sm leading-tight truncate pr-2">
                            {data.label}
                        </h3>
                        <div className="flex gap-1 shrink-0">
                            {selected && (
                                <CheckCircle className="w-10 h-10 absolute -top-5 -right-3 text-white bg-blue-500 rounded-full" />
                            )}
                        </div>
                    </div>
                    <p className="text-xs text-muted-foreground line-clamp-4">
                        {data.description}
                    </p>
                    <div className="flex items-center justify-between text-xs">
                        <div className="text-muted-foreground">
                            {data.itemCount} item{data.itemCount > 1 ? 's' : ''}
                        </div>
                        {data.avgConfidence !== undefined && data.itemCount > 0 && (
                            <div className={cn(
                                "font-medium",
                                getConfidenceTextColor(data.avgConfidence)
                            )}>
                                {(data.avgConfidence * 100).toFixed(0)}% conf
                            </div>
                        )}
                    </div>
                </div>
            </Card>
            <Handle
                type="source"
                position={data.isLayoutVertical ? Position.Right : Position.Bottom}
                className="w-2 h-2 bg-gray-400"
            />
        </>
    );
});

NodeCard.displayName = 'NodeCard';

export default NodeCard; 