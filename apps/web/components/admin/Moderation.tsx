"use client";

import { useEffect, useState } from "react";
import { http } from "@/lib/api";

export function Moderation() {
  const [reviews, setReviews] = useState<any[]>([]);
  const [sources, setSources] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [invites, setInvites] = useState<any[]>([]);
  const [msg, setMsg] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");

  const reload = () => {
    http.get("/admin/reviews").then(setReviews).catch(() => {});
    http.get("/admin/news-sources").then(setSources).catch(() => {});
    http.get("/admin/users?page_size=50").then((d: any) => setUsers(d.items || [])).catch(() => {});
    http.get("/admin/invitations").then(setInvites).catch(() => {});
  };
  useEffect(reload, []);

  const act = async (kind: string, id: number, action: string) => {
    await http.post(`/admin/reviews/action?kind=${kind}&id=${id}`, { action });
    reload();
  };

  const createInvite = async () => {
    await http.post("/admin/invitations", { email: inviteEmail || null });
    setInviteEmail("");
    setMsg("邀请码已生成");
    reload();
  };

  return (
    <div className="space-y-6">
      {msg && <div className="rounded-md bg-[#dafbe1] px-3 py-2 text-[13px] text-[#1a7f37]">{msg}</div>}

      {/* 审核队列 */}
      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <h3 className="mb-3 text-[15px] font-semibold">审核队列（合规中危帖 / 低置信 AI 回复 / 举报）</h3>
        {reviews.length === 0 && <div className="py-6 text-center text-[13px] text-[#656d76]">队列为空 ✅</div>}
        <div className="space-y-3">
          {reviews.map((r) => (
            <div key={`${r.kind}-${r.id}`} className="rounded-md border border-[#d0d7de]/60 p-3">
              <div className="flex items-center gap-2">
                <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${r.kind === "post_mid" ? "bg-[#fff8c5] text-[#9a6700]" : r.kind === "reply_low_conf" ? "bg-[#ddf4ff] text-[#0969da]" : "bg-[#ffebe9] text-[#cf222e]"}`}>
                  {r.kind === "post_mid" ? "中危帖" : r.kind === "reply_low_conf" ? "AI 待审" : "举报"}
                </span>
                <span className="text-[13px] font-medium">{r.title}</span>
                <span className="ml-auto text-[12px] text-[#656d76]">{r.reason}</span>
              </div>
              {r.body && <div className="mt-1 line-clamp-2 text-[12px] text-[#656d76]">{r.body}</div>}
              <div className="mt-2 flex gap-2">
                <button onClick={() => act(r.kind, r.id, "approve")} className="rounded bg-[#1a7f37] px-2 py-1 text-[12px] text-white">通过</button>
                <button onClick={() => act(r.kind, r.id, "hide")} className="rounded bg-[#9a6700] px-2 py-1 text-[12px] text-white">隐藏</button>
                <button onClick={() => act(r.kind, r.id, "delete")} className="rounded bg-[#cf222e] px-2 py-1 text-[12px] text-white">删除</button>
                {r.kind === "report" && <button onClick={() => act(r.kind, r.id, "dismiss")} className="rounded border border-[#d0d7de] px-2 py-1 text-[12px]">驳回举报</button>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 资讯源 */}
      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <h3 className="mb-3 text-[15px] font-semibold">AI 资讯源（每日抓取 → LLM 摘要 → 发布）</h3>
        <div className="mb-3 flex gap-2">
          <input id="news-name" placeholder="名称（如 AI 前线）" className="w-40 rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
          <input id="news-url" placeholder="RSS/API URL" className="w-80 rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
          <button
            onClick={async () => {
              const name = (document.getElementById("news-name") as HTMLInputElement).value;
              const url = (document.getElementById("news-url") as HTMLInputElement).value;
              if (!name || !url) return alert("请填写名称和 URL");
              await http.post("/admin/news-sources", { name, url, type: "rss" });
              reload();
            }}
            className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white"
          >
            + 添加
          </button>
        </div>
        <table className="w-full text-[13px]">
          <tbody>
            {sources.map((s) => (
              <tr key={s.id} className="border-b border-[#d0d7de]/50">
                <td className="py-2 font-medium">{s.name}</td>
                <td className="max-w-[300px] truncate py-2 text-[#656d76]">{s.url}</td>
                <td className="py-2">{s.enabled ? "启用" : "停用"}</td>
                <td className="py-2">
                  <button onClick={async () => { const r: any = await http.post(`/admin/news-sources/${s.id}/fetch`); setMsg(`已发布 ${r.published} 条`); }} className="text-[#0969da] hover:underline">立即抓取</button>
                  <button onClick={async () => { await http.post(`/admin/news-sources/${s.id}/fetch`); }} className="ml-2 text-[#cf222e] hover:underline">删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 用户 + 邀请码 */}
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
          <h3 className="mb-3 text-[15px] font-semibold">用户管理</h3>
          <table className="w-full text-[13px]">
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-[#d0d7de]/50">
                  <td className="py-2">{u.name}</td>
                  <td className="max-w-[180px] truncate py-2 text-[#656d76]">{u.email}</td>
                  <td className="py-2">
                    {u.role === "super_admin" ? <span className="text-[#0969da]">超管</span> : "成员"}
                    {u.status === "disabled" && <span className="ml-1 text-[#cf222e]">已禁用</span>}
                  </td>
                  <td className="py-2">
                    <button
                      onClick={async () => {
                        await http.put(`/admin/users/${u.id}`, { status: u.status === "disabled" ? "active" : "disabled" });
                        reload();
                      }}
                      className="text-[#0969da] hover:underline"
                    >
                      {u.status === "disabled" ? "启用" : "禁用"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
          <h3 className="mb-3 text-[15px] font-semibold">邀请码</h3>
          <div className="mb-3 flex gap-2">
            <input value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder="绑定邮箱（可选）" className="w-52 rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
            <button onClick={createInvite} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">生成</button>
          </div>
          <table className="w-full text-[13px]">
            <tbody>
              {invites.map((i) => (
                <tr key={i.id} className="border-b border-[#d0d7de]/50">
                  <td className="py-2 font-mono">{i.code}</td>
                  <td className="py-2 text-[#656d76]">{i.email || "不限"}</td>
                  <td className="py-2">
                    <span className={i.status === "valid" ? "text-[#1a7f37]" : i.status === "used" ? "text-[#656d76]" : "text-[#cf222e]"}>{i.status}</span>
                  </td>
                  <td className="py-2">
                    {i.status === "valid" && (
                      <button onClick={async () => { await http.del(`/admin/invitations/${i.id}`); reload(); }} className="text-[#cf222e] hover:underline">撤销</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
