import { createContext, useContext, useEffect, useState } from "react";

const STORAGE_KEY = "senior-safety-a11y";

const A11yContext = createContext({
  enabled: false,
  setEnabled: () => {},
});

export function A11yProvider({ children }) {
  const [enabled, setEnabledState] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === "on";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    document.documentElement.dataset.a11y = enabled ? "on" : "off";
    try {
      localStorage.setItem(STORAGE_KEY, enabled ? "on" : "off");
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
    <button
      type="button"
      className="a11y-switch"
      aria-pressed={enabled}
      onClick={() => setEnabled(!enabled)}
    >
      {enabled ? "Accessibility-Friendly Mode: On" : "Standard Mode — switch to easier reading"}
    </button>
  );
}
