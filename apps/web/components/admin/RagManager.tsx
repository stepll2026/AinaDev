"use client";

import { useEffect, useState } from "react";
import { http } from "@/lib/api";

export function RagManager() {
  const [cats, setCats] = useState<any[]>([]);
  const [docs, setDocs] = useState<any[]>([]);
  const [catId, setCatId] = useState<number>(0);
  const [url, setUrl] = useState("");
  const [urlName, setUrlName] = useState("");
  const [models, setModels] = useState<any[]>([]);
  const [msg, setMsg] = useState("");

  const reload = () => {
    http.get("/categories").then((d) => {
      setCats(d);
      if (d.length && !catId) setCatId(d[0].id);
    });
    http.get("/admin/model-configs").then(setModels).catch(() => {});
  };
  useEffect(reload, []);

  const loadDocs = (cid?: number) => {
    const id = cid ?? catId;
    if (id) http.get(`/admin/rag?category_id=${id}`).then(setDocs).catch(() => setDocs([]));
  };
  useEffect(() => {
    if (catId) loadDocs();
  }, [catId]);

  const upload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !catId) return;
    const fd = new FormData();
    fd.append("category_id", String(catId));
    fd.append("file", file);
    await http.upload("/admin/rag/upload", fd);
    setMsg(`已上传 ${file.name}，后台解析中`);
    loadDocs();
  };

  const addUrl = async () => {
    if (!url || !catId) return;
    const fd = new FormData();
    fd.append("category_id", String(catId));
    fd.append("url", url);
    fd.append("name", urlName || url);
    await http.upload("/admin/rag/url", fd);
    setUrl("");
    setMsg("URL 已加入知识库，抓取解析中");
    loadDocs();
  };

  return (
    <div className="space-y-6">
      {msg && <div className="rounded-md bg-[#dafbe1] px-3 py-2 text-[13px] text-[#1a7f37]">{msg}</div>}

      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <h3 className="mb-3 text-[15px] font-semibold">RAG 知识库</h3>
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <select value={catId} onChange={(e) => { setCatId(Number(e.target.value)); loadDocs(Number(e.target.value)); }} className="rounded border border-[#d0d7de] px-2 py-1.5 text-sm">
            {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <label className="cursor-pointer rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white hover:bg-[#0550ae]">
            上传文档（PDF/DOCX/MD/TXT）
            <input type="file" accept=".pdf,.docx,.md,.txt" className="hidden" onChange={upload} />
          </label>
          <div className="flex items-center gap-2">
            <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="网页 URL（自动抓取正文）" className="w-64 rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
            <input value={urlName} onChange={(e) => setUrlName(e.target.value)} placeholder="文档名（可选）" className="w-40 rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
            <button onClick={addUrl} className="rounded-md border border-[#d0d7de] px-3 py-1.5 text-[13px] hover:bg-[#f3f4f6]">加入</button>
          </div>
        </div>
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-[#d0d7de] text-left text-[#656d76]">
              <th className="py-2 pr-2">文档</th><th className="py-2 pr-2">类型</th><th className="py-2 pr-2">状态</th><th className="py-2 pr-2">chunk</th><th className="py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {docs.length === 0 && <tr><td colSpan={5} className="py-8 text-center text-[#656d76]">该栏目还没有知识文档</td></tr>}
            {docs.map((d) => (
              <tr key={d.id} className="border-b border-[#d0d7de]/50">
                <td className="max-w-[300px] truncate py-2 pr-2">{d.filename}</td>
                <td className="py-2 pr-2 text-[#656d76]">{d.file_type}</td>
                <td className="py-2 pr-2">
                  <span className={`rounded px-1.5 py-0.5 text-[12px] ${d.status === "ready" ? "bg-[#dafbe1] text-[#1a7f37]" : d.status === "failed" ? "bg-[#ffebe9] text-[#cf222e]" : "bg-[#fff8c5] text-[#9a6700]"}`}>
                    {d.status}{d.status === "failed" ? `：${(d.error || "").slice(0, 40)}` : ""}
                  </span>
                </td>
                <td className="py-2 pr-2">{d.chunk_count}</td>
                <td className="py-2 space-x-2">
                  <button onClick={async () => { await http.post(`/admin/rag/${d.id}/toggle`); loadDocs(); }} className="text-[#0969da] hover:underline">{d.enabled ? "停用" : "启用"}</button>
                  <button onClick={async () => { await http.post(`/admin/rag/${d.id}/rebuild`); setMsg("已重建索引"); }} className="text-[#0969da] hover:underline">重建</button>
                  <button onClick={async () => { if (confirm("删除该文档？")) { await http.del(`/admin/rag/${d.id}`); loadDocs(); } }} className="text-[#cf222e] hover:underline">删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <h3 className="mb-3 text-[15px] font-semibold">模型配置（OpenAI 兼容协议）</h3>
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-[#d0d7de] text-left text-[#656d76]">
              <th className="py-2 pr-2">名称</th><th className="py-2 pr-2">Base URL</th><th className="py-2 pr-2">Chat 模型</th><th className="py-2 pr-2">Embedding</th><th className="py-2 pr-2">维度</th><th className="py-2 pr-2">默认</th><th className="py-2">Key</th>
            </tr>
          </thead>
          <tbody>
            {models.map((m) => (
              <tr key={m.id} className="border-b border-[#d0d7de]/50">
                <td className="py-2 pr-2 font-medium">{m.name}</td>
                <td className="max-w-[220px] truncate py-2 pr-2 text-[#656d76]">{m.base_url}</td>
                <td className="py-2 pr-2">{m.chat_model}</td>
                <td className="py-2 pr-2">{m.embedding_model || "-"}</td>
                <td className="py-2 pr-2">{m.embedding_dim}</td>
                <td className="py-2 pr-2">{m.is_default ? "✅" : ""}</td>
                <td className="py-2">{m.has_api_key ? "已配置" : <span className="text-[#9a6700]">未填</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-[12px] text-[#656d76]">完整的新增 / 编辑 / 测试 / 删除请切换到「模型配置」页签。</p>
      </div>
    </div>
  );
}
