import { UserInput, FinalReport, StreamingReportData } from '../../models';

export type { UserInput, FinalReport, StreamingReportData };

export interface LayeredProgressStatus {
  task_id: string;
  total: number;
  processed: number;
  progress: number;
  status: 'running' | 'completed';
  start_time: string;
  end_time?: string;
}
