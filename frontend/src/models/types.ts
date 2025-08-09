// -------------------------------------- //
// ------------- Taxonomy types ------------- //
// -------------------------------------- //

export interface Taxonomy {
  id: string;
  user_id: string;
  name: string;
  aspect: string;
  rules: string[];
  classifier_state: ClassifierState;
  created_at: string;
  updated_at: string;
}

export interface TaxonomyInResponse {
  taxonomy: Taxonomy;
}

export interface TaxonomiesResponse {
  taxonomies: Taxonomy[];
  count: number;
}

// -------------------------------------- //
// ------------- Node types ------------- //
// -------------------------------------- //

export const ROOT_NODE_ID = "6889fa6ca166114297756152";

export interface ItemUnderNode {
  item_id: string;
  confidence_score: number;
  is_verified: boolean;
  used_as_few_shot_example: boolean;
}

export interface ClassNode {
  id: string;
  taxonomy_id: string;
  user_id: string;
  parent_node_id: string;
  label: string;
  description: string;
  items: ItemUnderNode[];
  created_at: string;
  updated_at: string;
}

export interface NodeResponse extends ClassNode {}

export interface NodesResponse {
  nodes: NodeResponse[];
  count: number;
}

export interface InitialNodesRequest {
  taxonomy_id: string;
  item_ids: string[];
}

export interface InitialNodesResponse {
  message: string;
}

// -------------------------------------- //
// ------------- Item types ------------- //
// -------------------------------------- //

export interface NodeAndConfidence {
  node_id: string;
  confidence_score: number;
}

export interface ClassifiedAs extends NodeAndConfidence {
  is_verified: boolean;
  used_as_few_shot_example: boolean;
  updated_at: string;
}

export interface Item {
  id: string;
  content: string;
  classified_as: ClassifiedAs[];
  created_at: string;
  updated_at: string;
}

export interface ItemResponse {
  item: Item;
}

export interface ItemsResponse {
  items: Item[];
  count: number;
  unclassified_count: number;
}

// -------------------------------------- //
// ----- Classification types ----------- //
// -------------------------------------- //

export interface ClassificationRequest {
  taxonomy_id: string;
  batch_size?: number;
  models?: string[];
  majority_threshold?: number;
  total_invocations?: number;
}

export interface ClassificationResponse {
  message: string;
  session_id?: string;
  items_classified: number;
  items_remaining?: number;
  status: string;
}

export interface ExaminationRequest {
  taxonomy_id: string;
  force_examine_node_ids?: string[];
}

export interface ExaminationResponse {
  message: string;
  session_id?: string;
  nodes_examined: string[];
  status: string;
}

export interface ClassificationStatusResponse {
  session_id: string;
  status: string;
  progress: Record<string, any>;
  current_batch?: number | null;
  total_batches?: number | null;
}

export interface RemoveClassificationRequest {
  taxonomy_id: string;
  item_id: string;
  node_id_to_remove: string;
}

export interface RemoveClassificationResponse {
  message: string;
  status: string;
}

export interface AddClassificationRequest {
  taxonomy_id: string;
  item_id: string;
  node_id: string;
  confidence_score?: number; // Default to 1.0 (100%)
}

export interface AddClassificationResponse {
  message: string;
  status: string;
}

export interface ClassifierState {
  majority_threshold: number;
  batch_size: number;
  total_invocations: number;
  initial_batch_size: number;
  use_human_in_the_loop: boolean;
  node_ids_not_to_examine: string[];
  examined_node_ids: string[];
  models: string[];
}

export interface ClassifierStateUpdate {
  majority_threshold?: number;
  batch_size?: number;
  total_invocations?: number;
  initial_batch_size?: number;
  use_human_in_the_loop?: boolean;
  node_ids_not_to_examine?: string[];
  models?: string[];
}

export interface VerifyClassificationRequest {
  taxonomy_id: string;
  node_id: string;
  item_ids_to_verify?: string[];
  item_ids_to_unverify?: string[];
}

export interface UpdateFewShotExamplesRequest {
  taxonomy_id: string;
  node_id: string;
  item_ids_to_add: string[];
  item_ids_to_remove: string[];
}

export interface OptimizePromptWithDspyRequest {
  taxonomy_id: string;
  node_id: string;
}

export interface RemoveClassificationItemsOnlyRequest {
  taxonomy_id: string;
  item_ids: string[];
  node_id_to_remove: string;
}

// -------------------------------------- //
// ------------ AI MODELS --------------- //
// -------------------------------------- //

export interface AIModelConfig {
  value: string;
  label: string;
  provider: "openai" | "anthropic";
  tier?: "mini" | "standard" | "pro" | "opus";
  isPaidOnly: boolean;
  description?: string;
}

export const AI_MODELS: AIModelConfig[] = [
  // Anthropic Models
  {
    value: "claude-3-5-haiku-latest",
    label: "Claude 3.5 Haiku",
    provider: "anthropic",
    tier: "mini",
    isPaidOnly: true,
    description: "Fast and efficient for simple tasks",
  },
  {
    value: "claude-3-5-sonnet-latest",
    label: "Claude 3.5 Sonnet",
    provider: "anthropic",
    tier: "standard",
    isPaidOnly: true,
    description: "Balanced performance and capability",
  },
  {
    value: "claude-3-7-sonnet-latest",
    label: "Claude 3.7 Sonnet",
    provider: "anthropic",
    tier: "standard",
    isPaidOnly: true,
    description: "Latest Sonnet version with improvements",
  },
  {
    value: "claude-sonnet-4-0",
    label: "Claude Sonnet 4.0",
    provider: "anthropic",
    tier: "standard",
    isPaidOnly: true,
    description: "Next generation Sonnet model",
  },
  {
    value: "claude-opus-4-0",
    label: "Claude Opus 4.0",
    provider: "anthropic",
    tier: "opus",
    isPaidOnly: true,
    description: "Most capable for complex reasoning",
  },
  {
    value: "claude-opus-4-1",
    label: "Claude Opus 4.1",
    provider: "anthropic",
    tier: "opus",
    isPaidOnly: true,
    description: "Latest Opus with enhanced capabilities",
  },

  // OpenAI Models
  {
    value: "gpt-4o-mini",
    label: "GPT-4o Mini",
    provider: "openai",
    tier: "mini",
    isPaidOnly: true,
    description: "Cost-effective for simple tasks",
  },
  {
    value: "gpt-4o",
    label: "GPT-4o",
    provider: "openai",
    tier: "standard",
    isPaidOnly: true,
    description: "Optimized GPT-4 for most use cases",
  },
  {
    value: "gpt-4.1",
    label: "GPT-4.1",
    provider: "openai",
    tier: "standard",
    isPaidOnly: true,
    description: "Enhanced GPT-4 with improvements",
  },
  {
    value: "gpt-4.1-mini",
    label: "GPT-4.1 Mini",
    provider: "openai",
    tier: "mini",
    isPaidOnly: true,
    description: "Lightweight GPT-4.1 variant",
  },
  {
    value: "gpt-4.1-nano",
    label: "GPT-4.1 Nano",
    provider: "openai",
    tier: "mini",
    isPaidOnly: true,
    description: "Ultra-light for basic tasks",
  },
  {
    value: "o1-mini",
    label: "O1 Mini",
    provider: "openai",
    tier: "mini",
    isPaidOnly: true,
    description: "Reasoning model - lightweight",
  },
  {
    value: "o1",
    label: "O1",
    provider: "openai",
    tier: "standard",
    isPaidOnly: true,
    description: "Advanced reasoning capabilities",
  },
  {
    value: "o1-pro",
    label: "O1 Pro",
    provider: "openai",
    tier: "pro",
    isPaidOnly: true,
    description: "Professional reasoning model",
  },
  {
    value: "o3-mini",
    label: "O3 Mini",
    provider: "openai",
    tier: "mini",
    isPaidOnly: true,
    description: "Next-gen reasoning - lightweight",
  },
  {
    value: "o3",
    label: "O3",
    provider: "openai",
    tier: "standard",
    isPaidOnly: true,
    description: "Next-gen advanced reasoning",
  },
  {
    value: "o3-pro",
    label: "O3 Pro",
    provider: "openai",
    tier: "pro",
    isPaidOnly: true,
    description: "Next-gen professional reasoning",
  },
  {
    value: "o4-mini",
    label: "O4 Mini",
    provider: "openai",
    tier: "mini",
    isPaidOnly: true,
    description: "Future reasoning model - lightweight",
  },
  {
    value: "gpt-5-2025-08-07",
    label: "GPT-5",
    provider: "openai",
    tier: "pro",
    isPaidOnly: true,
    description: "",
  },
];

export const getModelsByProvider = (
  provider: "openai" | "anthropic"
): AIModelConfig[] => {
  return AI_MODELS.filter((model) => model.provider === provider);
};

export const getModelsByTier = (
  tier: "mini" | "standard" | "pro" | "opus"
): AIModelConfig[] => {
  return AI_MODELS.filter((model) => model.tier === tier);
};

export const getTierColor = (tier?: string): string => {
  switch (tier) {
    case "mini":
      return "text-blue-600 border-blue-600";
    case "standard":
      return "text-green-600 border-green-600";
    case "pro":
      return "text-purple-600 border-purple-600";
    case "opus":
      return "text-amber-600 border-amber-600";
    default:
      return "text-gray-600 border-gray-600";
  }
};
