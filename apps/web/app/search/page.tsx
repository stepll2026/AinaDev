"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { PostCard } from "@/components/PostCard";
import { http } from "@/lib/api";

function SearchInner() {
  const params = useSearchParams();
  const q = params.get("q") || "";
  const [data, setData] = useState<any>({ total: 0, items: [] });

  useEffect(() => {
    if (!q) return;
    http.get(`/search?q=${encodeURIComponent(q)}&page_size=20`).then(setData).catch(() => {});
  }, [q]);

  return (
    <div className="mx-auto flex max-w-[1280px] gap-8 px-4 py-6">
      <Sidebar />
      <main className="min-w-0 flex-1">
        <h1 className="mb-4 text-[20px] font-semibold">搜索「{q}」</h1>
        <div className="rounded-lg border border-[#d0d7de] bg-white px-3 py-1">
          {data.items.length === 0 ? (
            <div className="py-16 text-center text-sm text-[#656d76]">没有找到相关帖子</div>
          ) : (
            data.items.map((p: any) => <PostCard key={p.id} post={p} />)
          )}
        </div>
        <div className="mt-3 text-[12px] text-[#656d76]">共 {data.total} 条</div>
      </main>
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="p-10 text-center">加载中…</div>}>
      <SearchInner />
    </Suspense>
  );
}
