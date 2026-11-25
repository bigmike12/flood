import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from "recharts";
import type { StrategyResult } from "./types";

export default function ComparisonChart({ data }: { data: Record<string, StrategyResult> }) {
  const order = ["random", "pop_proportional", "nearest", "ai_optimised"];
  const rows = order.filter(k => data[k]).map(k => ({
    name: data[k].label.replace("Population-proportional", "Pop-prop").replace("Nearest-depot", "Nearest"),
    Coverage: data[k].coverage_pct,
    Casualties: data[k].casualties,
  }));
  const best = order.filter(k => data[k]).reduce((a, b) => data[b].casualties < data[a].casualties ? b : a, order[0]);
  return (
    <div>
      <ResponsiveContainer width="100%" height={170}>
        <BarChart data={rows} margin={{ top: 6, right: 6, left: -18, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="name" tick={{ fontSize: 9 }} />
          <YAxis tick={{ fontSize: 9 }} />
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 10 }} />
          <Bar dataKey="Coverage" fill="#2E4A7A" />
          <Bar dataKey="Casualties" fill="#E0872A" />
        </BarChart>
      </ResponsiveContainer>
      <table className="cmp">
        <thead><tr><th>Strategy</th><th>Cov%</th><th>Cas.</th><th>Averted</th></tr></thead>
        <tbody>
          {order.filter(k => data[k]).map(k => (
            <tr key={k} className={k === best ? "best" : ""}>
              <td>{data[k].label}</td>
              <td>{data[k].coverage_pct}</td>
              <td>{data[k].casualties}</td>
              <td>{data[k].casualties_averted}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
