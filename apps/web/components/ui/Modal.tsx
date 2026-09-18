"use client";

/** 通用模态弹窗：白色磨砂玻璃遮罩 + 居中卡片。 */

import { useEffect } from "react";

type Props = {
  open: boolean;
  title: string;
  width?: number;
  onClose: () => void;
  children: React.ReactNode;
};

export function Modal({ open, title, width = 640, onClose, children }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-white/60 p-4 backdrop-blur-md"
      onClick={onClose}
    >
      <div
        className="max-h-[85vh] w-full overflow-y-auto rounded-xl border border-white/60 bg-white p-6 shadow-2xl shadow-black/10"
        style={{ maxWidth: width }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-[16px] font-semibold text-[#24292f]">{title}</h3>
          <button
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-md text-[#656d76] hover:bg-[#eaeef2] hover:text-[#24292f]"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
