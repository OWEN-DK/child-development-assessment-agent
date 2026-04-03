import type { UserInput } from '../../../models/assessment';

interface UseAssessmentFormReturn {
  initialValues: UserInput;
  handleFinish: (values: UserInput, onSubmit: (data: UserInput) => Promise<void>) => Promise<boolean>;
}

export const useAssessmentForm = (): UseAssessmentFormReturn => {
  const initialValues: UserInput = {
    child_profile: {
      name: '',
      age: 6,
      gender: 'male',
      issues: [],
      interests: []
    },
    proposed_plan: {
      plan_name: '感统训练计划 A',
      activities: [
        { name: '跳绳', duration_minutes: 10, frequency_weekly: 3, intensity: 'medium' }
      ],
      goals: ['提升协调性']
    }
  };

  const handleFinish = async (values: UserInput, onSubmit: (data: UserInput) => Promise<void>) => {
    const cleanValues = { ...values };
    if (!cleanValues.child_profile.issues) cleanValues.child_profile.issues = [];
    if (!cleanValues.child_profile.interests) cleanValues.child_profile.interests = [];
    if (!cleanValues.proposed_plan.goals) cleanValues.proposed_plan.goals = [];
    
    await onSubmit(cleanValues);
    return true;
  };

  return {
    initialValues,
    handleFinish
  };
};
