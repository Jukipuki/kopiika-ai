import { Skeleton } from "@/components/ui/skeleton";
import { SkeletonCard } from "@/features/teaching-feed/components/SkeletonCard";

export default function FeedLoading() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <Skeleton className="mb-6 h-8 w-48" />
      <ul className="flex flex-col gap-4">
        {[1, 2, 3].map((i) => (
          <li key={i}>
            <SkeletonCard />
          </li>
        ))}
      </ul>
    </div>
  );
}
