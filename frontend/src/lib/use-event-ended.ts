import { useQuery } from "@tanstack/react-query";
import { getPublicInfo } from "@/lib/api";

export function useEventEnded(): boolean {
  const { data: info } = useQuery({
    queryKey: ["info", "public"],
    queryFn: getPublicInfo,
    staleTime: 60_000,
  });
  return !!info?.competition.end_time && new Date(info.competition.end_time) < new Date();
}
