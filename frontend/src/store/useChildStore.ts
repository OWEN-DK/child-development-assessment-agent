import { create } from 'zustand';
import type { ChildProfile } from '../models/assessment';

interface ChildStore {
  currentProfile: ChildProfile | null;
  setProfile: (profile: ChildProfile) => void;
  clearProfile: () => void;
}

export const useChildStore = create<ChildStore>((set) => ({
  currentProfile: null,
  setProfile: (profile) => set({ currentProfile: profile }),
  clearProfile: () => set({ currentProfile: null }),
}));
