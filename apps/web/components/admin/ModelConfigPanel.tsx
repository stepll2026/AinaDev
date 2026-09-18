"use client";

import { useEffect, useState } from "react";
import { http } from "@/lib/api";
import { Modal } from "@/components/ui/Modal";

type Model = {
  id: number;
  name: string;
  provider: string;
  base_url: string;
  chat_model: string;
  embedding_model: string | null;
  embedding_dim: number;
  context_length: number;
  max_tokens: number;
  is_default: boolean;
  enabled: boolean;
  has_api_key: boolean;
};

const EMPTY = {
  name: "",
  provider: "openai_compatible",
  base_url: "",
  api_key: "",
  chat_model: "",
  embedding_model: "",
  embedding_dim: 1024,
  context_length: 128000,
  max_tokens: 2048,
  is_default: false,
  enabled: true,
};

const PRESETS: Record<string, { base_url: string; chat_model: string; embedding_model: string; embedding_dim: number; context_length: number }> = {
  "通义千问 DashScope": {
    base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    chat_model: "qwen-plus",
    embedding_model: "text-embedding-v3",
    embedding_dim: 1024,
    context_length: 131072,
  },
  "火山方舟 Ark": {
    base_url: "https://ark.cn-beijing.volces.com/api/v3",
    chat_model: "",
    embedding_model: "",
    embedding_dim: 2048,
    context_length: 128000,
  },
  "OpenAI": {
    base_url: "https://api.openai.com/v1",
    chat_model: "gpt-4o",
    embedding_model: "text-embedding-3-large",
    embedding_dim: 3072,
    context_length: 128000,
  },
};

export function ModelConfigPanel() {
  const [models, setModels] = useState<Model[]>([]);
  const [editing, setEditing] = useState<any>(null);
  const [isNew, setIsNew] = useState(true);
  const [testResult, setTestResult] = useState<{ ok: boolean; text: string } | null>(null);
  const [msg, setMsg] = useState("");

  const reload = () => {
    http.get<Model[]>("/admin/model-configs").then(setModels).catch(() => {});
  };
  useEffect(reload, []);

  const openNew = () => {
    setEditing({ ...EMPTY });
    setIsNew(true);
    setTestResult(null);
  };

  const openEdit = (m: Model) => {
    setEditing({
      name: m.name, provider: m.provider, base_url: m.base_url, api_key: "",
      chat_model: m.chat_model, embedding_model: m.embedding_model || "",
      embedding_dim: m.embedding_dim, context_length: m.context_length,
      max_tokens: m.max_tokens, is_default: m.is_default, enabled: m.enabled,
    });
    setIsNew(false);
    setTestResult(null);
  };

  const applyPreset = (name: string) => {
    const p = PRESETS[name];
    if (!p) return;
    setEditing((e: any) => ({ ...e, ...p }));
  };

  const set = (k: string, v: any) => setEditing((e: any) => ({ ...e, [k]: v }));

  const save = async () => {
    if (!editing.name || !editing.base_url || !editing.chat_model) {
      setMsg("名称 / Base URL / Chat 模型 为必填");
      return;
    }
    const body = { ...editing, api_key: editing.api_key || null };
    try {
      if (isNew) {
        await http.post("/admin/model-configs", body);
        setMsg("已创建模型配置");
      } else {
        const id = models.find((m) => m.name === editing.name)?.id;
        await http.put(`/admin/model-configs/${id}`, body);
        setMsg("已保存（Key 留空则保持原值）");
      }
      setEditing(null);
      reload();
    } catch (e: any) {
      setMsg(e.message || "保存失败");
    }
  };

  const testConnection = async () => {
    setTestResult({ ok: false, text: "测试中…" });
    try {
      const r = await http.post<{ ok: boolean; response?: string; error?: string }>("/admin/model-configs/test", {
        ...editing,
        api_key: editing.api_key || "",
      });
      setTestResult({ ok: r.ok, text: r.ok ? `连通正常：${r.response}` : `失败：${r.error}` });
    } catch (e: any) {
      setTestResult({ ok: false, text: e.message || "请求失败" });
    }
  };

  const remove = async (m: Model) => {
    if (!confirm(`删除模型配置「${m.name}」？`)) return;
    await http.del(`/admin/model-configs/${m.id}`);
    reload();
  };

  return (
    <div className="space-y-6">
      {msg && <div className="rounded-md bg-[#dafbe1] px-3 py-2 text-[13px] text-[#1a7f37]">{msg}</div>}

      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h3 className="text-[15px] font-semibold">模型配置（OpenAI 兼容协议）</h3>
            <p className="mt-1 text-[12px] text-[#656d76]">API Key 将 AES 加密存储，仅回传“是否已配置”，绝不回传明文。默认配置用于 AI 回帖与知识库向量化。</p>
          </div>
          <button onClick={openNew} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white hover:bg-[#0550ae]">+ 新建模型配置</button>
        </div>

        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-[#d0d7de] text-left text-[#656d76]">
              <th className="py-2 pr-2">名称</th><th className="py-2 pr-2">Base URL</th><th className="py-2 pr-2">Chat 模型</th><th className="py-2 pr-2">Embedding</th><th className="py-2 pr-2">维度</th><th className="py-2 pr-2">默认</th><th className="py-2 pr-2">状态</th><th className="py-2 pr-2">Key</th><th className="py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {models.length === 0 && <tr><td colSpan={9} className="py-8 text-center text-[#656d76]">还没有模型配置，点击「+ 新建模型配置」添加</td></tr>}
            {models.map((m) => (
              <tr key={m.id} className="border-b border-[#d0d7de]/50">
                <td className="py-2 pr-2 font-medium">{m.name}</td>
                <td className="max-w-[220px] truncate py-2 pr-2 text-[#656d76]">{m.base_url}</td>
                <td className="py-2 pr-2 font-mono">{m.chat_model}</td>
                <td className="py-2 pr-2 font-mono">{m.embedding_model || "-"}</td>
                <td className="py-2 pr-2">{m.embedding_dim}</td>
                <td className="py-2 pr-2">{m.is_default ? "✅" : ""}</td>
                <td className="py-2 pr-2">{m.enabled ? "启用" : <span className="text-[#9a6700]">停用</span>}</td>
                <td className="py-2 pr-2">{m.has_api_key ? "已配置" : <span className="text-[#9a6700]">未填</span>}</td>
                <td className="py-2 space-x-2">
                  <button onClick={() => openEdit(m)} className="text-[#0969da] hover:underline">编辑</button>
                  <button onClick={() => remove(m)} className="text-[#cf222e] hover:underline">删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 模型表单（模态） */}
      <Modal open={!!editing} title={isNew ? "新建模型配置" : `编辑 · ${editing?.name || ""}`} width={720} onClose={() => setEditing(null)}>
        {editing && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[12px] text-[#656d76]">快速模板：</span>
              {Object.keys(PRESETS).map((k) => (
                <button key={k} onClick={() => applyPreset(k)} className="rounded-full border border-[#d0d7de] px-3 py-1 text-[12px] hover:bg-white">{k}</button>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">配置名称 *</label>
                <input value={editing.name} onChange={(e) => set("name", e.target.value)} placeholder="如：通义千问" className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
              </div>
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">Base URL *</label>
                <input value={editing.base_url} onChange={(e) => set("base_url", e.target.value)} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 font-mono text-sm" />
              </div>
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">API Key {isNew ? "*" : "（留空保持原值）"}</label>
                <input type="password" value={editing.api_key} onChange={(e) => set("api_key", e.target.value)} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 font-mono text-sm" />
              </div>
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">Chat 模型 *</label>
                <input value={editing.chat_model} onChange={(e) => set("chat_model", e.target.value)} placeholder="如 qwen-plus / doubao-seed" className="w-full rounded border border-[#d0d7de] px-2 py-1.5 font-mono text-sm" />
              </div>
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">Embedding 模型</label>
                <input value={editing.embedding_model} onChange={(e) => set("embedding_model", e.target.value)} placeholder="如 text-embedding-v3" className="w-full rounded border border-[#d0d7de] px-2 py-1.5 font-mono text-sm" />
              </div>
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">Embedding 维度</label>
                <input type="number" value={editing.embedding_dim} onChange={(e) => set("embedding_dim", Number(e.target.value))} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
              </div>
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">上下文长度</label>
                <input type="number" value={editing.context_length} onChange={(e) => set("context_length", Number(e.target.value))} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
              </div>
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">最大输出 tokens</label>
                <input type="number" value={editing.max_tokens} onChange={(e) => set("max_tokens", Number(e.target.value))} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
              </div>
              <div className="flex items-end gap-4 pb-1">
                <label className="flex items-center gap-2 text-[13px]">
                  <input type="checkbox" checked={editing.is_default} onChange={(e) => set("is_default", e.target.checked)} /> 设为默认
                </label>
                <label className="flex items-center gap-2 text-[13px]">
                  <input type="checkbox" checked={editing.enabled} onChange={(e) => set("enabled", e.target.checked)} /> 启用
                </label>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2 pt-2">
              <button onClick={save} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white hover:bg-[#0550ae]">保存</button>
              <button onClick={testConnection} className="rounded-md border border-[#d0d7de] px-3 py-1.5 text-[13px] hover:bg-[#f3f4f6]">测试连接</button>
              <button onClick={() => setEditing(null)} className="rounded-md border border-[#d0d7de] px-3 py-1.5 text-[13px] hover:bg-[#f3f4f6]">取消</button>
              {testResult && (
                <span className={`text-[12px] ${testResult.ok ? "text-[#1a7f37]" : "text-[#cf222e]"}`}>{testResult.text}</span>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
