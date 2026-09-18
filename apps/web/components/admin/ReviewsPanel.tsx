"use client";

import { useEffect, useState } from "react";
import { http } from "@/lib/api";

type Filter = "all" | "post_rejected" | "post_mid" | "reply_low_conf" | "report";

const KIND_META: Record<string, { label: string; cls: string }> = {
  post_rejected: { label: "AI 审核不通过", cls: "bg-[#ffebe9] text-[#cf222e]" },
  post_mid: { label: "中危待审", cls: "bg-[#fff8c5] text-[#9a6700]" },
  reply_low_conf: { label: "AI 回复待审", cls: "bg-[#ddf4ff] text-[#0969da]" },
  report: { label: "用户举报", cls: "bg-[#ffebe9] text-[#cf222e]" },
};

export function ReviewsPanel() {
  const [reviews, setReviews] = useState<any[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [msg, setMsg] = useState("");

  const reload = () => {
    http.get("/admin/reviews").then(setReviews).catch(() => {});
  };
  useEffect(reload, []);

  const act = async (kind: string, id: number, action: string) => {
    try {
      await http.post(`/admin/reviews/action?kind=${kind}&id=${id}`, { action });
      setMsg(`已执行：${action}`);
      reload();
    } catch (e: any) {
      alert(e.message || "操作失败");
    }
  };

  const filtered = filter === "all" ? reviews : reviews.filter((r) => r.kind === filter);
  const counts: Record<string, number> = {};
  for (const r of reviews) counts[r.kind] = (counts[r.kind] || 0) + 1;

  return (
    <div className="space-y-4">
      {msg && <div className="rounded-md bg-[#dafbe1] px-3 py-2 text-[13px] text-[#1a7f37]">{msg}</div>}

      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <h3 className="mb-3 text-[15px] font-semibold">审核队列</h3>
        <p className="mb-3 text-[12px] text-[#656d76]">
          发帖后 AI 先审核（审核不通过的帖子在此处理：通过或删除）；同时包含合规中危帖、AI 回复低置信与用户举报。
        </p>
        {/* 分类 tab */}
        <div className="mb-3 flex flex-wrap gap-1">
          {([["all", "全部"], ["post_rejected", "AI 不通过"], ["post_mid", "中危帖"], ["reply_low_conf", "AI 待审"], ["report", "举报"]] as [Filter, string][]).map(([k, label]) => (
            <button
              key={k}
              onClick={() => setFilter(k)}
              className={`rounded-md px-3 py-1.5 text-[13px] ${filter === k ? "bg-[#0969da] text-white" : "bg-[#eaeef2] text-[#656d76] hover:bg-[#d0d7de]"}`}
            >
              {label}
              {k !== "all" && counts[k] ? <span className="ml-1 font-bold">{counts[k]}</span> : null}
            </button>
          ))}
        </div>

        {filtered.length === 0 ? (
          <div className="py-10 text-center text-[13px] text-[#656d76]">
            队列为空 · 新帖发布后会自动进入 AI 审核，不通过的内容会出现在这里
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map((r) => {
              const meta = KIND_META[r.kind] || { label: r.kind, cls: "bg-[#eaeef2] text-[#656d76]" };
              return (
                <div key={`${r.kind}-${r.id}`} className="rounded-md border border-[#d0d7de]/60 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${meta.cls}`}>{meta.label}</span>
                    <span className="text-[13px] font-medium">{r.title}</span>
                    {r.author_name && <span className="text-[12px] text-[#656d76]">by {r.author_name}</span>}
                    <span className="ml-auto text-[12px] text-[#656d76]">{r.reason}</span>
                  </div>
                  {r.body && <div className="mt-1 line-clamp-3 whitespace-pre-wrap text-[12px] text-[#656d76]">{r.body}</div>}
                  <div className="mt-2 flex gap-2">
                    <button onClick={() => act(r.kind, r.id, "approve")} className="rounded bg-[#1a7f37] px-2.5 py-1 text-[12px] text-white hover:bg-[#135c29]">
                      {r.kind === "post_rejected" ? "通过并发布" : "通过"}
                    </button>
                    <button onClick={() => act(r.kind, r.id, "hide")} className="rounded bg-[#9a6700] px-2.5 py-1 text-[12px] text-white hover:bg-[#744d00]">隐藏</button>
                    <button onClick={() => act(r.kind, r.id, "delete")} className="rounded bg-[#cf222e] px-2.5 py-1 text-[12px] text-white hover:bg-[#a01c26]">删除</button>
                    {r.kind === "report" && (
                      <button onClick={() => act(r.kind, r.id, "dismiss")} className="rounded border border-[#d0d7de] px-2.5 py-1 text-[12px] hover:bg-[#f3f4f6]">驳回举报</button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
