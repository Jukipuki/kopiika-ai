export interface FinancialProfile {
  id: string;
  totalIncome: number;
  totalExpenses: number;
  categoryTotals: Record<string, number>;
  periodStart: string | null;
  periodEnd: string | null;
  updatedAt: string;
}

// snake_case keys match the backend JSONB breakdown structure (opaque dict, not aliased by Pydantic)
export interface HealthScoreBreakdown {
  savings_ratio: number;
  category_diversity: number;
  expense_regularity: number;
  income_coverage: number;
}

export interface HealthScore {
  score: number;
  breakdown: HealthScoreBreakdown;
  calculatedAt: string;
}

export type HealthScoreHistoryItem = HealthScore;
export type HealthScoreHistory = HealthScoreHistoryItem[];

export interface CategoryBreakdownItem {
  category: string;
  amount: number;
  percentage: number;
}

export interface CategoryBreakdown {
  categories: CategoryBreakdownItem[];
  totalExpenses: number;
}

export interface CategoryComparison {
  category: string;
  currentAmount: number;
  previousAmount: number;
  changePercent: number;
  changeAmount: number;
}

export interface MonthlyComparison {
  currentMonth: string;
  previousMonth: string;
  categories: CategoryComparison[];
  totalCurrent: number;
  totalPrevious: number;
  totalChangePercent: number;
}
