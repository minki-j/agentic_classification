import { ClassNode, Item } from "@/models/types";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Utility functions for styling confidence scores
 */

/**
 * Get text color class based on confidence score
 * @param confidence - Confidence score between 0 and 1
 * @returns Tailwind CSS color class
 */
export const getConfidenceTextColor = (confidence: number): string => {
  if (confidence < 0.4) {
    return "text-white";
  } else if (confidence < 0.8) {
    return "text-yellow-600";
  } else {
    return "text-green-600";
  }
};

/**
 * Get background and border color styles based on confidence score
 * Used for node card background styling
 * @param confidence - Confidence score between 0 and 1 (or undefined)
 * @param itemCount - Number of items in the node
 * @returns Object with backgroundColor and borderColor styles
 */
export const getConfidenceBackgroundStyle = (
  confidence: number | undefined,
  itemCount: number
): { backgroundColor: string; borderColor: string } => {
  // 100% confidence or no items = gray
  // Lower confidence = more red
  if (itemCount === 0 || confidence === undefined || confidence === 0) {
    return {
      backgroundColor: "rgb(243, 244, 246)", // gray-100
      borderColor: "rgb(209, 213, 219)", // gray-300
    };
  }

  // Convert confidence (0-1) to intensity (0-1)
  // Higher confidence = lower intensity (less red)
  const intensity = 1 - confidence;

  // Interpolate from gray to red
  // rgb(255, 255, 255) -> rgb(255, 255, 125) -> rgb(249, 0, 0)
  let red = 255;
  let green = 255;
  let blue = 255;
  if (intensity < 0.5) {
    // Turn to yellow
    red = Math.round(255 + 0 * intensity);
    green = Math.round(255 - 0 * intensity);
    blue = Math.round(250 - 250 * intensity);
  } else {
    // Turn to red
    red = Math.round(255 + 0 * (intensity - 0.5));
    green = Math.round(255 - 510 * (intensity - 0.5));
    blue = Math.round(120 - 240 * (intensity - 0.5));
  }

  // Border should be slightly darker
  const borderRed = Math.max(0, red - 30);
  const borderGreen = Math.max(0, green - 30);
  const borderBlue = Math.max(0, blue - 30);

  return {
    backgroundColor: `rgb(${red}, ${green}, ${blue})`,
    borderColor: `rgb(${borderRed}, ${borderGreen}, ${borderBlue})`,
  };
};

/**
 * Get badge variant based on confidence score
 * @param confidence - Confidence score between 0 and 1
 * @returns Badge variant string
 */
export const getConfidenceBadgeVariant = (
  confidence: number
): "default" | "secondary" | "destructive" | "outline" => {
  if (confidence < 0.5) {
    return "destructive";
  } else if (confidence < 0.8) {
    return "secondary";
  } else {
    return "default";
  }
};

/**
 * Check if an item was updated in the last 10 minutes
 * @param item - The item to check
 * @param nodeId - The node ID to check classification update for
 * @returns boolean indicating if item was recently updated
 */
export const isRecentlyUpdated = (item: Item, nodeId: string): boolean => {
  const tenMinutesAgo = new Date(Date.now() - 10 * 60 * 1000);

  const classification = item.classified_as.find((c) => c.node_id === nodeId);
  if (classification) {
    const classificationUpdatedAt = new Date(classification.updated_at);
    if (classificationUpdatedAt > tenMinutesAgo) {
      return true;
    }
  }

  return false;
};

export const sortItems = (items: Item[], sortBy: string, node: ClassNode) => {
  return [...items].sort((a, b) => {
    // Primary sort based on selected option
    if (sortBy !== "none") {
      let primarySort = 0;
      switch (sortBy) {
        case "confidence-high":
          primarySort =
            (b.classified_as?.find((c) => c.node_id === node.id)
              ?.confidence_score || 0) -
            (a.classified_as?.find((c) => c.node_id === node.id)
              ?.confidence_score || 0);
          break;
        case "confidence-low":
          primarySort =
            (a.classified_as?.find((c) => c.node_id === node.id)
              ?.confidence_score || 0) -
            (b.classified_as?.find((c) => c.node_id === node.id)
              ?.confidence_score || 0);
          break;
      }
      // If primary sort values are different, use primary sort
      if (primarySort !== 0) {
        return primarySort;
      }
    }
    // Secondary sort by updated_at
    const dateA = new Date(
      a.classified_as?.find((c) => c.node_id === node.id)?.updated_at || ""
    ).getTime();
    const dateB = new Date(
      b.classified_as?.find((c) => c.node_id === node.id)?.updated_at || ""
    ).getTime();
    return dateB - dateA; // Descending order (latest first)
  });
};
