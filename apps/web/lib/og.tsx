import { ImageResponse } from "next/og";

/** Social card size (Open Graph + X summary_large_image). */
export const OG_SIZE = { width: 1200, height: 630 };

/**
 * The one social-card layout: monochrome, the page's own title, the brand and address. Every public
 * route that has its own card renders through this, so the cards read as one family.
 */
export function ogCard({ eyebrow, title, lead }: { eyebrow?: string; title: string; lead: string }) {
  return new ImageResponse(
    <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", width: "100%", height: "100%", padding: 80, background: "#0d0d0d", color: "#ffffff", fontFamily: "sans-serif" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 16, fontSize: 32 }}>
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="9" stroke="#ffffff" strokeWidth="1.75" />
          <circle cx="12" cy="12" r="3.5" fill="#ffffff" />
        </svg>
        <div style={{ display: "flex" }}>Valora3D</div>
        {eyebrow && <div style={{ display: "flex", color: "#8a8a8a" }}>· {eyebrow}</div>}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <div style={{ display: "flex", fontSize: title.length > 28 ? 64 : 84, fontWeight: 700, letterSpacing: -3, lineHeight: 1.05 }}>{title}</div>
        <div style={{ display: "flex", fontSize: 30, color: "#b4b4b4", lineHeight: 1.35 }}>{lead}</div>
      </div>
      <div style={{ display: "flex", fontSize: 24, color: "#b4b4b4" }}>valora3d.com</div>
    </div>,
    OG_SIZE,
  );
}
