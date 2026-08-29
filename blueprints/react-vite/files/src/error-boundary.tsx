import type { ErrorInfo, ReactNode } from "react";
import { Component } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  failed: boolean;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  public state: ErrorBoundaryState = { failed: false };

  public static getDerivedStateFromError(): ErrorBoundaryState {
    return { failed: true };
  }

  public componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Application render failed", error, info.componentStack);
  }

  public render(): ReactNode {
    if (this.state.failed) {
      return (
        <main className="shell" id="main-content">
          <h1>Something went wrong</h1>
          <p>The application stopped safely. Reload the page or return to the home route.</p>
        </main>
      );
    }
    return this.props.children;
  }
}
