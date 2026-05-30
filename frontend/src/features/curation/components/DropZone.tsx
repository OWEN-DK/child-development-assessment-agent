import React, { useState, useCallback, useRef } from 'react';
import styles from './DropZone.module.scss';

interface DropZoneProps {
  accept?: string[];
  maxSizeMB?: number;
  onFileSelect?: (file: File) => void;
  description?: string;
}

export const DropZone: React.FC<DropZoneProps> = ({
  accept = ['.epub'],
  maxSizeMB = 50,
  onFileSelect,
  description = '支持 .epub 格式，最大 50MB',
}) => {
  const [active, setActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setActive(false);
      const file = e.dataTransfer.files[0];
      if (file) {
        if (file.size > maxSizeMB * 1024 * 1024) return;
        const ext = '.' + file.name.split('.').pop()?.toLowerCase();
        if (accept.length && !accept.includes(ext)) return;
        onFileSelect?.(file);
      }
    },
    [accept, maxSizeMB, onFileSelect],
  );

  const handleClick = () => inputRef.current?.click();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFileSelect?.(file);
  };

  return (
    <div
      className={`${styles.dropzone} ${active ? styles['dropzone--active'] : ''}`}
      onDragOver={(e) => { e.preventDefault(); setActive(true); }}
      onDragLeave={() => setActive(false)}
      onDrop={handleDrop}
      onClick={handleClick}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept.join(',')}
        style={{ display: 'none' }}
        onChange={handleChange}
      />
      <div className={styles.dropzone__icon}>📂</div>
      <div className={styles.dropzone__text}>拖拽 EPUB 到此处，或点击选择文件</div>
      <div className={styles.dropzone__hint}>{description}</div>
    </div>
  );
};
