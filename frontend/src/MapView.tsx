import { useEffect } from "react";
import { MapContainer, TileLayer, CircleMarker, useMap } from "react-leaflet";
import type { Snapshot } from "./types";

const stateColor: Record<string, string> = {
  safe: "#2e7d32", at_risk: "#e0a72a", awaiting_rescue: "#dd3333",
  rescued: "#1C7293", casualty: "#111111",
};
function floodColor(d: number) {
  if (d < 0.3) return "#bcd7f0";
  if (d < 0.7) return "#7fb0e0";
  if (d < 1.2) return "#3d7fc4";
  return "#1b4f8a";
}

function Recenter({ center }: { center: [number, number] }) {
  const map = useMap();
  useEffect(() => { map.setView(center, map.getZoom()); }, [center[0], center[1]]);
  return null;
}

export default function MapView({ snap, center, risk }:
  { snap: Snapshot | null; center: [number, number]; risk: { lat: number; lng: number; risk: number }[] | null; }) {
  return (
    <MapContainer center={center} zoom={12} style={{ height: "100%", width: "100%" }} preferCanvas>
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution="&copy; OpenStreetMap" />
      <Recenter center={center} />

      {risk && risk.filter(r => r.risk > 0.15).map((r, i) => (
        <CircleMarker key={"r" + i} center={[r.lat, r.lng]} radius={6} stroke={false}
          pathOptions={{ fillColor: "#E0872A", fillOpacity: 0.12 + 0.5 * r.risk }} />
      ))}

      {snap?.flood.map((f, i) => (
        <CircleMarker key={"f" + i} center={[f.lat, f.lng]} radius={5} stroke={false}
          pathOptions={{ fillColor: floodColor(f.depth), fillOpacity: 0.55 }} />
      ))}
      {snap?.people.map((p, i) => (
        <CircleMarker key={"p" + i} center={[p.lat, p.lng]} radius={2.6} stroke={false}
          pathOptions={{ fillColor: stateColor[p.state] || "#888", fillOpacity: 0.95 }} />
      ))}
      {snap?.units.map((u, i) => (
        <CircleMarker key={"u" + i} center={[u.lat, u.lng]} radius={4.6}
          pathOptions={{ color: "#fff", weight: 1, fillColor: u.kind === "ambulance" ? "#c2185b" : "#6a1b9a", fillOpacity: 1 }} />
      ))}
      {snap?.hospitals.map((h, i) => (
        <CircleMarker key={"h" + i} center={[h.lat, h.lng]} radius={7}
          pathOptions={{ color: "#0B2A4A", weight: 2, fillColor: "#fff", fillOpacity: 1 }} />
      ))}
    </MapContainer>
  );
}
