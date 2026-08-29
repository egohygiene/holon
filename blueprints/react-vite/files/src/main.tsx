import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app";
import { ErrorBoundary } from "./error-boundary";
import "./styles/identity.css";
import "./styles/foundation.css";

const root = document.getElementById("root");

if (root === null) {
  throw new Error("The React root element is missing.");
}

createRoot(root).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
