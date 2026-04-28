import { Tabs } from 'antd';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  FileTextOutlined,
  AuditOutlined,
  FolderOpenOutlined,
  PlayCircleOutlined,
  BarChartOutlined,
  ToolOutlined,
} from '@ant-design/icons';

const tabItems = [
  { key: 'drafts', label: '草稿管理', icon: <FileTextOutlined /> },
  { key: 'cases', label: '测试用例', icon: <AuditOutlined /> },
  { key: 'sets', label: '测试集', icon: <FolderOpenOutlined /> },
  { key: 'runs', label: '运行', icon: <PlayCircleOutlined /> },
  { key: 'reports', label: '报告', icon: <BarChartOutlined /> },
  { key: 'tuning', label: '调优', icon: <ToolOutlined /> },
];

function RagEvalMainPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const activeKey = tabItems
    .map((t) => t.key)
    .find((key) => location.pathname.includes(`/rag-eval/${key}`)) || 'drafts';

  return (
    <div>
      <Tabs
        activeKey={activeKey}
        onChange={(key) => navigate(`/rag-eval/${key}`)}
        items={tabItems}
        style={{ marginBottom: 16 }}
      />
      <Outlet />
    </div>
  );
};

export default RagEvalMainPage;
