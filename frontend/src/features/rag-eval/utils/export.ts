/**
 * 触发浏览器下载 Blob 文件
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

/**
 * 将数据导出为 JSON 文件并触发下载
 *
 * @param data     - 任意可序列化数据
 * @param filename - 下载文件名（不含扩展名，自动追加 `.json`）
 */
export function exportToJSON(data: unknown, filename: string): void {
  const json = JSON.stringify(data, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  downloadBlob(blob, `${filename}.json`);
}

/**
 * 将行数组导出为 CSV 文件并触发下载
 *
 * @param rows     - 对象数组，每个对象的 key 作为 CSV 列名
 * @param filename - 下载文件名（不含扩展名，自动追加 `.csv`）
 */
export function exportToCSV(rows: Record<string, unknown>[], filename: string): void {
  if (rows.length === 0) return;

  const headers = Object.keys(rows[0]);
  const escape = (val: unknown): string => {
    const str = val == null ? '' : String(val);
    // 包含逗号、引号或换行符时需要用引号包裹，并转义内部引号
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  const headerLine = headers.join(',');
  const dataLines = rows.map((row) =>
    headers.map((h) => escape(row[h])).join(','),
  );
  const csv = [headerLine, ...dataLines].join('\n');

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  downloadBlob(blob, `${filename}.csv`);
}
