import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import { A11yProvider } from "./a11y.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <A11yProvider>
      <App />
    </A11yProvider>
  </React.StrictMode>
);
