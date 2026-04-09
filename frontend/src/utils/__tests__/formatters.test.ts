import { describe, it, expect } from 'vitest';
import { formatScore } from '../formatters';

describe('formatScore', () => {
  it('should format numbers to 1 decimal place', () => {
    expect(formatScore(85.123)).toBe('85.1');
    expect(formatScore(90)).toBe('90.0');
    expect(formatScore(0)).toBe('0.0');
  });

  it('should handle string inputs', () => {
    expect(formatScore('85.123')).toBe('85.1');
    expect(formatScore('90')).toBe('90.0');
  });

  it('should return 0.0 for invalid inputs', () => {
    expect(formatScore(null)).toBe('0.0');
    expect(formatScore(undefined)).toBe('0.0');
    expect(formatScore('invalid')).toBe('0.0');
  });
});
