import React from "react";

export class ErrorBoundary extends React.Component {
  state = { hasError: false, error: null };

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error("ErrorBoundary caught:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 40, textAlign: "center", maxWidth: 500, margin: "60px auto" }}>
          <div style={{ fontSize: 40, marginBottom: 14 }}>⚠</div>
          <div style={{ fontSize: 18, fontWeight: 600, color: "#dc2626", marginBottom: 10 }}>
            Something went wrong
          </div>
          <div style={{ fontSize: 13, color: "#64748b", marginBottom: 20 }}>
            {this.state.error?.message || "An unexpected error occurred"}
          </div>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{
              padding: "8px 20px", borderRadius: 8, border: "1px solid #e2e8f0",
              background: "#f8fafc", cursor: "pointer", fontSize: 13, fontWeight: 600,
              color: "#334155",
            }}
          >
            Try Again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
