import { create } from 'zustand';
import { ChildProfile } from '../models';

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
