import React from 'react';

const escapeRegExp = (string: string): string => {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
};

export const highlightKeywords = (
  text: string,
  keywords: string,
  highlightClassName: string = 'highlight'
): React.ReactNode => {
  if (!keywords.trim()) return text;
  
  const keywordList = keywords.split(/\s+/).filter(k => k);
  if (keywordList.length === 0) return text;

  const regex = new RegExp(
    `(${keywordList.map(escapeRegExp).join('|')})`,
    'gi'
  );
  
  return text.split(regex).map((part, index) => {
    if (keywordList.some(k => k.toLowerCase() === part.toLowerCase())) {
      return React.createElement('mark', { key: index, className: highlightClassName }, part);
    }
    return part;
  });
};

export const highlightKeywordsToArray = (
  text: string,
  keywords: string
): Array<{ text: string; isHighlight: boolean }> => {
  if (!keywords.trim()) return [{ text, isHighlight: false }];
  
  const keywordList = keywords.split(/\s+/).filter(k => k);
  if (keywordList.length === 0) return [{ text, isHighlight: false }];

  const regex = new RegExp(
    `(${keywordList.map(escapeRegExp).join('|')})`,
    'gi'
  );
  
  return text.split(regex).map(part => ({
    text: part,
    isHighlight: keywordList.some(k => k.toLowerCase() === part.toLowerCase()),
  }));
};
