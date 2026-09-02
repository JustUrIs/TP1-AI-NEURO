import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Gold Dice RL — jugá contra los agentes entrenados",
  description:
    "Gold Dice RL en el navegador: jugá contra agentes entrenados con aprendizaje por refuerzos y descubrí, contra la solución exacta del juego, cuánto de tu resultado fue decisión y cuánto fue suerte.",
};

export const viewport: Viewport = {
  themeColor: "#0b0d12",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
