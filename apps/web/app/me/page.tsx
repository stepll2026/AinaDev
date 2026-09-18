"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { http } from "@/lib/api";
import { PostCard } from "@/components/PostCard";
import { Avatar, MarkdownView, TimeAgo } from "@/components/ui";

export default function MePage() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<"posts" | "favorites" | "notifications">("posts");
  const [posts, setPosts] = useState<any[]>([]);
  const [favs, setFavs] = useState<any[]>([]);
  const [notifs, setNotifs] = useState<any>({ items: [], unread: 0 });

  useEffect(() => {
    if (!user) {
      router.push("/login");
      return;
    }
    // 进入「我的」页即清空未读角标（Header 通过路由变化自动刷新）
    http.post("/me/notifications/read-all").catch(() => {});
    loadTab(tab);
  }, [user, tab]);

  const loadTab = (t: string) => {
    if (t === "posts") http.get("/me/posts?page_size=50").then((d: any) => setPosts(d.items || []));
    if (t === "favorites") http.get("/me/favorites").then(setFavs);
    if (t === "notifications") http.get("/me/notifications?page_size=50").then(setNotifs);
  };

  if (!user) return null;

  return (
    <div className="mx-auto flex max-w-[1012px] gap-8 px-4 py-6">
      <div className="w-[220px] shrink-0">
        <div className="rounded-lg border border-[#d0d7de] bg-white p-6 text-center">
          <div className="flex justify-center"><Avatar name={user.name} url={user.avatar_url} size={64} /></div>
          <div className="mt-3 text-[16px] font-semibold">{user.name}</div>
          <div className="text-[13px] text-[#656d76]">{user.email}</div>
          <div className="mt-1 text-[12px] text-[#656d76]">{user.role === "super_admin" ? "超级管理员" : "成员"} · 加入于 {new Date(user.created_at).toLocaleDateString("zh-CN")}</div>
          <div className="mt-4 flex justify-center gap-2">
            <button onClick={logout} className="rounded-md border border-[#d0d7de] px-3 py-1.5 text-[13px] text-[#656d76] hover:bg-[#f3f4f6]">退出登录</button>
            {user.role === "super_admin" && <button onClick={() => router.push("/admin")} className="rounded-md bg-[#0969da] px-3 py-1.5 text-[13px] text-white">管理后台</button>}
          </div>
        </div>
      </div>
      <main className="min-w-0 flex-1">
        <div className="mb-4 flex gap-1 border-b border-[#d0d7de]">
          {([
            { key: "posts", label: "我发的" },
            { key: "favorites", label: "我赞过的" },
            { key: "notifications", label: `通知${notifs.unread ? `（${notifs.unread}）` : ""}` },
          ] as const).map((t) => (
            <button key={t.key} onClick={() => setTab(t.key)} className={`border-b-2 px-3 py-2 text-sm font-medium ${tab === t.key ? "border-[#0969da] text-[#0969da]" : "border-transparent text-[#656d76]"}`}>
              {t.label}
            </button>
          ))}
        </div>
        <div className="rounded-lg border border-[#d0d7de] bg-white px-3 py-1">
          {tab === "posts" &&
            (posts.length === 0 ? <div className="py-16 text-center text-sm text-[#656d76]">还没有发过帖</div> : posts.map((p: any) => <PostCard key={p.id} post={p} />))}
          {tab === "favorites" &&
            (favs.length === 0 ? <div className="py-16 text-center text-sm text-[#656d76]">还没有赞过的帖子</div> : favs.map((p: any) => <PostCard key={p.id} post={p} />))}
          {tab === "notifications" && (
            <div>
              {notifs.items.length === 0 && <div className="py-16 text-center text-sm text-[#656d76]">暂无通知</div>}
              {notifs.items.map((n: any) => (
                <div key={n.id} className={`flex gap-3 border-b border-[#d0d7de]/50 px-1 py-3 ${n.is_read ? "opacity-60" : ""}`}>
                  <div className="min-w-0 flex-1">
                    <a href={n.link_url || undefined} className="text-[14px] font-medium text-[#24292f] hover:text-[#0969da]">{n.title}</a>
                    {n.body && <div className="mt-0.5 line-clamp-2 text-[13px] text-[#656d76]">{n.body}</div>}
                    <div className="mt-1 text-[12px] text-[#656d76]"><TimeAgo iso={n.created_at} /></div>
                  </div>
                </div>
              ))}
              {notifs.unread > 0 && (
                <div className="p-2 text-center">
                  <button onClick={() => http.post("/me/notifications/read-all").then(() => loadTab("notifications"))} className="text-[13px] text-[#0969da] hover:underline">
                    全部标为已读
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
