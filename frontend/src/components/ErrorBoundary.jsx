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
        <main className="grid min-h-screen place-items-center bg-[#0b0d12] p-6 text-slate-100">
          <div className="max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-7 text-center shadow-2xl">
            <p className="text-lg font-semibold">CodeX could not load the editor</p>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              Your saved code is still in this browser. Reload the page to try again.
            </p>
            <button
              className="mt-5 rounded-lg bg-indigo-500 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-400"
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
