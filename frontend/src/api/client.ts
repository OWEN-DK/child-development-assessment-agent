import axios from 'axios';
import { UserInput, FinalReport } from '../models';

const client = axios.create({
  baseURL: '/', // Vite proxy will handle this
  headers: {
    'Content-Type': 'application/json',
  },
});

export const assessDevelopment = async (data: UserInput): Promise<FinalReport> => {
  const response = await client.post<FinalReport>('/assess', data);
  return response.data;
};
