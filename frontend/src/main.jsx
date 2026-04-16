import React from "react";
import ReactDOM from "react-dom/client";
import { ErrorBoundary } from "./components/ErrorBoundary";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>
);
