"use client";

import { useEffect, useState } from "react";
import { http } from "@/lib/api";
import { Modal } from "@/components/ui/Modal";

type Cat = {
  id: number; slug: string; name: string; description?: string; icon?: string;
  sort_order: number; allow_post: boolean; auto_reply_enabled: boolean;
  reply_threshold: number; notify_human_on_no_evidence: boolean;
  post_count?: number; ai_admin?: any; admins?: { user_id: number; name: string; email: string }[];
};

export function CategoryManager() {
  const [cats, setCats] = useState<Cat[]>([]);
  const [editing, setEditing] = useState<Cat | null>(null);
  const [creating, setCreating] = useState<Cat | null>(null);
  const [aiEditing, setAiEditing] = useState<Cat | null>(null);
  const [adminBinding, setAdminBinding] = useState<Cat | null>(null);
  const [msg, setMsg] = useState("");

  const reload = async () => {
    const list: Cat[] = await http.get("/admin/categories");
    for (const c of list) {
      c.admins = await http.get(`/admin/categories/${c.id}/admins`).catch(() => []);
    }
    setCats(list);
  };
  useEffect(() => { reload(); }, []);

  const saveCategory = async () => {
    if (!editing) return;
    await http.put(`/admin/categories/${editing.id}`, {
      name: editing.name, description: editing.description || "",
      icon: editing.icon || "📁", allow_post: editing.allow_post,
      auto_reply_enabled: editing.auto_reply_enabled, reply_threshold: Number(editing.reply_threshold),
      notify_human_on_no_evidence: editing.notify_human_on_no_evidence,
    });
    setEditing(null);
    setMsg("已保存");
    reload();
  };

  const createCategory = async () => {
    if (!creating) return;
    if (!creating.name || !creating.slug) return alert("名称和 slug 必填");
    await http.post("/admin/categories", { ...creating, reply_threshold: Number(creating.reply_threshold) });
    setCreating(null);
    setMsg("已创建");
    reload();
  };

  const saveAiAdmin = async () => {
    if (!aiEditing) return;
    const aa = aiEditing.ai_admin || {};
    await http.post(`/admin/categories/${aiEditing.id}/ai-admin`, {
      persona_name: aa.persona_name || "",
      system_prompt: aa.system_prompt || "",
      style_prompt: aa.style_prompt || "",
      model_config_id: aa.model_config_id || null,
      reply_threshold: aa.reply_threshold != null ? Number(aa.reply_threshold) : aiEditing.reply_threshold,
      self_review_threshold: aa.self_review_threshold != null ? Number(aa.self_review_threshold) : 0.9,
    });
    setAiEditing(null);
    setMsg("AI 管理员已保存");
    reload();
  };

  return (
    <div className="space-y-4">
      {msg && <div className="rounded-md bg-[#dafbe1] px-3 py-2 text-[13px] text-[#1a7f37]">{msg}</div>}

      <div className="flex justify-end">
        <button
          onClick={() => setCreating({ id: 0, slug: "", name: "", description: "", icon: "📁", sort_order: 0, allow_post: true, auto_reply_enabled: true, reply_threshold: 0.5, notify_human_on_no_evidence: true })}
          className="rounded-md bg-[#0969da] px-4 py-2 text-[13px] text-white hover:bg-[#0550ae]"
        >
          + 新建栏目
        </button>
      </div>

      <div className="rounded-lg border border-[#d0d7de] bg-white">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-[#d0d7de] text-left text-[#656d76]">
              <th className="px-4 py-2">栏目</th>
              <th className="py-2">帖子</th>
              <th className="py-2">AI 管理员</th>
              <th className="py-2">人工管理员</th>
              <th className="py-2 pr-4">操作</th>
            </tr>
          </thead>
          <tbody>
            {cats.map((c) => (
              <tr key={c.id} className="border-b border-[#d0d7de]/50">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2 font-medium">{c.icon} {c.name}</div>
                  <div className="text-[12px] text-[#656d76]">{c.slug} · {c.description}</div>
                </td>
                <td className="py-3 text-[#656d76]">{c.post_count}</td>
                <td className="py-3">
                  {c.ai_admin ? (
                    <span className="rounded bg-[#0969da]/10 px-1.5 py-0.5 text-[12px] text-[#0969da]">{c.ai_admin.persona_name}</span>
                  ) : <span className="text-[#656d76]">未配置</span>}
                </td>
                <td className="py-3 text-[#656d76]">
                  {c.admins?.length ? c.admins.map((a) => a.name).join("、") : "无"}
                </td>
                <td className="py-3 pr-4">
                  <div className="flex gap-1.5">
                    <button onClick={() => setEditing(c)} className="rounded border border-[#d0d7de] px-2 py-1 text-[12px] hover:bg-[#f3f4f6]">编辑</button>
                    <button onClick={() => setAiEditing(c)} className="rounded border border-[#d0d7de] px-2 py-1 text-[12px] hover:bg-[#f3f4f6]">AI 配置</button>
                    <button onClick={() => setAdminBinding(c)} className="rounded border border-[#d0d7de] px-2 py-1 text-[12px] hover:bg-[#f3f4f6]">绑定管理员</button>
                    <button onClick={async () => { if (confirm(`删除栏目「${c.name}」？`)) { await http.del(`/admin/categories/${c.id}`); reload(); } }} className="rounded border border-[#d0d7de] px-2 py-1 text-[12px] text-[#cf222e] hover:bg-[#ffebe9]">删除</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 编辑栏目（模态） */}
      <Modal open={!!editing} title="编辑栏目" width={560} onClose={() => setEditing(null)}>
        {editing && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">名称</label>
                <input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
              </div>
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">图标</label>
                <input value={editing.icon} onChange={(e) => setEditing({ ...editing, icon: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-[12px] text-[#656d76]">描述</label>
              <textarea value={editing.description || ""} onChange={(e) => setEditing({ ...editing, description: e.target.value })} rows={2} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={editing.allow_post} onChange={(e) => setEditing({ ...editing, allow_post: e.target.checked })} /> 允许发帖
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={editing.auto_reply_enabled} onChange={(e) => setEditing({ ...editing, auto_reply_enabled: e.target.checked })} /> 自动回复
              </label>
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">回复阈值</label>
                <input type="number" step="0.1" min={0} max={1} value={editing.reply_threshold} onChange={(e) => setEditing({ ...editing, reply_threshold: Number(e.target.value) })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={editing.notify_human_on_no_evidence} onChange={(e) => setEditing({ ...editing, notify_human_on_no_evidence: e.target.checked })} /> 无证据时通知人工
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setEditing(null)} className="rounded border border-[#d0d7de] px-3 py-1.5 text-[13px]">取消</button>
              <button onClick={saveCategory} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">保存</button>
            </div>
          </div>
        )}
      </Modal>

      {/* 新建栏目（模态） */}
      <Modal open={!!creating} title="新建栏目" width={560} onClose={() => setCreating(null)}>
        {creating && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">名称</label>
                <input value={creating.name} onChange={(e) => setCreating({ ...creating, name: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
              </div>
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">slug（URL 标识）</label>
                <input value={creating.slug} onChange={(e) => setCreating({ ...creating, slug: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-[12px] text-[#656d76]">描述</label>
              <textarea value={creating.description || ""} onChange={(e) => setCreating({ ...creating, description: e.target.value })} rows={2} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setCreating(null)} className="rounded border border-[#d0d7de] px-3 py-1.5 text-[13px]">取消</button>
              <button onClick={createCategory} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">创建</button>
            </div>
          </div>
        )}
      </Modal>

      {/* AI 管理员配置（模态） */}
      <Modal open={!!aiEditing} title={`AI 管理员配置 · ${aiEditing?.name || ""}`} width={640} onClose={() => setAiEditing(null)}>
        {aiEditing && (
          <div className="space-y-3">
            <AiAdminForm cat={aiEditing} onChange={(aa) => setAiEditing({ ...aiEditing, ai_admin: aa })} />
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setAiEditing(null)} className="rounded border border-[#d0d7de] px-3 py-1.5 text-[13px]">取消</button>
              <button onClick={saveAiAdmin} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">保存</button>
            </div>
          </div>
        )}
      </Modal>

      {/* 绑定管理员（模态，可搜索） */}
      <Modal open={!!adminBinding} title={`绑定管理员 · ${adminBinding?.name || ""}`} width={520} onClose={() => setAdminBinding(null)}>
        {adminBinding && <AdminPicker cat={adminBinding} onDone={() => { setAdminBinding(null); reload(); }} />}
      </Modal>
    </div>
  );
}

function AiAdminForm({ cat, onChange }: { cat: Cat; onChange: (aa: any) => void }) {
  const [models, setModels] = useState<any[]>([]);
  const aa = cat.ai_admin || {};
  useEffect(() => {
    http.get("/admin/model-configs").then(setModels).catch(() => {});
  }, []);
  const set = (k: string, v: any) => onChange({ ...aa, [k]: v });
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1 block text-[12px] text-[#656d76]">人设名称</label>
          <input value={aa.persona_name || ""} onChange={(e) => set("persona_name", e.target.value)} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
        </div>
        <div>
          <label className="mb-1 block text-[12px] text-[#656d76]">绑定模型</label>
          <select value={aa.model_config_id || ""} onChange={(e) => set("model_config_id", e.target.value ? Number(e.target.value) : null)} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm">
            <option value="">（默认模型）</option>
            {models.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </div>
      </div>
      <div>
        <label className="mb-1 block text-[12px] text-[#656d76]">系统提示词</label>
        <textarea value={aa.system_prompt || ""} onChange={(e) => set("system_prompt", e.target.value)} rows={4} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
      </div>
      <div>
        <label className="mb-1 block text-[12px] text-[#656d76]">回复风格提示词</label>
        <textarea value={aa.style_prompt || ""} onChange={(e) => set("style_prompt", e.target.value)} rows={2} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1 block text-[12px] text-[#656d76]">回复阈值</label>
          <input type="number" step="0.1" min={0} max={1} value={aa.reply_threshold != null ? aa.reply_threshold : 0.5} onChange={(e) => set("reply_threshold", Number(e.target.value))} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
        </div>
        <div>
          <label className="mb-1 block text-[12px] text-[#656d76]">自审阈值</label>
          <input type="number" step="0.05" min={0} max={1} value={aa.self_review_threshold != null ? aa.self_review_threshold : 0.9} onChange={(e) => set("self_review_threshold", Number(e.target.value))} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
        </div>
      </div>
    </div>
  );
}

function AdminPicker({ cat, onDone }: { cat: Cat; onDone: () => void }) {
  const [q, setQ] = useState("");
  const [users, setUsers] = useState<any[]>([]);
  const [selected, setSelected] = useState<number | null>(null);

  const search = async () => {
    const d: any = await http.get(`/admin/users?q=${encodeURIComponent(q)}&page_size=20`);
    setUsers(d.items);
  };
  useEffect(() => { search(); }, []);

  const bind = async () => {
    if (!selected) return alert("请选择用户");
    await http.post(`/admin/categories/${cat.id}/admins/${selected}`);
    onDone();
  };

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          placeholder="搜索 ID / 邮箱 / 名字"
          className="flex-1 rounded border border-[#d0d7de] px-2 py-1.5 text-sm"
        />
        <button onClick={search} className="rounded-md border border-[#d0d7de] px-3 py-1.5 text-[13px] hover:bg-[#f3f4f6]">搜索</button>
      </div>
      <div className="max-h-[320px] space-y-1 overflow-y-auto">
        {users.map((u) => (
          <label key={u.id} className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm ${selected === u.id ? "border-[#0969da] bg-[#0969da]/5" : "border-[#d0d7de] hover:bg-[#f6f8fa]"}`}>
            <input type="radio" name="admin-user" checked={selected === u.id} onChange={() => setSelected(u.id)} />
            <span className="w-10 text-[#656d76]">#{u.id}</span>
            <span className="font-medium">{u.name}</span>
            <span className="ml-auto text-[#656d76]">{u.email}</span>
          </label>
        ))}
        {users.length === 0 && <div className="py-8 text-center text-[13px] text-[#656d76]">无匹配用户</div>}
      </div>
      <div className="flex justify-end gap-2 pt-2">
        <button onClick={onDone} className="rounded border border-[#d0d7de] px-3 py-1.5 text-[13px]">取消</button>
        <button onClick={bind} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">确定绑定</button>
      </div>
    </div>
  );
}
