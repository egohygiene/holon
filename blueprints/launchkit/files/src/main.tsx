import { StrictMode } from "react";
import { hydrateRoot } from "react-dom/client";

import { App } from "./app";
import { ErrorBoundary } from "./error-boundary";
import "./styles/identity.css";
import "./styles/foundation.css";
import "./styles/launchkit.css";

const root = document.getElementById("root");

if (root === null) {
  throw new Error("The React root element is missing.");
}

hydrateRoot(
  root,
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
