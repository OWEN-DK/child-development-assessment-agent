/**
 * 前端导出工具函数
 * 支持 CSV 和 JSON 格式导出
 */

import { message } from 'antd';

/**
 * 导出测试用例结果为 CSV
 *
 * @param runId - 测试运行 ID
 * @param fileName - 导出文件名（不含扩展名）
 */
export const exportCasesToCSV = async (runId: string, fileName: string = 'test_results'): Promise<void> => {
  try {
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '';
    const response = await fetch(`${apiBaseUrl}/rag/test/runs/${runId}`);
    if (!response.ok) {
      throw new Error('获取测试运行数据失败');
    }

    const runData = await response.json();
    const results = runData.test_results || [];

    if (results.length === 0) {
      message.warning('暂无可导出的数据');
      return;
    }

    // 准备 CSV 数据
    const headers = ['查询', '状态', 'Hit@1', 'Hit@3', 'Hit@5', '耗时(ms)', '匹配文档数'];
    const rows = results.map((r: any) => [
      r.query || '',
      r.status || '',
      r.hit_at_1 ? '是' : '否',
      r.hit_at_3 ? '是' : '否',
      r.hit_at_5 ? '是' : '否',
      r.duration_ms || '',
      Array.isArray(r.matched_doc_ids) ? r.matched_doc_ids.length : 0,
    ]);

    // 生成 CSV 内容
    const csvContent = [
      headers.join(','),
      ...rows.map((row: string[]) => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')),
    ].join('\n');

    // 添加 BOM 以支持 Excel 打开 UTF-8
    const bom = '\uFEFF';
    const blob = new Blob([bom + csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${fileName}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);

    message.success(`已导出 ${results.length} 条结果到 ${fileName}.csv`);
  } catch (error) {
    message.error('导出 CSV 失败');
    console.error('Export CSV error:', error);
  }
};

/**
 * 导出报告数据为 JSON
 *
 * @param reportId - 报告 ID
 * @param fileName - 导出文件名（不含扩展名）
 */
export const exportReportToJSON = async (reportId: string, fileName: string = 'report'): Promise<void> => {
  try {
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '';
    const response = await fetch(`${apiBaseUrl}/rag/test/reports/${reportId}`);
    if (!response.ok) {
      throw new Error('获取报告数据失败');
    }

    const reportData = await response.json();

    // 格式化 JSON
    const jsonStr = JSON.stringify(reportData, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${fileName}.json`;
    a.click();
    window.URL.revokeObjectURL(url);

    message.success('报告已导出为 JSON');
  } catch (error) {
    message.error('导出 JSON 失败');
    console.error('Export JSON error:', error);
  }
};
