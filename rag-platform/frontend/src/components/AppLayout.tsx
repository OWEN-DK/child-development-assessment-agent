/**
 * 应用布局外壳
 *
 * 提供侧边栏导航 + 顶部 Header（租户/用户信息）+ 内容区域（Outlet）
 */
import { useState, useMemo } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Avatar, Dropdown, Tag, Typography, type MenuProps } from 'antd'
import {
  DashboardOutlined,
  ApartmentOutlined,
  BookOutlined,
  SettingOutlined,
  UserOutlined,
  LogoutOutlined,
  TeamOutlined,
  SafetyOutlined,
} from '@ant-design/icons'
import { useAuth } from '@/shared/hooks/useAuth'
import { usePermission } from '@/shared/hooks/usePermission'

const { Header, Sider, Content } = Layout
const { Text } = Typography

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const { user, tenant, logout } = useAuth()
  const { isSuperadmin, isTenantAdmin } = usePermission()
  const navigate = useNavigate()
  const location = useLocation()

  /** 当前选中的菜单项 */
  const selectedKey = useMemo(() => {
    const path = location.pathname
    if (path === '/') return '/'
    if (path.startsWith('/pipelines')) return '/pipelines'
    if (path.startsWith('/knowledge/test-data')) return '/knowledge/test-data'
    if (path.startsWith('/knowledge')) return '/knowledge'
    if (path.startsWith('/admin/tenants')) return '/admin/tenants'
    if (path.startsWith('/admin/users')) return '/admin/users'
    if (path.startsWith('/admin/roles')) return '/admin/roles'
    return '/'
  }, [location.pathname])

  /** 管理子菜单默认展开 */
  const defaultOpenKeys = useMemo(() => {
    if (location.pathname.startsWith('/admin')) return ['admin-group']
    return []
  }, [location.pathname])

  /** 主侧边栏菜单 */
  const menuItems: MenuProps['items'] = [
    { key: '/', icon: <DashboardOutlined />, label: '首页' },
    { key: '/pipelines', icon: <ApartmentOutlined />, label: '管道管理' },
    { key: '/knowledge', icon: <BookOutlined />, label: '知识库' },
  ]

  // 管理子菜单（仅管理员/超管可见）
  if (isSuperadmin || isTenantAdmin) {
    menuItems.push({
      key: 'admin-group',
      icon: <SettingOutlined />,
      label: '系统管理',
      children: [
        ...(isSuperadmin
          ? [{ key: '/admin/tenants', icon: <TeamOutlined />, label: '租户管理' }]
          : []),
        { key: '/admin/users', icon: <UserOutlined />, label: '用户管理' },
        { key: '/admin/roles', icon: <SafetyOutlined />, label: '角色管理' },
      ],
    })
  }

  /** 菜单点击 → 导航 */
  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    // 父级菜单 key 'admin-group' 不触发导航
    if (key === 'admin-group') return
    navigate(key)
  }

  /** 用户下拉菜单 */
  const userDropdownItems: MenuProps['items'] = [
    {
      key: 'username',
      label: user?.username ?? '未登录',
      icon: <UserOutlined />,
      disabled: true,
    },
    {
      key: 'role-tag',
      label: `角色: ${user?.roles?.join(', ') ?? '无'}`,
      disabled: true,
    },
    { type: 'divider' },
    {
      key: 'logout',
      label: '退出登录',
      icon: <LogoutOutlined />,
      danger: true,
    },
  ]

  /** 用户下拉菜单点击 */
  const handleUserMenuClick: MenuProps['onClick'] = ({ key }) => {
    if (key === 'logout') {
      logout()
      navigate('/login')
    }
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* 侧边栏 */}
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        width={220}
        theme="dark"
        style={{ borderRight: '1px solid rgba(255,255,255,0.06)' }}
      >
        {/* Logo 区域 */}
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderBottom: '1px solid rgba(255,255,255,0.06)',
            transition: 'all 0.2s',
          }}
        >
          <Text
            strong
            style={{
              color: '#fff',
              fontSize: collapsed ? 18 : 16,
              whiteSpace: 'nowrap',
            }}
          >
            {collapsed ? 'RAG' : 'RAG Platform'}
          </Text>
        </div>

        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          defaultOpenKeys={defaultOpenKeys}
          items={menuItems}
          onClick={handleMenuClick}
        />
      </Sider>

      {/* 右侧：Header + Content */}
      <Layout>
        <Header
          style={{
            background: '#fff',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid #f0f0f0',
            height: 56,
            lineHeight: '56px',
          }}
        >
          {/* 左侧：租户标识 */}
          <div>
            {tenant ? (
              <Tag color="blue" style={{ fontSize: 13, padding: '2px 12px' }}>
                {tenant.name}
              </Tag>
            ) : (
              <Tag color="gold" style={{ fontSize: 13, padding: '2px 12px' }}>
                超级管理员
              </Tag>
            )}
          </div>

          {/* 右侧：用户下拉 */}
          <Dropdown
            menu={{ items: userDropdownItems, onClick: handleUserMenuClick }}
            placement="bottomRight"
            trigger={['click']}
          >
            <div
              style={{
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <Avatar
                size="small"
                icon={<UserOutlined />}
                style={{ backgroundColor: '#1677ff' }}
              />
              <Text>{user?.username ?? '未登录'}</Text>
            </div>
          </Dropdown>
        </Header>

        <Content style={{ background: '#f5f5f5', minHeight: 'calc(100vh - 56px)' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
