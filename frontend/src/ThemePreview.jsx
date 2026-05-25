import React from "react";
import { THEMES } from "./theme/themes";

const PREVIEW_ORDER = ["A", "B", "C"];

function pickTheme(themeKey) {
  localStorage.setItem("farmula:theme", themeKey);
  window.alert(`Theme ${themeKey} chosen. Reload the main app to apply.`);
}

function PreviewCard({ themeKey, theme }) {
  const cssVars = {
    "--preview-primary": theme.primary,
    "--preview-accent": theme.accent,
    "--preview-bgBase": theme.bgBase,
    "--preview-bgAccent": theme.bgAccent,
    "--preview-cardBg": theme.cardBg,
    "--preview-cardBorder": theme.cardBorder,
    "--preview-text": theme.text,
    "--preview-textMuted": theme.textMuted,
    "--preview-sidebar": theme.sidebarBg,
    "--preview-sidebarText": theme.sidebarText,
  };

  return (
    <article className={`preview-card motif-${theme.motif}`} style={cssVars}>
      <header className="preview-head">
        <h2>{theme.name}</h2>
        <p>{themeKey === "A" ? "Warm earthy Sahyadri tones." : themeKey === "B" ? "Festival-inspired modern energy." : "Premium monsoon agritech minimalism."}</p>
      </header>

      <section className="preview-recommendation">
        <div className="preview-title-wrap">
          <p className="preview-eyebrow">Recommended Mandi</p>
          <h3>Khed APMC Mandi</h3>
        </div>
        <div className="preview-metrics">
          <div>
            <small>Net Price</small>
            <strong>Rs. 2,480</strong>
          </div>
          <div>
            <small>Distance</small>
            <strong>42 km</strong>
          </div>
          <div>
            <small>Forecast</small>
            <strong>+3.2%</strong>
          </div>
        </div>
        <div className="preview-actions">
          <span className="preview-badge">HOLD</span>
          <button type="button">Analyze Route</button>
        </div>
      </section>

      <button type="button" className="choose-theme-btn" onClick={() => pickTheme(themeKey)}>
        Choose this direction
      </button>
    </article>
  );
}

export default function ThemePreview() {
  return (
    <main className="theme-preview-page">
      <header className="theme-preview-header">
        <h1>Maharashtra Visual Identity Preview</h1>
        <p>Compare all three design directions and choose one to apply across Farmula.</p>
      </header>

      <section className="theme-preview-grid">
        {PREVIEW_ORDER.map((themeKey) => (
          <PreviewCard key={themeKey} themeKey={themeKey} theme={THEMES[themeKey]} />
        ))}
      </section>
    </main>
  );
}

