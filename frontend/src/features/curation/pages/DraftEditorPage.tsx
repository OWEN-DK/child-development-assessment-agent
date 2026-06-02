import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Button, App, Modal, Spin, Segmented, Tooltip, Popover } from 'antd';
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
import rehypeRaw from 'rehype-raw';
import { useDraftEditor, ENTITY_TYPE_LABELS } from '../hooks/useDraftEditor';
import { EntityNav } from '../components/EntityNav';
import { InfoPanel } from '../components/InfoPanel';
import { RelationshipCards } from '../components/RelationshipCards';
import { CrossBookPanel } from '../components/CrossBookPanel';
import styles from './DraftEditorPage.module.scss';
import { stripFrontmatter, preprocessCurationMarkdown } from '../../../lib/markdown';


export const DraftEditorPage: React.FC = () => {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const [editMode, setEditMode] = useState(false);
  const [viewMode, setViewMode] = useState<'markdown' | 'relations' | 'crossbook'>('markdown');
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const sectionTargets = useMemo(() => [
    { key: 'entities', label: '已有实体', textMatch: '已有实体' },
    { key: 'relations', label: '主张', textMatch: '主张' },
    { key: 'stories', label: '案例/故事', textMatch: '案例/故事' },
    { key: 'coverage', label: '段落覆盖', textMatch: '段落覆盖' },
  ], []);

  const { message } = App.useApp();
  const contentRef = useRef<HTMLDivElement>(null);

  const location = useLocation();
  const isCompareMode = location.pathname.endsWith('/compare');

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
    relations,
    activeEntityRelations,
    groupedRelations,
    crossBookRelations,
    crossBookLoading,
    setContent,
    save,
    markReviewed,
    publish,
    setActiveEntity,
    toggleConfirm,
  } = useDraftEditor(bookId);

  const chapterTargets = useMemo(() => {
    if (!content) return [];
    const matches = content.match(/^# .+/gm) || [];
    return matches.slice(0, 24).map((line, idx) => ({
      key: `chapter-${idx}`,
      label: line.replace(/^#\s*/, '').trim(),
      textMatch: line.replace(/^#\s*/, '').trim(),
    }));
  }, [content]);

  // Scroll to entity heading when activeEntity changes (markdown mode)
  useEffect(() => {
    if (!activeEntity || !contentRef.current || viewMode !== 'markdown') return;
    const headings = contentRef.current.querySelectorAll('h3');
    for (const h of headings) {
      if (h.textContent?.includes(activeEntity)) {
        h.scrollIntoView({ behavior: 'smooth', block: 'center' });
        h.style.background = 'rgba(79, 70, 229, 0.1)';
        h.style.borderRadius = '4px';
        h.style.transition = 'background 0.3s';
        setTimeout(() => { h.style.background = ''; }, 2000);
        break;
      }
    }
  }, [activeEntity, viewMode]);

  const scrollToSection = (textMatch: string, key: string, heading: 'h1' | 'h2' = 'h2') => {
    if (!contentRef.current) return;
    const targets = contentRef.current.querySelectorAll(heading);
    for (const el of targets) {
      if (el.textContent?.includes(textMatch)) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        setActiveSection(key);
        return;
      }
    }
  };

  // 从关系卡片点击实体时切换到关系视图
  const handleEntityClick = (name: string) => {
    setActiveEntity(name);
    // 如果当前是 Markdown 模式，自动切到关系视图
    if (viewMode === 'markdown') {
      setViewMode('relations');
    }
  };

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

  const entityDistribution = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const entity of entities) {
      const type = entity.type || 'AutoEntity';
      counts[type] = (counts[type] || 0) + 1;
    }
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .map(([type, count]) => ({
        type,
        label: `${ENTITY_TYPE_LABELS[type]?.icon ?? '🧩'} ${ENTITY_TYPE_LABELS[type]?.label ?? type}`.trim(),
        count,
      }));
  }, [entities]);

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
            onSelect={(name) => {
              setActiveEntity(name);
              // 在 markdown 模式下点击实体 → 滚动到对应标题
              // 在关系模式下 → 自动过滤关系
            }}
            onToggleConfirm={toggleConfirm}
          />
        </div>

        {/* 中间：MD 正文 / 关系卡片 */}
        <div className={styles.content}>
          {viewMode === 'markdown' ? (
            editMode ? (
              <textarea
                className={styles['edit-area']}
                value={content}
                onChange={(e) => setContent(e.target.value)}
                style={{ width: '100%', maxWidth: 720 }}
              />
            ) : (
              <div className={styles['content-body']}>
                <div className={styles['section-nav']}>
                  {sectionTargets.map((s) => (
                    <Tooltip key={s.key} title={`跳转到「${s.label}」`}>
                      <Button
                        size="small"
                        type={activeSection === s.key ? 'primary' : 'default'}
                        onClick={() => scrollToSection(s.textMatch, s.key)}
                      >
                        {s.label}
                      </Button>
                    </Tooltip>
                  ))}

                  {chapterTargets.length > 0 && (
                    <Popover
                      trigger="click"
                      placement="bottom"
                      content={
                        <div style={{ display: 'grid', gap: 6, maxHeight: 320, overflow: 'auto', minWidth: 220 }}>
                          {chapterTargets.map((c) => (
                            <Button
                              key={c.key}
                              size="small"
                              type={activeSection === c.key ? 'primary' : 'default'}
                              onClick={() => scrollToSection(c.textMatch, c.key, 'h1')}
                              style={{ justifyContent: 'flex-start' }}
                            >
                              {c.label}
                            </Button>
                          ))}
                        </div>
                      }
                    >
                      <Button size="small">章节目录</Button>
                    </Popover>
                  )}
                </div>

                <div className={styles['md-body']} ref={contentRef}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
                    {preprocessCurationMarkdown(stripFrontmatter(content)) || '*暂无内容*'}
                  </ReactMarkdown>
                </div>
              </div>
            )
          ) : (
            <RelationshipCards
              allRelations={activeEntity ? activeEntityRelations : relations}
              groupedRelations={groupedRelations}
              activeEntity={activeEntity}
              hasActiveEntity={!!activeEntity}
              onEntityClick={handleEntityClick}
            />
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
          {/* 视图切换 */}
          {!editMode && (
            <div className={styles.panel__section} style={{
              background: 'var(--surface-panel)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--radius-md)',
              padding: 'var(--space-4)',
            }}>
              <div className={styles.panel__sectionTitle} style={{
                fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)',
                marginBottom: 'var(--space-3)',
              }}>
                视图模式
              </div>
              <Segmented
                block
                value={viewMode}
                onChange={(val) => setViewMode(val as 'markdown' | 'relations')}
                options={[
                  { label: '📝 原文', value: 'markdown' },
                  { label: '🔗 关系', value: 'relations' },
                  { label: '🌐 跨书', value: 'crossbook' },
                ]}
              />
              {viewMode === 'relations' && activeEntity && (
                <Button
                  size="small"
                  type="link"
                  style={{ marginTop: 8, padding: 0 }}
                  onClick={() => setActiveEntity(null)}
                >
                  清除筛选 · 显示全部关系
                </Button>
              )}
              {viewMode === 'relations' && !activeEntity && relations.length > 0 && (
                <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-tertiary)' }}>
                  点击左侧实体可筛选关系
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 跨书关系对比区块 */}
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

      {/* 跨书融合面板 */}
      {viewMode === 'crossbook' && bookId && (
        <div style={{ margin: '0 16px' }}>
          <CrossBookPanel bookId={bookId} />
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
            {editMode ? '编辑模式' : viewMode === 'relations' ? '关系视图' : '预览模式'} · v{draft.version}
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
