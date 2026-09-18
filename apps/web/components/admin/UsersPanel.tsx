"use client";

import { useEffect, useState } from "react";
import { http } from "@/lib/api";
import { Modal } from "@/components/ui/Modal";

export function UsersPanel() {
  const [users, setUsers] = useState<any[]>([]);
  const [invites, setInvites] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [editUser, setEditUser] = useState<any>(null);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteNote, setInviteNote] = useState("");
  const [msg, setMsg] = useState("");

  const reload = () => {
    http.get(`/admin/users?q=${encodeURIComponent(q)}&page_size=50`).then((d: any) => setUsers(d.items)).catch(() => {});
    http.get("/admin/invitations").then(setInvites).catch(() => {});
  };
  useEffect(reload, []);

  const saveUser = async () => {
    if (!editUser) return;
    await http.put(`/admin/users/${editUser.id}`, { name: editUser.name, role: editUser.role, status: editUser.status });
    setEditUser(null);
    setMsg("已保存");
    reload();
  };

  const createInvite = async () => {
    if (!inviteEmail) return;
    await http.post("/admin/invitations", { email: inviteEmail, note: inviteNote || null });
    setInviteEmail("");
    setInviteNote("");
    reload();
  };

  return (
    <div className="space-y-4">
      {msg && <div className="rounded-md bg-[#dafbe1] px-3 py-2 text-[13px] text-[#1a7f37]">{msg}</div>}
      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <h3 className="mb-2 text-[15px] font-semibold">用户管理</h3>
        <div className="mb-3 flex gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && reload()}
            placeholder="搜索姓名 / 邮箱"
            className="w-64 rounded border border-[#d0d7de] px-2 py-1.5 text-sm"
          />
          <button onClick={reload} className="rounded-md border border-[#d0d7de] px-3 py-1.5 text-[13px] hover:bg-[#f3f4f6]">搜索</button>
        </div>
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-[#d0d7de] text-left text-[#656d76]">
              <th className="py-2 pr-2">ID</th><th className="py-2 pr-2">姓名</th><th className="py-2 pr-2">邮箱</th><th className="py-2 pr-2">角色</th><th className="py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-[#d0d7de]/50">
                <td className="py-2 text-[#656d76]">{u.id}</td>
                <td className="py-2 font-medium">{u.name}</td>
                <td className="py-2 text-[#656d76]">{u.email}</td>
                <td className="py-2">{u.role === "super_admin" ? "管理员" : "成员"}</td>
                <td className="py-2">
                  <button onClick={() => setEditUser(u)} className="text-[#0969da] hover:underline">编辑</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <h3 className="mb-2 text-[15px] font-semibold">邀请码</h3>
        <div className="mb-3 flex gap-2">
          <input value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder="受邀人邮箱" className="w-64 rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
          <input value={inviteNote} onChange={(e) => setInviteNote(e.target.value)} placeholder="备注（可选）" className="w-40 rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
          <button onClick={createInvite} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">生成邀请码</button>
        </div>
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-[#d0d7de] text-left text-[#656d76]">
              <th className="py-2 pr-2">邀请码</th><th className="py-2 pr-2">受邀邮箱</th><th className="py-2 pr-2">状态</th><th className="py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {invites.map((i) => (
              <tr key={i.id} className="border-b border-[#d0d7de]/50">
                <td className="py-2 font-mono text-[12px]">{i.code}</td>
                <td className="py-2 text-[#656d76]">{i.email}</td>
                <td className="py-2">{i.status === "active" ? "有效" : i.status}</td>
                <td className="py-2">
                  {i.status === "active" && (
                    <button onClick={async () => { await http.del(`/admin/invitations/${i.id}`); reload(); }} className="text-[#cf222e] hover:underline">作废</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Modal open={!!editUser} title="编辑用户" width={480} onClose={() => setEditUser(null)}>
        {editUser && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">姓名</label>
                <input value={editUser.name} onChange={(e) => setEditUser({ ...editUser, name: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
              </div>
              <div>
                <label className="mb-1 block text-[12px] text-[#656d76]">角色</label>
                <select value={editUser.role} onChange={(e) => setEditUser({ ...editUser, role: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm">
                  <option value="member">成员</option>
                  <option value="super_admin">管理员</option>
                </select>
              </div>
            </div>
            <div>
              <label className="mb-1 block text-[12px] text-[#656d76]">状态</label>
              <select value={editUser.status} onChange={(e) => setEditUser({ ...editUser, status: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm">
                <option value="active">正常</option>
                <option value="disabled">禁用</option>
              </select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setEditUser(null)} className="rounded border border-[#d0d7de] px-3 py-1.5 text-[13px]">取消</button>
              <button onClick={saveUser} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">保存</button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
