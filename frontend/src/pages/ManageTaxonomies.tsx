import React, { useState, useEffect } from 'react';
import Layout from '@/components/Layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { useToast } from '@/hooks/use-toast';
import { Plus, Edit, Trash2, Loader2 } from 'lucide-react';
import { nodesApi, taxonomiesApi } from '@/lib/api';
import { Taxonomy, TaxonomiesResponse } from '@/models/types';
import { useAuth } from '@/contexts/AuthContext';

interface TaxonomyFormData {
    name: string;
    aspect: string;
    rules: string[];
}

const ManageTaxonomies: React.FC = () => {
    const [taxonomies, setTaxonomies] = useState<Taxonomy[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isCreating, setIsCreating] = useState(false);
    const [isEditing, setIsEditing] = useState(false);
    const [createDialogOpen, setCreateDialogOpen] = useState(false);
    const [editDialogOpen, setEditDialogOpen] = useState(false);
    const [selectedTaxonomy, setSelectedTaxonomy] = useState<Taxonomy | null>(null);
    const [formData, setFormData] = useState<TaxonomyFormData>({ name: '', aspect: '', rules: [] });
    const { toast } = useToast();
    const { user } = useAuth();

    useEffect(() => {
        fetchTaxonomies();
    }, []);

    const fetchTaxonomies = async () => {
        setIsLoading(true);
        try {
            const response = await taxonomiesApi.list();
            const data: TaxonomiesResponse = response.data;
            setTaxonomies(data.taxonomies);
        } catch (error) {
            toast({
                title: 'Error',
                description: 'Failed to fetch taxonomies',
                variant: 'destructive',
            });
        } finally {
            setIsLoading(false);
        }
    };

    const handleCreate = async () => {
        if (!formData.name.trim() || !formData.aspect.trim()) {
            toast({
                title: 'Error',
                description: 'Please fill in all fields',
                variant: 'destructive',
            });
            return;
        }

        setIsCreating(true);
        try {
            await taxonomiesApi.create(formData);
            toast({
                title: 'Success',
                description: 'Taxonomy created successfully',
            });
            setCreateDialogOpen(false);
            setFormData({ name: '', aspect: '', rules: [] });
            fetchTaxonomies();
        } catch (error: any) {
            toast({
                title: 'Error',
                description: error.response?.data?.detail || 'Failed to create taxonomy',
                variant: 'destructive',
            });
        } finally {
            setIsCreating(false);
        }
    };

    const handleUpdate = async () => {
        if (!selectedTaxonomy) return;

        if (!formData.name.trim() || !formData.aspect.trim()) {
            toast({
                title: 'Error',
                description: 'Please fill in all fields',
                variant: 'destructive',
            });
            return;
        }

        setIsEditing(true);
        try {
            await taxonomiesApi.update(selectedTaxonomy.id, formData);
            toast({
                title: 'Success',
                description: 'Taxonomy updated successfully',
            });
            setEditDialogOpen(false);
            fetchTaxonomies();
        } catch (error: any) {
            toast({
                title: 'Error',
                description: error.response?.data?.detail || 'Failed to update taxonomy',
                variant: 'destructive',
            });
        } finally {
            setIsEditing(false);
        }
    };

    const handleDelete = async (taxonomy: Taxonomy) => {
        try {
            await taxonomiesApi.delete(taxonomy.id);

            // Check if the deleted taxonomy is stored in localStorage and remove it
            const savedTaxonomyId = localStorage.getItem('selectedTaxonomyId');
            if (savedTaxonomyId === taxonomy.id) {
                localStorage.removeItem('selectedTaxonomyId');
            }

            toast({
                title: 'Success',
                description: 'Taxonomy deleted successfully',
            });
            fetchTaxonomies();
        } catch (error) {
            toast({
                title: 'Error',
                description: 'Failed to delete taxonomy',
                variant: 'destructive',
            });
        }
    };

    const openEditDialog = (taxonomy: Taxonomy) => {
        setSelectedTaxonomy(taxonomy);
        setFormData({ name: taxonomy.name, aspect: taxonomy.aspect, rules: taxonomy.rules || [] });
        setEditDialogOpen(true);
    };

    const formatDate = (dateString: string) => {
        return new Date(dateString).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
        });
    };

    return (
        <Layout>
            <div className="space-y-6">
                <div className="flex justify-end items-center">
                    <TooltipProvider>
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <div>
                                    <Dialog open={createDialogOpen} onOpenChange={(open) => {
                                        if (user?.is_paid_user) {
                                            setCreateDialogOpen(open);
                                        }
                                    }}>
                                        <DialogTrigger asChild>
                                            <Button variant="outline" disabled={!user?.is_paid_user}>
                                                <Plus className="mr-2 h-4 w-4" />
                                                Create Taxonomy
                                            </Button>
                                        </DialogTrigger>
                                        {user?.is_paid_user && (
                                            <DialogContent>
                                                <DialogHeader>
                                                    <DialogTitle>Create New Taxonomy</DialogTitle>
                                                    <DialogDescription>
                                                        Create a new taxonomy for classifying items.
                                                    </DialogDescription>
                                                </DialogHeader>
                                                <div className="space-y-4 py-4">
                                                    <div className="space-y-2">
                                                        <Label htmlFor="name">Name</Label>
                                                        <Input
                                                            id="name"
                                                            placeholder="e.g., Customer Feedback"
                                                            value={formData.name}
                                                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                                        />
                                                    </div>
                                                    <div className="space-y-2">
                                                        <Label htmlFor="aspect">Aspect</Label>
                                                        <Textarea
                                                            id="aspect"
                                                            placeholder="e.g., Categorize feedback by sentiment and topic"
                                                            value={formData.aspect}
                                                            onChange={(e) => setFormData({ ...formData, aspect: e.target.value })}
                                                            rows={3}
                                                        />
                                                    </div>
                                                    <div className="space-y-2">
                                                        <Label htmlFor="rules">Rules (one per line)</Label>
                                                        <Textarea
                                                            id="rules"
                                                            placeholder="e.g.,
Include only English text\nIgnore numerical-only entries"
                                                            value={(formData.rules || []).join('\n')}
                                                            onChange={(e) =>
                                                                setFormData({
                                                                    ...formData,
                                                                    rules: e.target.value
                                                                        .split('\n')
                                                                        .map((r) => r.trim())
                                                                        .filter((r) => r.length > 0),
                                                                })
                                                            }
                                                            rows={6}
                                                        />
                                                    </div>
                                                </div>
                                                <DialogFooter>
                                                    <Button
                                                        variant="outline"
                                                        onClick={() => {
                                                            setCreateDialogOpen(false);
                                                            setFormData({ name: '', aspect: '', rules: [] });
                                                        }}
                                                    >
                                                        Cancel
                                                    </Button>
                                                    <Button onClick={handleCreate} disabled={isCreating}>
                                                        {isCreating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                                        Create
                                                    </Button>
                                                </DialogFooter>
                                            </DialogContent>
                                        )}
                                    </Dialog>
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

                {isLoading ? (
                    <div className="flex items-center justify-center py-12">
                        <Loader2 className="h-8 w-8 animate-spin" />
                    </div>
                ) : taxonomies.length === 0 ? (
                    <Card>
                        <CardContent className="flex flex-col items-center justify-center py-12">
                            <p className="text-muted-foreground">Please create your first taxonomy</p>
                        </CardContent>
                    </Card>
                ) : (
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                        {taxonomies.map((taxonomy) => (
                            <Card key={taxonomy.id}>
                                <CardHeader>
                                    <div className="flex justify-between items-start">
                                        <div className="space-y-1">
                                            <CardTitle>{taxonomy.name}</CardTitle>
                                            <CardDescription className="text-xs">
                                                Created {formatDate(taxonomy.created_at)}
                                            </CardDescription>
                                        </div>
                                        <div className="flex gap-1">
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                onClick={() => openEditDialog(taxonomy)}
                                            >
                                                <Edit className="h-4 w-4" />
                                            </Button>
                                            <AlertDialog>
                                                <AlertDialogTrigger asChild>
                                                    <Button variant="ghost" size="icon">
                                                        <Trash2 className="h-4 w-4" />
                                                    </Button>
                                                </AlertDialogTrigger>
                                                <AlertDialogContent>
                                                    <AlertDialogHeader>
                                                        <AlertDialogTitle>Delete Taxonomy</AlertDialogTitle>
                                                        <AlertDialogDescription>
                                                            Are you sure you want to delete "{taxonomy.name}"? This will also delete all associated nodes and cannot be undone.
                                                        </AlertDialogDescription>
                                                    </AlertDialogHeader>
                                                    <AlertDialogFooter>
                                                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                                                        <AlertDialogAction
                                                            onClick={() => handleDelete(taxonomy)}
                                                            className="bg-red-600 hover:bg-red-700"
                                                        >
                                                            Delete
                                                        </AlertDialogAction>
                                                    </AlertDialogFooter>
                                                </AlertDialogContent>
                                            </AlertDialog>
                                        </div>
                                    </div>
                                </CardHeader>
                                <CardContent>
                                    <p className="text-sm text-muted-foreground">{taxonomy.aspect}</p>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                )}

                {/* Edit Dialog */}
                <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>Edit Taxonomy</DialogTitle>
                            <DialogDescription>
                                Update the taxonomy information.
                            </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                            <div className="space-y-2">
                                <Label htmlFor="edit-name">Name</Label>
                                <Input
                                    id="edit-name"
                                    value={formData.name}
                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="edit-aspect">Aspect</Label>
                                <Textarea
                                    id="edit-aspect"
                                    value={formData.aspect}
                                    onChange={(e) => setFormData({ ...formData, aspect: e.target.value })}
                                    rows={10}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="edit-rules">Rules (one per line)</Label>
                                <Textarea
                                    id="edit-rules"
                                    value={(formData.rules || []).join('\n')}
                                    onChange={(e) =>
                                        setFormData({
                                            ...formData,
                                            rules: e.target.value
                                                .split('\n')
                                                .map((r) => r.trim())
                                                .filter((r) => r.length > 0),
                                        })
                                    }
                                    rows={8}
                                />
                            </div>

                        </div>
                        <DialogFooter className="flex items-center">
                            <div className="mr-auto">
                                <AlertDialog>
                                    <AlertDialogTrigger asChild>
                                        <Button variant="destructive">
                                            Delete All Nodes
                                        </Button>
                                    </AlertDialogTrigger>
                                    <AlertDialogContent>
                                        <AlertDialogHeader>
                                            <AlertDialogTitle>
                                                Delete All Nodes
                                            </AlertDialogTitle>
                                            <AlertDialogDescription>
                                                Are you sure you want to delete all nodes in this taxonomy? This action cannot be undone.
                                            </AlertDialogDescription>
                                        </AlertDialogHeader>
                                        <AlertDialogFooter>
                                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                                            <AlertDialogAction
                                                className="bg-red-600 hover:bg-red-700"
                                                onClick={() => {
                                                    nodesApi.deleteAllNodes(selectedTaxonomy?.id);
                                                }}
                                            >
                                                Delete All Nodes
                                            </AlertDialogAction>
                                        </AlertDialogFooter>
                                    </AlertDialogContent>
                                </AlertDialog>
                            </div>
                            <div className="flex gap-2">
                                <Button
                                    variant="outline"
                                    onClick={() => {
                                        setEditDialogOpen(false);
                                        setSelectedTaxonomy(null);
                                    }}
                                >
                                    Cancel
                                </Button>
                                <Button onClick={handleUpdate} disabled={isEditing}>
                                    {isEditing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                    Update
                                </Button></div>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>
        </Layout>
    );
};

export default ManageTaxonomies; 