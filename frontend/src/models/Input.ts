import { ChildProfile } from './Child';
import { ProposedPlan } from './Plan';
import { HistoryRecord } from './History';

export interface UserInput {
  child_profile: ChildProfile;
  proposed_plan: ProposedPlan;
  history_context?: HistoryRecord[];
}
