import React, { useState } from 'react';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
import { Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SelectableListProps<T> {
    items: T[];
    renderItem: (item: T, isSelected: boolean, onToggle: () => void) => React.ReactNode;
    getItemId: (item: T) => string;
    onRemoveSelected: (selectedIds: string[]) => void;
    onUseAsExample?: (selectedIds: string[]) => void;
    onVerify?: (selectedIds: string[]) => void;
    isRemoving?: boolean;
    className?: string;
    showSelectAll?: boolean;
    emptyMessage?: string;
}

export function SelectableList<T>({
    items,
    renderItem,
    getItemId,
    onRemoveSelected,
    onUseAsExample,
    onVerify,
    isRemoving = false,
    className,
    showSelectAll = true,
}: SelectableListProps<T>) {
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

    const toggleSelection = (id: string) => {
        setSelectedIds(prev => {
            const newSet = new Set(prev);
            if (newSet.has(id)) {
                newSet.delete(id);
            } else {
                newSet.add(id);
            }
            return newSet;
        });
    };

    const toggleSelectAll = () => {
        if (selectedIds.size === items.length) {
            setSelectedIds(new Set());
        } else {
            setSelectedIds(new Set(items.map(getItemId)));
        }
    };

    const handleRemove = () => {
        onRemoveSelected(Array.from(selectedIds));
        setSelectedIds(new Set());
    };

    const handleUseAsExample = () => {
        onUseAsExample(Array.from(selectedIds));
        setSelectedIds(new Set());
    };

    const handleVerify = () => {
        onVerify(Array.from(selectedIds));
        setSelectedIds(new Set());
    };

    if (items.length === 0) {
        return;
    }

    return (
        <div className={cn("space-y-2", className)}>
            {/* Selection controls */}
            {(selectedIds.size > 0 || showSelectAll) && (
                <div className="flex items-center justify-between p-2">
                    {showSelectAll && (
                        <div className="flex items-center gap-2 h-8 pl-1">
                            <Checkbox
                                checked={selectedIds.size === items.length && items.length > 0}
                                onCheckedChange={toggleSelectAll}
                                aria-label="Select all"
                            />
                            <span className="text-xs text-muted-foreground">
                                {selectedIds.size === 0
                                    ? "Select all"
                                    : `${selectedIds.size}`}
                            </span>
                        </div>
                    )}

                    {selectedIds.size > 0 && (
                        <div className="flex items-center gap-1">
                            {onRemoveSelected && <Button
                                size="sm"
                                variant="destructive"
                                onClick={handleRemove}
                                disabled={isRemoving}
                                className="h-8"
                            >
                                Remove
                            </Button>}
                            {onUseAsExample && <Button
                                size="sm"
                                variant="outline"
                                onClick={handleUseAsExample}
                                disabled={isRemoving}
                                className="h-8"
                            >
                                Use as example
                            </Button>}
                            {onVerify && <Button
                                size="sm"
                                variant="default"
                                onClick={handleVerify}
                                disabled={isRemoving}
                                className="h-8"
                            >
                                Verify
                            </Button>}
                        </div>
                    )}
                </div>
            )}

            {/* List items */}
            <div className="space-y-2">
                {items.map(item => {
                    const id = getItemId(item);
                    const isSelected = selectedIds.has(id);

                    return (
                        <div key={id} className="relative">
                            {renderItem(item, isSelected, () => toggleSelection(id))}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

// Helper component for individual selectable items
interface SelectableItemProps {
    isSelected: boolean;
    onToggle: () => void;
    children: React.ReactNode;
    className?: string;
    variant?: 'default' | 'card';
    checkboxPosition?: 'inline' | 'embedded';
}

export function SelectableItem({
    isSelected,
    onToggle,
    children,
    className,
    variant = 'default',
    checkboxPosition = 'inline'
}: SelectableItemProps) {
    const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
        // Don't toggle checkbox if clicking on the node details link
        if (!(e.target as HTMLElement).closest('.node-link')) {
            onToggle();
        }
    }

    if (variant === 'card') {
        return (
            <div className="relative group">
                <div
                    className={cn(
                        "flex flex-col gap-2 p-4 rounded-lg border bg-card transition-colors cursor-pointer",
                        isSelected ? "bg-accent/50" : "hover:bg-accent/50",
                        className
                    )}
                    onClick={handleClick}
                >
                    {children}
                </div>
            </div>
        );
    }

    // Default variant
    return (
        <div className={cn(
            "flex items-start gap-3 p-3 rounded-lg transition-colors",
            isSelected ? "bg-accent" : "hover:bg-accent/50",
            className
        )}>
            <Checkbox
                checked={isSelected}
                onCheckedChange={onToggle}
                className="mt-0.5"
            />
            <div className="flex-1 min-w-0">
                {children}
            </div>
        </div>
    );
}

export function SelectableItemHeader({ children, className, isSelected, onToggle }: { children: React.ReactNode; className?: string, isSelected: boolean, onToggle: () => void }) {
    return (
        <div className={cn("flex items-start justify-between", className)}>
            <Checkbox
                checked={isSelected}
                onCheckedChange={onToggle}
                className="pointer-events-none"
            />
            <div className="flex flex-wrap gap-1 justify-end">{children}</div>
        </div>
    );
}

export function SelectableItemContent({ children, className }: { children: React.ReactNode; className?: string }) {
    return (
        <div className={cn("w-full", className)}>
            {children}
        </div>
    );
}

export function SelectableItemFooter({ className, onItemClick, item, message }: { className?: string, onItemClick: (item: any) => void, item: any, message: string }) {
    return (
        <div className={cn("flex justify-end", className)}>
            <Button
                variant="link"
                size="sm"
                className="item-link h-auto p-0 text-xs text-muted-foreground hover:text-primary"
                onClick={(e) => {
                    e.stopPropagation();
                    onItemClick(item);
                }}
            >
                {message} →
            </Button>
        </div>
    );
} 