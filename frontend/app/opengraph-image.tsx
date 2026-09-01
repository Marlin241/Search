import { ImageResponse } from "next/og";
import { PRODUCT_NAME, TAGLINE } from "@/lib/brand";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OgImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: 80,
          background: "linear-gradient(135deg, #4f46e5, #14b8a6)",
          color: "white",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ fontSize: 40, fontWeight: 700 }}>{PRODUCT_NAME}</div>
        <div
          style={{
            fontSize: 60,
            fontWeight: 800,
            marginTop: 24,
            lineHeight: 1.1,
          }}
        >
          {TAGLINE}
        </div>
      </div>
    ),
    size
  );
}
