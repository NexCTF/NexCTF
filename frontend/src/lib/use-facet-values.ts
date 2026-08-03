import { useQuery } from "@tanstack/react-query";
import { getFacetValues } from "@/lib/api";

/** Existing values of a free-text label column, unfiltered, for input suggestions. */
export function useFacetValues(path: string, key: string): string[] {
  const { data } = useQuery({
    queryKey: ["facet", path, key],
    queryFn: () => getFacetValues(path, key),
    staleTime: 30_000,
  });
  return data ?? [];
}

/** Every tag in use, whether on a challenge or on a question. */
export function useTagSuggestions(): string[] {
  const challengeTags = useFacetValues("/admin/challenge", "tags");
  const questionTags = useFacetValues("/admin/question", "tags");
  return [...new Set([...challengeTags, ...questionTags])].sort();
}
