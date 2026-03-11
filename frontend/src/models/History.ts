import { IntensityType } from './Plan';

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
