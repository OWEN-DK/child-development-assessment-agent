export interface FinalReport {
  markdown_content: string;
  structured_data: Record<string, any>;
}

export interface StreamingReportData {
  score: number;
  radar_chart: Record<string, any>;
  key_suggestions: string[];
}
