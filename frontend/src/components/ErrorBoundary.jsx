import React from "react";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, details) {
    console.error("CodeX interface error", error, details);
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="auth-page">
          <div className="panel auth-card max-w-md p-7 text-center">
            <p className="text-lg font-semibold text-[var(--text-strong)]">CodeX could not load the editor</p>
            <p className="mt-2 text-sm leading-6 text-[var(--text-muted)]">
              Your saved code is still in this browser. Reload the page to try again.
            </p>
            <button
              className="primary-button mt-5"
              onClick={() => window.location.reload()}
              type="button"
            >
              Reload CodeX
            </button>
          </div>
        </main>
      );
    }

    return this.props.children;
  }
}
