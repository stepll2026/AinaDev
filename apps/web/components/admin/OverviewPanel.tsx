"use client";

import { useEffect, useState } from "react";
import { http } from "@/lib/api";

export function OverviewPanel() {
  const [stats, setStats] = useState<any>(null);
  const [site, setSite] = useState<any>({});

  useEffect(() => {
    http.get("/admin/stats").then(setStats).catch(() => {});
    http.get("/admin/site-config").then(setSite).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      {stats && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            ["用户", stats.user_count], ["帖子", stats.post_count], ["回复", stats.reply_count], ["今日新帖", stats.today_posts],
            ["待审", stats.pending_reviews], ["举报", stats.open_reports], ["AI 回复", stats.ai_replies], ["知识文档", stats.doc_count],
          ].map(([label, value]) => (
            <div key={label as string} className="rounded-lg border border-[#d0d7de] bg-white p-4">
              <div className="text-[12px] text-[#656d76]">{label}</div>
              <div className="mt-1 text-[24px] font-semibold">{value}</div>
            </div>
          ))}
        </div>
      )}

      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <h3 className="mb-2 text-[15px] font-semibold">MCP 接入信息（供豆包工作配置）</h3>
        <div className="space-y-1 rounded-md bg-[#f6f8fa] p-3 font-mono text-[13px]">
          <div>服务器 URL：<span className="text-[#0969da]">{window.location.origin}/mcp</span></div>
          <div>传输类型：<span className="text-[#0969da]">HTTP（Streamable）</span></div>
          <div>Authorization：<span className="text-[#0969da]">Bearer {site.mcp_api_key || "（未设置）"}</span></div>
        </div>
        <p className="mt-2 text-[12px] text-[#656d76]">同事可在豆包工作中添加 MCP 服务器，接入后即可调用：合规审查、知识库检索、帖子/栏目管理、审核处置、每日资讯、周报、系统统计等工具。</p>
      </div>
    </div>
  );
}
