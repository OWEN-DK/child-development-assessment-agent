import dayjs from 'dayjs';

export const formatDateTime = (date: string | Date): string => {
  return dayjs(date).format('YYYY-MM-DD HH:mm:ss');
};

export const formatDate = (date: string | Date): string => {
  return dayjs(date).format('YYYY-MM-DD');
};

export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
};

export const formatPercentage = (value: number, decimals: number = 1): string => {
  return `${(value * 100).toFixed(decimals)}%`;
};

export const formatTaskStatus = (status: string): string => {
  const statusMap: Record<string, string> = {
    pending: '排队中',
    processing: '处理中',
    success: '完成',
    failed: '失败',
    cancelled: '已取消',
  };
  return statusMap[status] || status;
};

export const formatTaskStage = (stage: string): string => {
  const stageMap: Record<string, string> = {
    pending: '等待中',
    parsing: '解析中',
    chunking: '分块中',
    embedding: '向量化中',
    indexing: '索引中',
    completed: '已完成',
  };
  return stageMap[stage] || stage;
};

export const formatPageLabel = (pageLabel: string, chapterTitle?: string): string => {
  if (!pageLabel) return '无';
  
  if (pageLabel.endsWith('.xhtml') || pageLabel.endsWith('.html')) {
    const match = pageLabel.match(/part(\d+)/i) || pageLabel.match(/chapter(\d+)/i);
    if (match) {
      return `第${parseInt(match[1])}章`;
    }
    const numMatch = pageLabel.match(/(\d+)/);
    if (numMatch) {
      return `第${parseInt(numMatch[1])}章`;
    }
    return chapterTitle || '章节内容';
  }
  
  if (/^\d+$/.test(pageLabel)) {
    return `第 ${pageLabel} 页`;
  }
  
  return pageLabel;
};

export const formatScore = (score: string | number | null | undefined): string => {
  if (score === null || score === undefined || score === '') return '0.0';
  const num = Number(score);
  if (isNaN(num)) return '0.0';
  return num.toFixed(1);
};
