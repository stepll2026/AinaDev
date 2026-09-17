"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { CategoryManager } from "@/components/admin/CategoryManager";
import { RagManager } from "@/components/admin/RagManager";
import { ModelConfigPanel } from "@/components/admin/ModelConfigPanel";
import { Moderation } from "@/components/admin/Moderation";
import { SystemPanel } from "@/components/admin/SystemPanel";

type TabKey = "overview" | "categories" | "rag" | "models" | "moderation" | "system";

export default function AdminPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<TabKey>("overview");

  useEffect(() => {
    if (user && user.role !== "super_admin") router.push("/");
  }, [user, router]);

  if (!user || user.role !== "super_admin") {
    return <div className="p-10 text-center text-sm text-[#656d76]">加载中…</div>;
  }

  const tabs: { key: TabKey; label: string }[] = [
    { key: "overview", label: "总览 / MCP" },
    { key: "categories", label: "栏目 & AI 管理员" },
    { key: "rag", label: "知识库" },
    { key: "models", label: "模型配置" },
    { key: "moderation", label: "审核 / 资讯 / 用户" },
    { key: "system", label: "审计 & 设置" },
  ];

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-6">
      <div className="mb-5">
        <h1 className="text-[24px] font-semibold">管理后台</h1>
        <p className="text-[13px] text-[#656d76]">AI 原生运维控制台 · 所有 Agent 决策可审计</p>
      </div>
      <div className="mb-6 flex flex-wrap gap-1 border-b border-[#d0d7de]">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`border-b-2 px-3 py-2 text-sm font-medium ${tab === t.key ? "border-[#0969da] text-[#0969da]" : "border-transparent text-[#656d76] hover:text-[#24292f]"}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === "overview" && <SystemPanel />}
      {tab === "categories" && <CategoryManager />}
      {tab === "rag" && <RagManager />}
      {tab === "models" && <ModelConfigPanel />}
      {tab === "moderation" && <Moderation />}
      {tab === "system" && (
        <div className="rounded-lg border border-[#d0d7de] bg-white p-6">
          <h3 className="mb-3 text-[15px] font-semibold">审计与设置</h3>
          <p className="text-[13px] text-[#656d76]">完整审计在「总览 / MCP」页签查看。</p>
        </div>
      )}
    </div>
  );
}
