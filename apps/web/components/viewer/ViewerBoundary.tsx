"use client";

import { Component, type ReactNode } from "react";
import { Button } from "@/components/ui";

type Props = { children: ReactNode; className?: string };
type State = { failed: boolean; attempt: number };

/** Catches anything thrown by the canvas (WebGL unavailable, loader crash) and offers a retry. */
export class ViewerBoundary extends Component<Props, State> {
  state: State = { failed: false, attempt: 0 };

  static getDerivedStateFromError(): Partial<State> {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    console.error("3D preview failed", error);
  }

  reload = () => {
    this.setState((s) => ({ failed: false, attempt: s.attempt + 1 }));
  };

  render() {
    if (this.state.failed) {
      return (
        <div
          role="alert"
          className={`flex h-full w-full flex-col items-center justify-center gap-4 bg-bg-1 p-8 text-center ${this.props.className ?? ""}`}
        >
          <p className="tracking-tight text-xl font-semibold text-fg">3D preview failed to start</p>
          <p className="max-w-sm text-sm text-fg-muted">
            Your browser could not start the 3D view. Check that hardware acceleration is on, then try again.
          </p>
          <Button variant="primary" onClick={this.reload}>
            Reload
          </Button>
        </div>
      );
    }
    // Re-key so the subtree mounts fresh after a reload.
    return <div key={this.state.attempt} className="contents">{this.props.children}</div>;
  }
}
