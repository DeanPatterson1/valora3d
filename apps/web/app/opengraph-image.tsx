import { ImageResponse } from "next/og";

export const alt = "Valora3D — Your model. Your shot. Cinematic renders.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", width: "100%", height: "100%", padding: 80, background: "#0d0d0d", color: "#ffffff", fontFamily: "sans-serif" }}>
      <div style={{ display: "flex", fontSize: 32 }}>Valora3D</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <div style={{ display: "flex", fontSize: 76, fontWeight: 700, letterSpacing: -3 }}>Your model. Your shot.</div>
        <div style={{ display: "flex", fontSize: 30, color: "#b4b4b4" }}>Turn your 3D models into cinematic renders and videos.</div>
      </div>
      <div style={{ display: "flex", fontSize: 24, color: "#b4b4b4" }}>valora3d.com</div>
    </div>,
    size,
  );
}
