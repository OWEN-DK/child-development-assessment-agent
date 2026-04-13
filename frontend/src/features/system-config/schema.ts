export interface ConfigFieldSchema {
  key: string;
  type: 'boolean' | 'number' | 'string' | 'enum';
  label: string;
  description?: string;
  default?: any;
  min?: number;
  max?: number;
  step?: number;
  options?: { label: string; value: string | number }[];
  required?: boolean;
  disabled?: boolean;  // 只读字段
}

export const CONFIG_SCHEMAS: Record<string, ConfigFieldSchema[]> = {
  database: [
    {
      key: 'db_host',
      type: 'string',
      label: '数据库主机',
      description: 'MySQL 服务器地址',
      default: 'localhost',
      required: true,
    },
    {
      key: 'db_port',
      type: 'number',
      label: '数据库端口',
      description: 'MySQL 服务器端口',
      default: 3306,
      min: 1,
      max: 65535,
      required: true,
    },
    {
      key: 'db_user',
      type: 'string',
      label: '数据库用户',
      default: 'root',
      required: true,
    },
    {
      key: 'db_password',
      type: 'string',
      label: '数据库密码',
      default: '',
      required: false,
      disabled: true,  // 密码字段只允许修改，不允许查看
    },
    {
      key: 'pool_size',
      type: 'number',
      label: '连接池大小',
      default: 10,
      min: 1,
      max: 50,
      step: 1,
    },
  ],
  redis: [
    {
      key: 'redis_url',
      type: 'string',
      label: 'Redis URL',
      default: 'redis://localhost:6379/0',
      required: true,
    },
    {
      key: 'cache_enabled',
      type: 'boolean',
      label: '启用缓存',
      default: true,
    },
    {
      key: 'cache_default_ttl',
      type: 'number',
      label: '默认缓存 TTL',
      default: 3600,
      min: 60,
      max: 86400,
      step: 60,
    },
  ],
  // 其他配置模块后续扩展
};