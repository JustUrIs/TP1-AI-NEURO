import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Sin esto Turbopack sube buscando un lockfile y toma el home del usuario
  // como raiz del proyecto.
  turbopack: { root: dirname(fileURLToPath(import.meta.url)) },
  // Los binarios de public/models son inmutables: llevan el nombre del modelo y
  // se regeneran solo cuando se reentrena. Cachearlos fuerte evita bajar 2 MB
  // en cada visita.
  async headers() {
    return [
      {
        source: "/models/:path*",
        headers: [{ key: "Cache-Control", value: "public, max-age=31536000, immutable" }],
      },
    ];
  },
};
export default nextConfig;
