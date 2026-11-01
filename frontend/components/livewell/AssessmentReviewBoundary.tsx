"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = {
  title: string;
  children: ReactNode;
};

type State = {
  error: Error | null;
};

/**
 * Isolates Review-step panel crashes (common on iPad Safari) so one panel
 * cannot white-screen the entire assessment wizard.
 */
export class AssessmentReviewBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[AssessmentReviewBoundary:${this.props.title}]`, error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <section className="card home-safety-section">
          <h2>{this.props.title}</h2>
          <p className="error-text">
            This section could not load on this device. Other review sections below may still work.
          </p>
          <p className="muted" style={{ fontSize: "0.85rem" }}>
            {this.state.error.message || "Unknown client error"}
          </p>
          <button
            type="button"
            className="secondary"
            onClick={() => this.setState({ error: null })}
          >
            Try again
          </button>
        </section>
      );
    }
    return this.props.children;
  }
}
