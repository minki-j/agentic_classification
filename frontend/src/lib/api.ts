import axios from "axios";
import TokenManager from "./tokenManager";
import { toast } from "../hooks/use-toast";
import type {
  InitialNodesResponse,
  NodesResponse,
  NodeResponse,
  TaxonomyInResponse,
  TaxonomiesResponse,
  ClassificationRequest,
  ClassificationResponse,
  ExaminationRequest,
  ExaminationResponse,
  ClassificationStatusResponse,
  RemoveClassificationRequest,
  RemoveClassificationResponse,
  AddClassificationRequest,
  AddClassificationResponse,
  ClassifierState,
  ClassifierStateUpdate,
  ItemsResponse,
  ItemResponse,
  ItemUnderNode,
  VerifyClassificationRequest,
  UpdateFewShotExamplesRequest,
  OptimizePromptWithDspyRequest,
  RemoveClassificationItemsOnlyRequest,
} from "../models/types";

const API_BASE_URL = import.meta.env.VITE_API_URL;
if (!API_BASE_URL) {
  throw new Error("VITE_API_URL is not set");
}

export const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    "Content-Type": "application/json",
  },
});

// Proactive token refresh
let refreshTimeout: NodeJS.Timeout | null = null;

const scheduleTokenRefresh = () => {
  // Clear any existing timeout
  if (refreshTimeout) {
    clearTimeout(refreshTimeout);
  }

  const accessToken = TokenManager.getAccessToken();
  if (!accessToken) return;

  const expirationDate = TokenManager.getTokenExpiration(accessToken);
  if (!expirationDate) return;

  // Schedule refresh 5 minutes before expiration
  const refreshTime = expirationDate.getTime() - Date.now() - 5 * 60 * 1000;

  if (refreshTime > 0) {
    refreshTimeout = setTimeout(async () => {
      try {
        await refreshAccessToken();
        scheduleTokenRefresh(); // Schedule next refresh
      } catch (error) {
        console.error("Proactive token refresh failed:", error);
      }
    }, refreshTime);
  }
};

// Refresh access token function
const refreshAccessToken = async () => {
  const refreshToken = TokenManager.getRefreshToken();
  if (!refreshToken) throw new Error("No refresh token available");

  const response = await axios.post(`${API_BASE_URL}/api/v1/auth/refresh`, {
    refresh_token: refreshToken,
  });

  const { access_token, refresh_token: newRefreshToken } = response.data;
  const rememberMe = TokenManager.isRememberMeEnabled();
  TokenManager.setTokens(access_token, newRefreshToken, rememberMe);

  return { access_token, refresh_token: newRefreshToken };
};

// Add request interceptor to include auth token
api.interceptors.request.use(
  (config) => {
    const token = TokenManager.getAccessToken();
    if (token) {
      // Check if token is expiring soon
      if (TokenManager.isTokenExpiringSoon(token)) {
        // Try to refresh before making the request
        return refreshAccessToken()
          .then(({ access_token }) => {
            config.headers.Authorization = `Bearer ${access_token}`;
            scheduleTokenRefresh();
            return config;
          })
          .catch(() => {
            // If refresh fails, continue with potentially expired token
            config.headers.Authorization = `Bearer ${token}`;
            return config;
          });
      }
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add response interceptor to handle token refresh and centralized error handling
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    console.log("Error from api interceptor:", error);
    const originalRequest = error.config;

    // Handle 401 errors with token refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const { access_token } = await refreshAccessToken();
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        scheduleTokenRefresh();
        return api(originalRequest);
      } catch (refreshError) {
        // Refresh failed, redirect to login
        TokenManager.clearTokens();
        if (refreshTimeout) {
          clearTimeout(refreshTimeout);
        }
        window.location.href = "/login";
        return Promise.reject(refreshError);
      }
    }

    // Centralized error handling with toast notifications
    // Skip toast for certain URLs or if the request has a custom flag
    const skipToast =
      originalRequest._skipToast || originalRequest.url?.includes("/auth/");

    if (!skipToast && error.response) {
      const status = error.response.status;
      const data = error.response.data;

      // Extract error message from response
      let errorMessage = "An unexpected error occurred";

      if (data?.detail) {
        errorMessage =
          typeof data.detail === "string"
            ? data.detail
            : data.detail.message || errorMessage;
      } else if (data?.message) {
        errorMessage = data.message;
      } else if (data?.error) {
        errorMessage = data.error;
      }

      // Handle different status codes
      switch (status) {
        case 400:
          toast({
            title: "Bad Request",
            description: errorMessage,
            variant: "destructive",
          });
          break;
        case 403:
          toast({
            title: "Access Denied",
            description: errorMessage,
            variant: "destructive",
          });
          break;
        case 404:
          toast({
            title: "Not Found",
            description: errorMessage,
            variant: "destructive",
          });
          break;
        case 422:
          toast({
            title: "Validation Error",
            description: errorMessage,
            variant: "destructive",
          });
          break;
        case 500:
          toast({
            title: "Server Error",
            description: errorMessage,
            variant: "destructive",
          });
          break;
        default:
          if (status >= 400) {
            toast({
              title: "Error",
              description: errorMessage,
              variant: "destructive",
            });
          }
      }
    } else if (!skipToast && error.request) {
      // Network error
      toast({
        title: "Network Error",
        description:
          "Unable to connect to the server. Please check your connection.",
        variant: "destructive",
      });
    }

    return Promise.reject(error);
  }
);

// Schedule initial token refresh
scheduleTokenRefresh();

// Taxonomies API
export const taxonomiesApi = {
  list: (skip = 0, limit = 100): Promise<{ data: TaxonomiesResponse }> =>
    api.get(`/taxonomies?skip=${skip}&limit=${limit}`),

  get: (id: string): Promise<{ data: TaxonomyInResponse }> =>
    api.get(`/taxonomies/${id}`),

  create: (data: {
    name: string;
    aspect: string;
    rules?: string[];
  }): Promise<{ data: TaxonomyInResponse }> => api.post("/taxonomies", data),

  update: (
    id: string,
    data: {
      name?: string;
      aspect?: string;
      rules?: string[];
      classifier_state?: ClassifierState;
    }
  ): Promise<{ data: TaxonomyInResponse }> =>
    api.patch(`/taxonomies/${id}`, data),

  delete: (id: string): Promise<void> => api.delete(`/taxonomies/${id}`),
};

// Items API
export const itemsApi = {
  upload: (
    items: Array<{ content: string }>
  ): Promise<{ data: ItemsResponse }> => api.post("/items/upload", { items }),

  getOne: (taxonomyId: string, id: string): Promise<{ data: ItemResponse }> =>
    api.get(`/items/${taxonomyId}/${id}`),

  getMany: (
    taxonomyId: string,
    itemIds: string[]
  ): Promise<{ data: ItemsResponse }> =>
    api.get(`/items/many?taxonomy_id=${taxonomyId}&item_ids=${itemIds}`),

  list: (
    taxonomyId: string,
    skip = 0,
    limit = 100
  ): Promise<{ data: ItemsResponse }> =>
    api.get(
      `/items/list?taxonomy_id=${taxonomyId}&skip=${skip}&limit=${limit}`
    ),

  exportAll: (): Promise<{ data: string }> => api.get("/items/export-all"),

  getCount: (): Promise<{ data: number }> => api.get("/items/count"),

  getBatch: (
    taxonomyId: string,
    batchSize: number
  ): Promise<{ data: ItemsResponse }> =>
    api.get(`/items/batch/${taxonomyId}/${batchSize}`),

  delete: (id: string): Promise<void> => api.delete(`/items/${id}`),

  deleteAll: (): Promise<void> => api.delete("/items"),

  getIdsByListOfContent: (data: {
    content_list: string[];
  }): Promise<{ data: string[] }> =>
    api.post("/items/get-ids-by-list-of-content", data),
};

// Nodes API
export const nodesApi = {
  getNodes: async (taxonomyId: string): Promise<NodesResponse> => {
    const response = await api.get(`/nodes/${taxonomyId}`);
    return response.data;
  },

  getNode: async (
    taxonomyId: string,
    nodeId: string
  ): Promise<NodeResponse> => {
    const response = await api.get(`/nodes/${taxonomyId}/${nodeId}`);
    return response.data;
  },

  createInitialNodes: async (
    taxonomyId: string,
    numOfItems: number,
    llmName: string
  ): Promise<InitialNodesResponse> => {
    const payload: any = {
      taxonomy_id: taxonomyId,
      num_of_items_to_use: numOfItems,
      llm_name: llmName,
    };
    const response = await api.post("/nodes/initial", payload);
    return response.data;
  },

  createNode: async (
    taxonomyId: string,
    data: {
      parent_node_id: string;
      label: string;
      description: string;
      items?: Array<ItemUnderNode>;
    }
  ): Promise<NodeResponse> => {
    const response = await api.post(`/nodes/${taxonomyId}`, data);
    return response.data;
  },

  updateNode: async (
    taxonomyId: string,
    nodeId: string,
    data: {
      label?: string;
      description?: string;
      parent_node_id?: string;
      items?: Array<ItemUnderNode>;
    }
  ): Promise<void> => {
    await api.patch(`/nodes/${taxonomyId}/${nodeId}`, data);
  },

  deleteNode: async (taxonomyId: string, nodeId: string): Promise<void> => {
    await api.delete(`/nodes/${taxonomyId}/${nodeId}`);
  },

  deleteAllNodes: async (taxonomyId: string): Promise<void> => {
    await api.delete(`/nodes/${taxonomyId}`);
    toast({
      title: "Nodes deleted",
      description: "All nodes in this taxonomy have been deleted.",
    });
  },
};

// Classification API
export const classificationApi = {
  initTrialSetup: (): Promise<void> =>
    api.post("/classification/init-trial-setup"),

  classify: (
    data: ClassificationRequest
  ): Promise<{ data: ClassificationResponse }> =>
    api.post("/classification/classify", data),

  examine: (data: ExaminationRequest): Promise<{ data: ExaminationResponse }> =>
    api.post("/classification/examine", data),

  removeClassification: (
    data: RemoveClassificationRequest
  ): Promise<{ data: RemoveClassificationResponse }> =>
    api.post("/classification/remove", data),

  removeClassificationItemsOnly: (
    data: RemoveClassificationItemsOnlyRequest
  ): Promise<{ data: RemoveClassificationResponse }> =>
    api.post("/classification/remove-items-only", data),

  addClassification: (
    data: AddClassificationRequest
  ): Promise<{ data: AddClassificationResponse }> =>
    api.post("/classification/add", data),

  verifyClassification: (data: VerifyClassificationRequest): Promise<void> =>
    api.post("/classification/verify", data),

  updateFewShotExamples: (data: UpdateFewShotExamplesRequest): Promise<void> =>
    api.post("/classification/update-few-shot-examples", data),

  getStatus: (
    sessionId: string
  ): Promise<{ data: ClassificationStatusResponse }> =>
    api.get(`/classification/status/${sessionId}`),

  updateConfig: (
    taxonomyId: string,
    config: ClassifierStateUpdate
  ): Promise<{ data: ClassifierState }> =>
    api.put(`/classification/config/${taxonomyId}`, config),

  getConfig: (taxonomyId: string): Promise<{ data: ClassifierState }> =>
    api.get(`/classification/config/${taxonomyId}`),

  optimizePromptWithDspy: (
    data: OptimizePromptWithDspyRequest
  ): Promise<void> => api.post("/classification/dspy/optimize", data),
};

// WebSocket connection
export class WSConnection {
  private errorListener: (data: any) => void = (data) => {
    console.error("WebSocket error:", data);
    toast({
      title: "WebSocket Error",
      description: "An error occurred while connecting to the server.",
      variant: "destructive",
    });
  };

  private ws: WebSocket | null = null;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private listeners: Map<string, Set<(data: any) => void>> = new Map([
    ["error", new Set([this.errorListener])],
  ]);
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 1000; // Start with 1 second
  private maxReconnectDelay = 30000; // Max 30 seconds
  private isConnecting = false; // Prevent multiple simultaneous connection attempts

  connect() {
    // Prevent multiple connection attempts
    if (
      this.isConnecting ||
      (this.ws && this.ws.readyState === WebSocket.CONNECTING)
    ) {
      console.log("WebSocket connection already in progress");
      return;
    }

    // Don't reconnect if already connected
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.log("WebSocket already connected");
      return;
    }

    const token = TokenManager.getAccessToken();
    if (!token) {
      console.error("No access token for WebSocket connection");
      return;
    }

    // Check if token is expiring soon
    if (TokenManager.isTokenExpiringSoon(token)) {
      // Try to refresh first
      refreshAccessToken()
        .then(() => this.connect())
        .catch(() => console.error("Failed to refresh token for WebSocket"));
      return;
    }

    this.isConnecting = true;

    const wsUrl = `${API_BASE_URL.replace(
      /^http/,
      "ws"
    )}/api/v1/ws/connect?token=${token}`;

    // Close existing connection if any
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.info("WebSocket connected");
      this.isConnecting = false;
      this.reconnectAttempts = 0;
      this.reconnectDelay = 1000;
      if (this.reconnectTimeout) {
        clearTimeout(this.reconnectTimeout);
        this.reconnectTimeout = null;
      }
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // Handle ping messages
        if (data.type === "ping") {
          this.send({ type: "pong", timestamp: data.timestamp });
          return;
        }

        this.emit(data.type, data.data); // We send the data.data, not just data. No need to parse further.
      } catch (error) {
        console.error("Failed to parse WebSocket message:", error);
      }
    };

    this.ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      this.isConnecting = false;
    };

    this.ws.onclose = (event) => {
      console.log("WebSocket disconnected", event.code, event.reason);
      this.isConnecting = false;
      this.ws = null;

      // Don't reconnect if the connection was closed due to auth issues
      if (event.code === 1008) {
        // Policy Violation - typically auth failure
        console.error("WebSocket closed due to authentication error");
        return;
      }

      // Don't reconnect if connection was closed intentionally (normal closure)
      if (event.code === 1000) {
        console.log("WebSocket closed normally, not reconnecting");
        return;
      }

      // Attempt to reconnect with exponential backoff
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectTimeout = setTimeout(() => {
          console.log(
            `Attempting WebSocket reconnection (${this.reconnectAttempts + 1}/${
              this.maxReconnectAttempts
            })`
          );
          this.reconnectAttempts++;
          this.reconnectDelay = Math.min(
            this.reconnectDelay * 2,
            this.maxReconnectDelay
          );
          this.connect();
        }, this.reconnectDelay);
      } else {
        console.error("Max WebSocket reconnection attempts reached");
      }
    };
  }

  disconnect() {
    this.isConnecting = false;
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.ws) {
      // Use code 1000 for normal closure to prevent reconnection
      this.ws.close(1000, "Client disconnecting");
      this.ws = null;
    }
    this.reconnectAttempts = 0;
    this.reconnectDelay = 1000;
  }

  send(data: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(data));
      } catch (error) {
        console.error("Failed to send WebSocket message:", error);
      }
    } else {
      console.error("WebSocket is not connected");
    }
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  getConnectionState(): string {
    if (!this.ws) return "DISCONNECTED";
    switch (this.ws.readyState) {
      case WebSocket.CONNECTING:
        return "CONNECTING";
      case WebSocket.OPEN:
        return "OPEN";
      case WebSocket.CLOSING:
        return "CLOSING";
      case WebSocket.CLOSED:
        return "CLOSED";
      default:
        return "UNKNOWN";
    }
  }

  on(event: string, callback: (data: any) => void) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);
  }

  off(event: string, callback: (data: any) => void) {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.delete(callback);
      // Clean up empty callback sets
      if (callbacks.size === 0) {
        this.listeners.delete(event);
      }
    }
  }

  private emit(event: string, data: any) {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.forEach((callback) => {
        try {
          callback(data);
        } catch (error) {
          console.error(
            `Error in WebSocket callback for event '${event}':`,
            error
          );
        }
      });
    } else {
      console.warn("No callback for event: ", event, "data: ", data);
    }
  }
}

export const wsConnection = new WSConnection();
