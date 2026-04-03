export type GenderType = "male" | "female" | "other";

export interface ChildProfile {
  name: string;
  age: number;
  gender: GenderType;
  issues: string[];
  interests: string[];
}
