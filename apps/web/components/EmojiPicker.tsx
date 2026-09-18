"use client";

/**
 * Emoji 图标选择器（参照微信表情选择面板）：
 * 搜索 + 分区展示 + 点击选中 + 确认/取消。
 * 用于栏目图标等需要从固定集合中选取 emoji 的场景。
 */

import { useMemo, useState } from "react";
import { Modal } from "@/components/ui/Modal";

const GROUPS: { name: string; emojis: string[] }[] = [
  {
    name: "常用",
    emojis: ["📁", "📢", "🤖", "💡", "❓", "📰", "🔧", "🚀", "💬", "📚", "🏠", "⭐"],
  },
  {
    name: "技术",
    emojis: ["💻", "🖥️", "⌨️", "🖱️", "📡", "🛰️", "🔬", "🧪", "🧠", "🤖", "👾", "🛠️", "⚙️", "🔩", "💾", "🕸️", "🌐", "🔒", "🗄️", "☁️", "🅰️", "⚡"],
  },
  {
    name: "交流",
    emojis: ["💬", "🗨️", "📝", "✍️", "📣", "📢", "🔊", "💭", "❓", "❗", "💡", "📌", "🗂️", "📑", "📊", "📈", "📉"],
  },
  {
    name: "生活",
    emojis: ["☕", "🍵", "🍔", "🍎", "🎧", "🎮", "🎯", "🏆", "🎉", "🎊", "✨", "🌈", "🌤️", "🌧️", "🏞️", "🏙️", "🚗", "✈️", "🧳", "📷", "🎨", "🎵"],
  },
  {
    name: "办公",
    emojis: ["📋", "📅", "📆", "⏰", "⏳", "📁", "🗃️", "📎", "📌", "📏", "✂️", "🖇️", "📮", "✉️", "📧", "☎️", "📞", "💼", "👔", "👥", "🗣️", "🤝"],
  },
  {
    name: "符号",
    emojis: ["✅", "❌", "⚠️", "🚫", "🟢", "🟡", "🔴", "🔵", "🟣", "🟠", "⚪", "⚫", "🔺", "🔻", "➡️", "⬅️", "⬆️", "⬇️", "↔️", "↕️", "🔥", "💯"],
  },
];

type Props = {
  open: boolean;
  value: string;
  onClose: () => void;
  onConfirm: (emoji: string) => void;
};

export function EmojiPicker({ open, value, onClose, onConfirm }: Props) {
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(value || "📁");

  const groups = useMemo(() => {
    const kw = q.trim().toLowerCase();
    if (!kw) return GROUPS;
    // 简单关键字过滤：支持 emoji 名称与中文标签近似匹配
    const kwMap: Record<string, string[]> = {
      "文件夹": ["📁"], "喇叭": ["📢", "🔊"], "机器人": ["🤖", "👾"], "灯泡": ["💡"],
      "问": ["❓", "❗"], "新闻": ["📰"], "工具": ["🔧", "🛠️", "⚙️"], "火箭": ["🚀"],
      "电脑": ["💻", "🖥️"], "代码": ["⌨️", "💾"], "云": ["☁️"], "锁": ["🔒"],
      "数据库": ["🗄️"], "脑": ["🧠"], "实验": ["🧪", "🔬"], "星": ["⭐", "✨"],
      "杯": ["☕", "🍵"], "音乐": ["🎧", "🎵"], "游戏": ["🎮"], "目标": ["🎯"],
      "奖": ["🏆"], "庆祝": ["🎉", "🎊"], "天气": ["🌤️", "🌧️"], "城市": ["🏙️"],
      "飞机": ["✈️"], "相机": ["📷"], "画": ["🎨"], "时间": ["⏰", "⏳"],
      "文件": ["📑", "📎", "🖇️"], "日历": ["📅", "📆"], "邮箱": ["✉️", "📧", "📮"],
      "电话": ["☎️", "📞"], "包": ["💼", "🧳"], "人": ["👥", "🗣️", "🤝"],
      "对": ["✅"], "错": ["❌"], "警告": ["⚠️"], "禁止": ["🚫"], "点": ["🔴", "🔵", "🟢", "🟡", "🟣", "🟠", "⚪", "⚫"],
      "箭头": ["➡️", "⬅️", "⬆️", "⬇️", "↔️", "↕️"], "火": ["🔥"], "百": ["💯"],
    };
    const hits = new Set<string>();
    for (const [k, arr] of Object.entries(kwMap)) {
      if (kw.includes(k)) arr.forEach((e) => hits.add(e));
    }
    if (hits.size === 0) {
      // 直接按 emoji 字符包含匹配（如用户输入一个 emoji 或它的字形）
      GROUPS.forEach((g) => g.emojis.forEach((e) => { if (e.includes(kw)) hits.add(e); }));
    }
    if (hits.size === 0) return [];
    return [{ name: "搜索结果", emojis: Array.from(hits) }];
  }, [q]);

  return (
    <Modal open={open} title="选择图标" width={520} onClose={onClose}>
      <div className="space-y-3">
        <div className="flex gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="搜索图标（如：机器人、云、数据库）"
            autoFocus
            className="flex-1 rounded border border-[#d0d7de] px-2 py-1.5 text-sm outline-none focus:border-[#0969da]"
          />
        </div>

        <div className="max-h-[360px] space-y-4 overflow-y-auto pr-1">
          {groups.length === 0 && <div className="py-10 text-center text-[13px] text-[#656d76]">无匹配图标</div>}
          {groups.map((g) => (
            <div key={g.name}>
              <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-[#656d76]">{g.name}</div>
              <div className="grid grid-cols-8 gap-1">
                {g.emojis.map((e) => (
                  <button
                    key={e}
                    type="button"
                    onClick={() => setSel(e)}
                    className={`flex h-10 items-center justify-center rounded-md border text-[20px] transition ${
                      sel === e ? "border-[#0969da] bg-[#0969da]/10" : "border-transparent hover:border-[#d0d7de] hover:bg-[#f6f8fa]"
                    }`}
                    title={e}
                  >
                    {e}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="flex items-center justify-between border-t border-[#d0d7de] pt-3">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-[#656d76]">当前选择：</span>
            <span className="flex h-8 w-8 items-center justify-center rounded-md border border-[#d0d7de] bg-[#f6f8fa] text-[18px]">{sel}</span>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={onClose} className="rounded-md border border-[#d0d7de] px-4 py-1.5 text-[13px] hover:bg-[#f3f4f6]">
              取消
            </button>
            <button
              type="button"
              onClick={() => onConfirm(sel)}
              className="rounded-md bg-[#0969da] px-4 py-1.5 text-[13px] text-white hover:bg-[#0550ae]"
            >
              确认
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
