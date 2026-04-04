"use client";

import { cn } from "@/lib/utils";

interface EducationLayerProps {
  whyItMatters: string;
  deepDive: string;
  isExpanded: boolean;
  expandLevel: 0 | 1 | 2;
  id?: string;
}

export function EducationLayer({ whyItMatters, deepDive, expandLevel, id }: EducationLayerProps) {
  return (
    <>
      <div
        id={id ? `${id}-why` : undefined}
        role="region"
        aria-hidden={expandLevel < 1}
        className={cn(
          "overflow-hidden transition-all duration-300 ease-in-out",
          expandLevel >= 1 ? "max-h-96 opacity-100" : "max-h-0 opacity-0",
        )}
      >
        <div className="pt-3">
          <h4 className="mb-1 text-sm font-semibold text-muted-foreground">Why this matters</h4>
          <p className="text-sm">{whyItMatters}</p>
        </div>
      </div>

      <div
        id={id ? `${id}-deep` : undefined}
        role="region"
        aria-hidden={expandLevel < 2}
        className={cn(
          "overflow-hidden transition-all duration-300 ease-in-out",
          expandLevel >= 2 ? "max-h-96 opacity-100" : "max-h-0 opacity-0",
        )}
      >
        <div className="pt-3">
          <h4 className="mb-1 text-sm font-semibold text-muted-foreground">Deep dive</h4>
          <p className="text-sm">{deepDive}</p>
        </div>
      </div>
    </>
  );
}
