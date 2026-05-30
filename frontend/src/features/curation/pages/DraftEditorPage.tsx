import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Button, App, Modal, Spin } from 'antd';
import {
  SaveOutlined,
  CheckOutlined,
  SendOutlined,
  EditOutlined,
  EyeOutlined,
  ArrowLeftOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useDraftEditor } from '../hooks/useDraftEditor';
import { curationApi } from '../api/curationApi';
import { EntityNav } from '../components/EntityNav';
import { InfoPanel } from '../components/InfoPanel';
import styles from './DraftEditorPage.module.scss';

const ENTITY_TYPES = ['Problem', 'Solution', 'BrainRegion', 'Exercise', 'Prescription', 'RootCause'];
const TYPE_LABELS: Record<string, string> = {
  Problem: '📋 问题',
  Solution: '✅ 方案',
  BrainRegion: '🧠 脑区',
  Exercise: '🏃 运动',
  Prescription: '💉 处方',
  RootCause: '⚠️ 根因',
};

export const DraftEditorPage: React.FC = () => {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const [editMode, setEditMode] = useState(false);
  const { message } = App.useApp();
  const contentRef = useRef<HTMLDivElement>(null);

  const location = useLocation();
  const isCompareMode = location.pathname.endsWith('/compare');
  const [crossBookRelations, setCrossBookRelations] = useState<any[]>([]);
  const [crossBookLoading, setCrossBookLoading] = useState(false);

  // Load cross-book data in compare mode
  useEffect(() => {
    if (isCompareMode && bookId) {
      setCrossBookLoading(true);
      curationApi.getCrossBookPairs([bookId])
        .then((res) => setCrossBookRelations(res.relations || []))
        .catch(() => setCrossBookRelations([]))
        .finally(() => setCrossBookLoading(false));
    }
  }, [isCompareMode, bookId]);

  const {
    draft,
    content,
    loading,
    saving,
    entities,
    groupedEntities,
    confirmedEntities,
    activeEntity,
    totalEntities,
    confirmedCount,
    setContent,
    save,
    markReviewed,
    publish,
    setActiveEntity,
    toggleConfirm,
  } = useDraftEditor(bookId);

  // Scroll to entity when activeEntity changes
  useEffect(() => {
    if (!activeEntity || !contentRef.current) return;
    // Find the heading that matches the entity name
    const headings = contentRef.current.querySelectorAll('h3');
    for (const h of headings) {
      if (h.textContent?.includes(activeEntity)) {
        h.scrollIntoView({ behavior: 'smooth', block: 'center' });
        // Brief highlight
        h.style.background = 'rgba(79, 70, 229, 0.1)';
        h.style.borderRadius = '4px';
        h.style.transition = 'background 0.3s';
        setTimeout(() => { h.style.background = ''; }, 2000);
        break;
      }
    }
  }, [activeEntity]);


  const handleSave = async () => {
    try {
      await save();
      message.success('保存成功');
    } catch {
      message.error('保存失败');
    }
  };

  const handleMarkReviewed = async () => {
    try {
      await markReviewed();
      message.success('已标记为已审核');
    } catch {
      message.error('标记失败');
    }
  };

  const handlePublish = () => {
    Modal.confirm({
      title: '确认入库',
      content: '入库后将写入 Neo4j 知识图谱，确认继续？',
      onOk: async () => {
        try {
          await publish();
          message.success('入库成功');
        } catch {
          message.error('入库失败');
        }
      },
    });
  };

  const handleExportMD = () => {
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${draft?.book_title || 'draft'}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const entityDistribution = ENTITY_TYPES.map((type) => ({
    type,
    label: TYPE_LABELS[type] || type,
    count: entities.filter((e) => e.type === type).length,
  }));

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!draft) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>📭</div>
        <div style={{ color: 'var(--text-tertiary)', marginBottom: 16 }}>未找到该书籍的草稿</div>
        <Button onClick={() => navigate('/curation')}>返回书籍列表</Button>
      </div>
    );
  }

  return (
    <>
      <div className={styles['draft-editor']}>
        {/* 左侧：实体导航 */}
        <div className={styles.nav}>
          <EntityNav
            entities={entities}
            groupedEntities={groupedEntities}
            confirmedEntities={confirmedEntities}
            activeEntity={activeEntity}
            confirmedCount={confirmedCount}
            totalEntities={totalEntities}
            onSelect={setActiveEntity}
            onToggleConfirm={toggleConfirm}
          />
        </div>

        {/* 中间：MD 正文 */}
        <div className={styles.content}>
          {editMode ? (
            <textarea
              className={styles['edit-area']}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              style={{ width: '100%', maxWidth: 720 }}
            />
          ) : (
            <div className={styles['md-body']} ref={contentRef}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content || '*暂无内容*'}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* 右侧：信息面板 */}
        <div className={styles.panel}>
          <InfoPanel
            bookTitle={draft.book_title}
            status={draft.status}
            version={draft.version}
            generatedAt={draft.generated_at}
            reviewedAt={draft.reviewed_at}
            reviewedBy={draft.reviewed_by}
            totalEntities={totalEntities}
            confirmedCount={confirmedCount}
            entityDistribution={entityDistribution}
            onViewGraph={() => navigate(`/curation/graph/${bookId}`)}
            onExportMD={handleExportMD}
          />
        </div>
      </div>

      {/* 跨书关系对比区块 (compare mode) */}
      {isCompareMode && (
        <div className={styles['cross-book-section']} style={{
          margin: '0 16px', padding: '16px', background: 'var(--surface-secondary)',
          borderRadius: '8px', border: '1px solid var(--border-default)'
        }}>
          <h3 style={{ margin: '0 0 12px', fontSize: 15, fontWeight: 600 }}>
            🔗 跨书关系对比
          </h3>
          {crossBookLoading ? (
            <Spin size="small" />
          ) : crossBookRelations.length === 0 ? (
            <div style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>
              暂无跨书关系数据（需先入库第二本书并建立跨书关系）
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {crossBookRelations.map((rel, i) => {
                const typeColors: Record<string, string> = {
                  CONSENSUS: '#10B981',
                  COMPLEMENTS: '#0EA5E9',
                  CONFLICTS: '#F43F5E',
                };
                const color = typeColors[rel.type] || '#A8A29E';
                return (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px',
                    background: 'var(--surface-primary)', borderRadius: 6,
                    borderLeft: `3px solid ${color}`,
                  }}>
                    <span style={{ fontWeight: 500 }}>{rel.source}</span>
                    <span style={{ color, fontSize: 12 }}>
                      {rel.type === 'CONFLICTS' ? '⚠️ 冲突' : rel.type === 'CONSENSUS' ? '✅ 共识' : '🔗 互补'}
                    </span>
                    <span style={{ fontWeight: 500 }}>{rel.target}</span>
                    <span style={{ color: 'var(--text-tertiary)', fontSize: 12, marginLeft: 'auto' }}>
                      来源: {rel.book1} → {rel.book2}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* 底部操作栏 */}
      <div className={styles.footer}>
        <div className={styles.footer__left}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/curation')}>
            返回
          </Button>
          {!isCompareMode && (
            <Button onClick={() => navigate(`/curation/editor/${bookId}/compare`)}>
              🔗 对比模式
            </Button>
          )}
          {isCompareMode && (
            <Button onClick={() => navigate(`/curation/editor/${bookId}`)}>
              📝 普通模式
            </Button>
          )}
          <Button
            icon={editMode ? <EyeOutlined /> : <EditOutlined />}
            onClick={() => setEditMode(!editMode)}
          >
            {editMode ? '预览' : '编辑'}
          </Button>
        </div>
        <div className={styles.footer__right}>
          <span className={styles.footer__status}>
            {editMode ? '编辑模式' : '预览模式'} · v{draft.version}
          </span>
          <Button icon={<SaveOutlined />} onClick={handleSave} loading={saving}>
            保存草稿
          </Button>
          {draft.status === 'draft' && (
            <Button icon={<CheckOutlined />} type="primary" onClick={handleMarkReviewed}>
              标记已审核
            </Button>
          )}
          {draft.status === 'reviewed' && (
            <Button icon={<SendOutlined />} type="primary" danger onClick={handlePublish}>
              入库 Neo4j
            </Button>
          )}
        </div>
      </div>
    </>
  );
};
