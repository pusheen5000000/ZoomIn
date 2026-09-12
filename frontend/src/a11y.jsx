import { createContext, useContext, useEffect, useState } from "react";

const STORAGE_KEY = "senior-safety-mode";

const A11yContext = createContext({
  enabled: false,
  setEnabled: () => {},
});

export function A11yProvider({ children }) {
  const [enabled, setEnabledState] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === "plain";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    document.documentElement.dataset.mode = enabled ? "plain" : "standard";
    try {
      localStorage.setItem(STORAGE_KEY, enabled ? "plain" : "standard");
    } catch {
      /* ignore */
    }
  }, [enabled]);

  return (
    <A11yContext.Provider value={{ enabled, setEnabled: setEnabledState }}>
      {children}
    </A11yContext.Provider>
  );
}

export function useA11y() {
  return useContext(A11yContext);
}

export function A11yToggle() {
  const { enabled, setEnabled } = useA11y();
  return (
    <div className="mode-switch" role="group" aria-label="Reading mode">
      <button
        type="button"
        aria-pressed={!enabled}
        className={!enabled ? "mode-btn on" : "mode-btn"}
        onClick={() => setEnabled(false)}
      >
        Standard mode
      </button>
      <button
        type="button"
        aria-pressed={enabled}
        className={enabled ? "mode-btn on" : "mode-btn"}
        onClick={() => setEnabled(true)}
      >
        Plain mode
      </button>
    </div>
  );
}
