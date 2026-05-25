// Farmula - Single Light Agriculture Theme
// Inspired by Maharashtra's sage fields, warm wheat tones, and mandi warmth.
// Designed for daytime use on phones in sunlit conditions.

export const THEME = {
  // Surfaces - warm cream tones
  bgBase: "#FAF8F3", // warm cream - page background
  bgElevated: "#FFFFFF", // pure white - cards
  bgSubtle: "#F3EFE7", // pale cream - secondary surfaces, inputs
  bgAccent: "#EDE5D4", // wheat tone - for borders and hover states

  // Text
  text: "#1F2419", // very dark olive - primary text
  textSubtle: "#5C6354", // muted olive - secondary text
  textMuted: "#8A9082", // soft gray-green - captions

  // Primary - sage green (not forest green, more inviting)
  primary: "#4A7C59", // sage green - buttons, key actions
  primaryHover: "#3D6849", // darker sage for hover
  primarySoft: "#E8F0E8", // very soft sage tint for backgrounds

  // Accent - warm turmeric
  accent: "#C9962E", // turmeric - highlights, metric values
  accentHover: "#A87E22",
  accentSoft: "#FAF1DC", // soft turmeric for backgrounds

  // Semantic colors
  success: "#5A8A4A", // healthy plant green
  warning: "#D49032", // ripe wheat orange
  danger: "#B85431", // terracotta - for sell-now alerts

  // Borders
  border: "#E5DDD0", // soft cream border
  borderStrong: "#C9BDA8", // wheat border for emphasis

  // Sidebar - distinct from main but still light
  sidebarBg: "#F3EDE0", // wheat cream - visible but not heavy
  sidebarText: "#2F3528", // dark olive
  sidebarHover: "#E8DFC8",
  sidebarActive: "#4A7C59", // sage for active item

  // Shadows
  shadowSoft: "0 1px 3px rgba(74, 56, 24, 0.06), 0 1px 2px rgba(74, 56, 24, 0.04)",
  shadowMd: "0 4px 12px rgba(74, 56, 24, 0.08), 0 2px 4px rgba(74, 56, 24, 0.04)",
  shadowLg: "0 12px 32px rgba(74, 56, 24, 0.10), 0 4px 12px rgba(74, 56, 24, 0.06)",
};

export function getActiveTheme() {
  return THEME;
}

