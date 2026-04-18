export interface SearchResultItem {
  id: string;
  content: string;
  score: number;
  age_fit_score?: number;
  source_book: string;
  chapter_title?: string;
  page_label?: string;
  target_age_min: number;
  target_age_max: number;
  brain_regions: string[];
  topics: string[];
  file_hash: string;
}
