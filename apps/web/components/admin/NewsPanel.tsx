"use client";

import { useEffect, useState } from "react";
import { http } from "@/lib/api";

export function NewsPanel() {
  const [sources, setSources] = useState<any[]>([]);
  const [msg, setMsg] = useState("");

  const reload = () => {
    http.get("/admin/news-sources").then(setSources).catch(() => {});
  };
  useEffect(reload, []);

  const addSource = async () => {
    const name = (document.getElementById("news-name") as HTMLInputElement).value;
    const url = (document.getElementById("news-url") as HTMLInputElement).value;
    if (!name || !url) return alert("请填写名称和 URL");
    await http.post("/admin/news-sources", { name, url, type: "rss" });
    (document.getElementById("news-name") as HTMLInputElement).value = "";
    (document.getElementById("news-url") as HTMLInputElement).value = "";
    reload();
  };

  return (
    <div className="space-y-4">
      {msg && <div className="rounded-md bg-[#dafbe1] px-3 py-2 text-[13px] text-[#1a7f37]">{msg}</div>}
      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <h3 className="mb-2 text-[15px] font-semibold">AI 资讯源（每日抓取 → LLM 摘要 → 发布）</h3>
        <p className="mb-3 text-[12px] text-[#656d76]">每天 08:00 自动抓取资讯源，由 AI 摘要后发布到「AI 资讯」栏目。</p>
        <div className="mb-3 flex gap-2">
          <input id="news-name" placeholder="名称（如 AI 前线）" className="w-40 rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
          <input id="news-url" placeholder="RSS/API URL" className="w-80 rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
          <button onClick={addSource} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">+ 添加</button>
        </div>
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-[#d0d7de] text-left text-[#656d76]">
              <th className="py-2 pr-2">名称</th><th className="py-2 pr-2">URL</th><th className="py-2 pr-2">状态</th><th className="py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {sources.length === 0 && <tr><td colSpan={4} className="py-8 text-center text-[#656d76]">还没有资讯源</td></tr>}
            {sources.map((s) => (
              <tr key={s.id} className="border-b border-[#d0d7de]/50">
                <td className="py-2 font-medium">{s.name}</td>
                <td className="max-w-[300px] truncate py-2 text-[#656d76]">{s.url}</td>
                <td className="py-2">{s.enabled ? "启用" : "停用"}</td>
                <td className="py-2">
                  <button onClick={async () => { const r: any = await http.post(`/admin/news-sources/${s.id}/fetch`); setMsg(`已发布 ${r.published} 条`); }} className="text-[#0969da] hover:underline">立即抓取</button>
                  <button onClick={async () => { await http.del(`/admin/news-sources/${s.id}`); reload(); }} className="ml-2 text-[#cf222e] hover:underline">删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
