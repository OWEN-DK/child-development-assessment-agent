import { MAX_FILE_SIZE_MB, ALLOWED_FILE_EXTENSIONS } from '@shared/lib/constants';

export const validateFileType = (file: File): { valid: boolean; message?: string } => {
  const extension = '.' + file.name.split('.').pop()?.toLowerCase();
  const isAllowedType = ALLOWED_FILE_EXTENSIONS.includes(extension);
  
  if (!isAllowedType) {
    return {
      valid: false,
      message: `仅支持上传 ${ALLOWED_FILE_EXTENSIONS.join('、')} 格式的文件`,
    };
  }
  
  return { valid: true };
};

export const validateFileSize = (file: File): { valid: boolean; message?: string } => {
  const isLtMaxSize = file.size / 1024 / 1024 < MAX_FILE_SIZE_MB;
  
  if (!isLtMaxSize) {
    return {
      valid: false,
      message: `文件大小不能超过 ${MAX_FILE_SIZE_MB}MB`,
    };
  }
  
  return { valid: true };
};

export const validateFile = (file: File): { valid: boolean; message?: string } => {
  const typeValidation = validateFileType(file);
  if (!typeValidation.valid) return typeValidation;
  
  const sizeValidation = validateFileSize(file);
  if (!sizeValidation.valid) return sizeValidation;
  
  return { valid: true };
};

export const validateEmail = (email: string): boolean => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
};

export const validateAge = (age: number, min: number = 0, max: number = 18): boolean => {
  return age >= min && age <= max && Number.isInteger(age);
};
