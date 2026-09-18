"use client";

import { useEffect, useState } from "react";
import { http } from "@/lib/api";

export function AuditPanel() {
  const [logs, setLogs] = useState<any[]>([]);
  const [runs, setRuns] = useState<any>({ items: [] });
  const [traceId, setTraceId] = useState("");

  useEffect(() => {
    http.get("/admin/audit-logs?page_size=20").then(setLogs).catch(() => {});
    http.get("/admin/agent-runs?page_size=15").then(setRuns).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <h3 className="mb-2 text-[15px] font-semibold">Agent 执行记录（流水线全链路审计）</h3>
        <div className="mb-2 flex gap-2">
          <input value={traceId} onChange={(e) => setTraceId(e.target.value)} placeholder="trace_id 查询" className="flex-1 rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
          <button onClick={() => http.get(`/admin/agent-runs?trace_id=${traceId}`).then(setRuns)} className="rounded border border-[#d0d7de] px-2 py-1.5 text-sm">查询</button>
        </div>
        <table className="w-full text-[12px]">
          <thead>
            <tr className="border-b border-[#d0d7de] text-left text-[#656d76]">
              <th className="py-1.5 pr-2">trace</th><th className="py-1.5 pr-2">节点</th><th className="py-1.5 pr-2">决策</th><th className="py-1.5 pr-2">评分</th><th className="py-1.5">耗时</th>
            </tr>
          </thead>
          <tbody>
            {runs.items.map((r: any) => (
              <tr key={r.id} className="border-b border-[#d0d7de]/50">
                <td className="py-1.5 font-mono">{r.trace_id.slice(0, 8)}</td>
                <td className="py-1.5">{r.node}</td>
                <td className="py-1.5">{r.decision}</td>
                <td className="py-1.5">{r.score ?? "-"}</td>
                <td className="py-1.5 text-[#656d76]">{r.latency_ms}ms</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <h3 className="mb-2 text-[15px] font-semibold">操作审计日志</h3>
        <table className="w-full text-[12px]">
          <thead>
            <tr className="border-b border-[#d0d7de] text-left text-[#656d76]">
              <th className="py-1.5 pr-2">操作</th><th className="py-1.5 pr-2">操作用户</th><th className="py-1.5">时间</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((l) => (
              <tr key={l.id} className="border-b border-[#d0d7de]/50">
                <td className="py-1.5">{l.action}</td>
                <td className="py-1.5 text-[#656d76]">{l.actor_type}{l.actor_id ? `#${l.actor_id}` : ""}</td>
                <td className="py-1.5 font-mono text-[11px]">{l.created_at?.slice(0, 16)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
