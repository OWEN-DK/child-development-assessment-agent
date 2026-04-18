import { Component, ErrorInfo, ReactNode } from 'react';
import { Result, Button } from 'antd';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ConfigErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('配置组件错误:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <Result
          status="error"
          title="配置加载失败"
          subTitle={this.state.error?.message || '未知错误'}
          extra={[
            <Button
              type="primary"
              key="retry"
              onClick={() => this.setState({ hasError: false, error: null })}
            >
              重试
            </Button>
          ]}
        />
      );
    }

    return this.props.children;
  }
}
