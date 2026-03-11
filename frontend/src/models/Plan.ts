export type IntensityType = "low" | "medium" | "high";

export interface Activity {
  name: string;
  duration_minutes: number;
  frequency_weekly: number;
  intensity?: IntensityType | null;
  description?: string | null;
}

export interface ProposedPlan {
  plan_name: string;
  activities: Activity[];
  goals: string[];
}
