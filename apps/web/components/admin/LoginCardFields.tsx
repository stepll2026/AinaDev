"use client";

export function LoginCardFields({ site, onChange }: {
  site: { login_title?: string; login_subtitle?: string };
  onChange: (patch: { login_title?: string; login_subtitle?: string }) => void;
}) {
  return <>
    <label className="block min-w-0">
      <span className="mb-1 block text-[12px] text-[#656d76]">登录卡片标题</span>
      <input maxLength={120} value={site.login_title ?? ""} onChange={(e) => onChange({ login_title: e.target.value })} placeholder="AI 开发者社区" className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
    </label>
    <label className="block min-w-0">
      <span className="mb-1 block text-[12px] text-[#656d76]">登录卡片副标题</span>
      <input maxLength={240} value={site.login_subtitle ?? ""} onChange={(e) => onChange({ login_subtitle: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
    </label>
  </>;
}
