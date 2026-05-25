import React, { useEffect } from "react";
import { THEME } from "./themes";

export default function ThemeProvider({ children }) {
  useEffect(() => {
    const root = document.documentElement;
    Object.entries(THEME).forEach(([key, value]) => {
      root.style.setProperty(`--theme-${key}`, value);
    });
  }, []);
  return children;
}

