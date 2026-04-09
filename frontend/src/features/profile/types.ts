export interface FinancialProfile {
  id: string;
  totalIncome: number;
  totalExpenses: number;
  categoryTotals: Record<string, number>;
  periodStart: string | null;
  periodEnd: string | null;
  updatedAt: string;
}
