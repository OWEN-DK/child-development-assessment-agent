
export interface LayeredProgressStatus {
  task_id: string;
  total: number;
  processed: number;
  progress: number;
  status: 'running' | 'completed';
  start_time: string;
  end_time?: string;
}
export type GenderType = "male" | "female" | "other";

export interface ChildProfile {
  name: string;
  age: number;
  gender: GenderType;
  issues: string[];
  interests: string[];
}
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


export interface HistoryActivity {
  name: string;
  duration_minutes: number;
  intensity?: IntensityType | null;
  feedback?: string | null;
}

export interface HistoryRecord {
  date: string;
  activities: HistoryActivity[];
  notes?: string | null;
}
export interface FinalReport {
  markdown_content: string;
  structured_data: Record<string, any>;
}

export interface StreamingReportData {
  score: number;
  radar_chart: Record<string, any>;
  key_suggestions: string[];
}


export interface UserInput {
  child_profile: ChildProfile;
  proposed_plan: ProposedPlan;
  history_context?: HistoryRecord[];
}
