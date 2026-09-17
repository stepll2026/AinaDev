"use client";

import { useEffect, useState } from "react";
import { http } from "@/lib/api";

export function CategoryManager() {
  const [cats, setCats] = useState<any[]>([]);
  const [editing, setEditing] = useState<any | null>(null);
  const [aiForm, setAiForm] = useState<any | null>(null);
  const [models, setModels] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [msg, setMsg] = useState("");

  const reload = () => {
    http.get("/admin/categories").then(setCats);
    http.get("/admin/model-configs").then(setModels).catch(() => {});
    http.get("/admin/users?page_size=100").then((d: any) => setUsers(d.items || [])).catch(() => {});
  };
  useEffect(reload, []);

  const saveCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    const body = new FormData(e.target as HTMLFormElement);
    const data: any = {
      slug: body.get("slug"), name: body.get("name"), description: body.get("description"),
      icon: body.get("icon"), sort_order: Number(body.get("sort_order") || 0),
      allow_post: body.get("allow_post") === "on", auto_reply_enabled: body.get("auto_reply_enabled") === "on",
      reply_threshold: Number(body.get("reply_threshold") || 0.7),
      notify_human_on_no_evidence: body.get("notify_human") === "on",
    };
    if (editing?.id) await http.put(`/admin/categories/${editing.id}`, data);
    else await http.post("/admin/categories", data);
    setEditing(null);
    setMsg("已保存");
    reload();
  };

  const openAi = (c: any) => {
    setAiForm({
      category_id: c.id, category_name: c.name,
      persona_name: c.ai_admin?.persona_name || `${c.name} AI 助手`,
      system_prompt: c.ai_admin?.system_prompt || "",
      style_prompt: c.ai_admin?.style_prompt || "",
      model_config_id: c.ai_admin?.model_config_id || "",
      reply_threshold: c.ai_admin?.reply_threshold ?? c.reply_threshold,
      self_review_threshold: c.ai_admin?.self_review_threshold || 0.6,
    });
  };

  const saveAi = async (e: React.FormEvent) => {
    e.preventDefault();
    const body = new FormData(e.target as HTMLFormElement);
    const data: any = {
      persona_name: body.get("persona_name"),
      system_prompt: body.get("system_prompt"),
      style_prompt: body.get("style_prompt"),
      model_config_id: body.get("model_config_id") ? Number(body.get("model_config_id")) : null,
      reply_threshold: body.get("reply_threshold") ? Number(body.get("reply_threshold")) : null,
      self_review_threshold: Number(body.get("self_review_threshold") || 0.6),
      auto_reply_enabled: true, active: true,
    };
    await http.post(`/admin/categories/${aiForm.category_id}/ai-admin`, data);
    setAiForm(null);
    setMsg("AI 管理员已保存");
    reload();
  };

  const bindAdmin = async (c: any, userId: string) => {
    if (!userId) return;
    await http.post(`/admin/categories/${c.id}/admins/${userId}`);
    setMsg("已绑定人类管理员");
  };

  return (
    <div className="space-y-6">
      {msg && <div className="rounded-md bg-[#dafbe1] px-3 py-2 text-[13px] text-[#1a7f37]">{msg}</div>}

      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-[15px] font-semibold">栏目管理</h3>
          <button onClick={() => setEditing({})} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">
            + 新建栏目
          </button>
        </div>
        {editing && (
          <form onSubmit={saveCategory} className="mb-4 space-y-2 rounded-md bg-[#f6f8fa] p-4">
            <div className="grid grid-cols-2 gap-3">
              <input name="name" defaultValue={editing.name} placeholder="名称" required className="rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
              <input name="slug" defaultValue={editing.slug} placeholder="slug（如 ai-news）" required className="rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
              <input name="icon" defaultValue={editing.icon} placeholder="图标 emoji" className="rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
              <input name="sort_order" defaultValue={editing.sort_order ?? 0} placeholder="排序" type="number" className="rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
            </div>
            <input name="description" defaultValue={editing.description} placeholder="描述" className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
            <div className="flex flex-wrap gap-4 text-[13px]">
              <label className="flex items-center gap-1"><input type="checkbox" name="allow_post" defaultChecked={editing.allow_post !== false} /> 允许发帖</label>
              <label className="flex items-center gap-1"><input type="checkbox" name="auto_reply_enabled" defaultChecked={editing.auto_reply_enabled !== false} /> 自动回帖</label>
              <label className="flex items-center gap-1"><input type="checkbox" name="notify_human" defaultChecked={editing.notify_human_on_no_evidence !== false} /> 无证据时通知管理员补文档</label>
              <label className="flex items-center gap-1">
                回帖阈值 <input name="reply_threshold" type="number" step="0.05" defaultValue={editing.reply_threshold ?? 0.7} className="w-20 rounded border border-[#d0d7de] px-2 py-1" />
              </label>
            </div>
            <div className="flex gap-2">
              <button className="rounded bg-[#0969da] px-3 py-1.5 text-[13px] text-white">保存</button>
              <button type="button" onClick={() => setEditing(null)} className="rounded border border-[#d0d7de] px-3 py-1.5 text-[13px]">取消</button>
            </div>
          </form>
        )}
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-[#d0d7de] text-left text-[#656d76]">
              <th className="py-2 pr-2">栏目</th><th className="py-2 pr-2">AI 管理员</th><th className="py-2 pr-2">阈值</th><th className="py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {cats.map((c) => (
              <tr key={c.id} className="border-b border-[#d0d7de]/50">
                <td className="py-2 pr-2 font-medium">{c.icon} {c.name} <span className="text-[#656d76] font-normal">({c.post_count} 帖)</span></td>
                <td className="py-2 pr-2">
                  {c.ai_admin ? <span className="rounded bg-[#0969da]/10 px-1.5 py-0.5 text-[#0969da]">{c.ai_admin.persona_name}</span> : <span className="text-[#656d76]">未配置</span>}
                </td>
                <td className="py-2 pr-2">{c.reply_threshold}</td>
                <td className="py-2 space-x-2">
                  <button onClick={() => { setEditing(c); }} className="text-[#0969da] hover:underline">编辑</button>
                  <button onClick={() => openAi(c)} className="text-[#0969da] hover:underline">AI 配置</button>
                  <button
                    onClick={async () => {
                      const uid = prompt("绑定人类管理员 User ID：");
                      if (uid) await bindAdmin(c, uid);
                    }}
                    className="text-[#0969da] hover:underline"
                  >
                    绑定管理员
                  </button>
                  <button
                    onClick={async () => {
                      if (confirm(`删除栏目「${c.name}」？`)) {
                        await http.del(`/admin/categories/${c.id}`);
                        reload();
                      }
                    }}
                    className="text-[#cf222e] hover:underline"
                  >
                    删除
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {aiForm && (
        <div className="rounded-lg border border-[#0969da]/30 bg-white p-4">
          <h3 className="mb-3 text-[15px] font-semibold">AI 管理员配置 · {aiForm.category_name}</h3>
          <form onSubmit={saveAi} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">AI 名称（persona）</label>
                <input name="persona_name" defaultValue={aiForm.persona_name} required className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
              </div>
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">模型</label>
                <select name="model_config_id" defaultValue={aiForm.model_config_id || ""} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm">
                  <option value="">系统默认</option>
                  {models.map((m) => <option key={m.id} value={m.id}>{m.name}（{m.chat_model}）</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className="mb-1 block text-[12px] text-[#656d76]">职责说明 system_prompt</label>
              <textarea name="system_prompt" defaultValue={aiForm.system_prompt} placeholder="如：你是 XX 产品技术支持工程师，只回答与 XX 相关的问题" rows={2} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
            </div>
            <div>
              <label className="mb-1 block text-[12px] text-[#656d76]">回复风格 style_prompt</label>
              <textarea name="style_prompt" defaultValue={aiForm.style_prompt} placeholder="语气/长度/是否给代码示例/是否分步" rows={2} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
            </div>
            <div className="flex gap-4 text-[13px]">
              <label>回帖阈值 <input name="reply_threshold" type="number" step="0.05" defaultValue={aiForm.reply_threshold} className="w-20 rounded border border-[#d0d7de] px-2 py-1" /></label>
              <label>自检阈值 <input name="self_review_threshold" type="number" step="0.05" defaultValue={aiForm.self_review_threshold} className="w-20 rounded border border-[#d0d7de] px-2 py-1" /></label>
            </div>
            <div className="flex gap-2">
              <button className="rounded bg-[#0969da] px-3 py-1.5 text-[13px] text-white">保存 AI 管理员</button>
              <button type="button" onClick={() => setAiForm(null)} className="rounded border border-[#d0d7de] px-3 py-1.5 text-[13px]">取消</button>
            </div>
          </form>
        </div>
      )}

      {users.length > 0 && (
        <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
          <h3 className="mb-2 text-[15px] font-semibold">用户列表（绑定人类管理员用）</h3>
          <select onChange={(e) => setMsg(`选中的用户 ID：${e.target.value}（在栏目操作里输入该 ID 绑定）`)} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm">
            <option value="">选择用户…</option>
            {users.map((u) => <option key={u.id} value={u.id}>{u.name}（{u.email} · ID {u.id}）</option>)}
          </select>
        </div>
      )}
    </div>
  );
}
