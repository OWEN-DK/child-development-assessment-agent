import { Tag } from 'antd';
import type { TestDomain } from '@entities/rag-eval';
import { DOMAIN_COLORS, formatDomain } from '@entities/rag-eval';

interface DomainTagProps {
  domain: TestDomain;
}

export function DomainTag({ domain }: DomainTagProps) {
  return <Tag color={DOMAIN_COLORS[domain]}>{formatDomain(domain)}</Tag>;
}
