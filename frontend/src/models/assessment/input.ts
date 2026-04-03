import { ChildProfile } from './child';
import { ProposedPlan } from './plan';
import { HistoryRecord } from './history';

export interface UserInput {
  child_profile: ChildProfile;
  proposed_plan: ProposedPlan;
  history_context?: HistoryRecord[];
}
