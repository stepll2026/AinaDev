"use client";

import { useEffect, useState } from "react";
import { http } from "@/lib/api";
import { Modal } from "@/components/ui/Modal";

export function RagManager() {
  const [docs, setDocs] = useState<any[]>([]);
  const [cats, setCats] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const [urlForm, setUrlForm] = useState({ category_id: 0, url: "", name: "" });
  const [viewChunks, setViewChunks] = useState<any>(null); // {doc, chunks}
  const [msg, setMsg] = useState("");

  const reload = async () => {
    const [ds, cs] = await Promise.all([
      http.get("/admin/rag").catch(() => []),
      http.get("/categories").catch(() => []),
    ]);
    setDocs(ds);
    setCats(cs);
    if (!urlForm.category_id && cs.length) setUrlForm((f) => ({ ...f, category_id: cs[0].id }));
  };
  useEffect(() => { reload(); }, []);

  const upload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const fd = new FormData();
    fd.append("category_id", String(urlForm.category_id || cats[0]?.id || 1));
    fd.append("file", f);
    setUploading(true);
    try {
      await http.upload("/admin/rag/upload", fd);
      setMsg(`已上传 ${f.name}，解析中…`);
      setTimeout(reload, 1500);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setUploading(false);
    }
  };

  const addUrl = async () => {
    if (!urlForm.url) return alert("请输入 URL");
    const fd = new FormData();
    fd.append("category_id", String(urlForm.category_id || cats[0]?.id || 1));
    fd.append("url", urlForm.url);
    if (urlForm.name) fd.append("name", urlForm.name);
    await http.upload("/admin/rag/url", fd);
    setUrlForm({ ...urlForm, url: "", name: "" });
    setMsg("URL 已添加，解析中…");
    setTimeout(reload, 1500);
  };

  const openChunks = async (doc: any) => {
    const chunks = await http.get(`/admin/rag/${doc.id}/chunks`).catch(() => []);
    setViewChunks({ doc, chunks });
  };

  return (
    <div className="space-y-4">
      {msg && <div className="rounded-md bg-[#dafbe1] px-3 py-2 text-[13px] text-[#1a7f37]">{msg}</div>}

      {/* 上传区 */}
      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <h3 className="mb-3 text-[15px] font-semibold">RAG 知识库</h3>
        <div className="flex flex-wrap items-center gap-2">
          <select value={urlForm.category_id} onChange={(e) => setUrlForm({ ...urlForm, category_id: Number(e.target.value) })} className="rounded border border-[#d0d7de] px-2 py-1.5 text-sm">
            {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <label className="cursor-pointer rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white hover:bg-[#0550ae]">
            {uploading ? "上传中…" : "📄 上传文件"}
            <input type="file" accept=".pdf,.docx,.md,.txt" onChange={upload} className="hidden" />
          </label>
          <span className="text-[12px] text-[#656d76]">支持 PDF / DOCX / MD / TXT，自动切片并向量化</span>
        </div>
        <div className="mt-2 flex gap-2">
          <input value={urlForm.url} onChange={(e) => setUrlForm({ ...urlForm, url: e.target.value })} placeholder="网页 URL（自动抓取正文并切片）" className="flex-1 rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
          <input value={urlForm.name} onChange={(e) => setUrlForm({ ...urlForm, name: e.target.value })} placeholder="文档名（可选）" className="w-48 rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
          <button onClick={addUrl} className="rounded-md border border-[#d0d7de] px-3 py-1.5 text-[13px] hover:bg-[#f3f4f6]">添加 URL</button>
        </div>
      </div>

      {/* 文档列表 */}
      <div className="rounded-lg border border-[#d0d7de] bg-white">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-[#d0d7de] text-left text-[#656d76]">
              <th className="px-4 py-2">文档</th><th className="py-2">栏目</th><th className="py-2">状态</th><th className="py-2">切片数</th><th className="py-2 pr-4">操作</th>
            </tr>
          </thead>
          <tbody>
            {docs.length === 0 && (
              <tr><td colSpan={5} className="py-10 text-center text-[#656d76]">还没有文档，上传文件或添加 URL 开始构建知识库</td></tr>
            )}
            {docs.map((d) => {
              const cat = cats.find((c) => c.id === d.category_id);
              return (
                <tr key={d.id} className="border-b border-[#d0d7de]/50">
                  <td className="max-w-[280px] truncate px-4 py-3 font-medium">
                    {d.filename}
                    <span className="ml-2 rounded bg-[#eaeef2] px-1.5 py-0.5 text-[11px] text-[#656d76]">{d.file_type}</span>
                  </td>
                  <td className="py-3 text-[#656d76]">{cat?.name || `#${d.category_id}`}</td>
                  <td className="py-3">
                    {d.status === "ready" ? <span className="rounded bg-[#dafbe1] px-1.5 py-0.5 text-[12px] text-[#1a7f37]">已就绪</span>
                      : d.status === "parsing" ? <span className="rounded bg-[#fff8c5] px-1.5 py-0.5 text-[12px] text-[#9a6700]">解析中</span>
                      : <span className="rounded bg-[#ffebe9] px-1.5 py-0.5 text-[12px] text-[#cf222e]">{d.status}</span>}
                  </td>
                  <td className="py-3">{d.chunk_count}</td>
                  <td className="py-3 pr-4">
                    <div className="flex gap-1.5">
                      <button onClick={() => openChunks(d)} className="rounded border border-[#d0d7de] px-2 py-1 text-[12px] hover:bg-[#f3f4f6]">切片</button>
                      <a href={`/api/admin/rag/${d.id}/download`} className="rounded border border-[#d0d7de] px-2 py-1 text-[12px] hover:bg-[#f3f4f6]">下载</a>
                      <button onClick={async () => { await http.post(`/admin/rag/${d.id}/toggle`); reload(); }} className="rounded border border-[#d0d7de] px-2 py-1 text-[12px] hover:bg-[#f3f4f6]">{d.enabled ? "停用" : "启用"}</button>
                      <button onClick={async () => { if (confirm("删除该文档及其向量索引？")) { await http.del(`/admin/rag/${d.id}`); reload(); } }} className="rounded border border-[#d0d7de] px-2 py-1 text-[12px] text-[#cf222e] hover:bg-[#ffebe9]">删除</button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* 切片查看（模态） */}
      <Modal open={!!viewChunks} title={`切片 · ${viewChunks?.doc?.filename || ""}`} width={760} onClose={() => setViewChunks(null)}>
        {viewChunks && (
          <div className="space-y-2">
            <p className="text-[12px] text-[#656d76]">共 {viewChunks.chunks.length} 个切片（按顺序切分，已向量化存入检索库）</p>
            {viewChunks.chunks.length === 0 && <div className="py-8 text-center text-[13px] text-[#656d76]">暂无可显示的切片（文档可能仍在解析）</div>}
            {viewChunks.chunks.map((c: any) => (
              <div key={c.id} className="rounded-md border border-[#d0d7de]/60 p-3">
                <div className="mb-1 flex items-center gap-2 text-[12px] text-[#656d76]">
                  <span className="rounded bg-[#0969da]/10 px-1.5 py-0.5 font-medium text-[#0969da]">chunk #{c.chunk_index + 1}</span>
                  {c.title && <span>{c.title}</span>}
                </div>
                <div className="line-clamp-4 whitespace-pre-wrap text-[13px] text-[#24292f]">{c.content}</div>
              </div>
            ))}
          </div>
        )}
      </Modal>
    </div>
  );
}
