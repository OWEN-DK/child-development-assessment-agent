import { UserInput } from '../models';

export const useAssessmentForm = () => {
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

  const handleFinish = async (values: UserInput, onSubmit: (data: UserInput) => void) => {
    // 简单的数据清洗，确保数组存在
    const cleanValues = { ...values };
    if (!cleanValues.child_profile.issues) cleanValues.child_profile.issues = [];
    if (!cleanValues.child_profile.interests) cleanValues.child_profile.interests = [];
    if (!cleanValues.proposed_plan.goals) cleanValues.proposed_plan.goals = [];
    
    onSubmit(cleanValues);
    return true;
  };

  return {
    initialValues,
    handleFinish
  };
};
