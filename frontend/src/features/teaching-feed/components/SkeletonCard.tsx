import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";

export function SkeletonCard() {
  return (
    <Card>
      <CardContent className="p-4">
        <Skeleton className="mb-2 h-5 w-20 rounded-full" />
        <Skeleton className="mb-1 h-4 w-full" />
        <Skeleton className="mb-3 h-8 w-24" />
        <Skeleton className="h-4 w-28" />
      </CardContent>
    </Card>
  );
}
