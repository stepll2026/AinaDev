"use client";

/** ByteMD 编辑器封装：工具栏（图片/附件上传到 /api/uploads，需登录鉴权），完全本地化（npm 打包，无 CDN 依赖）。 */

import { useMemo } from "react";
import { Editor } from "@bytemd/react";
import gfm from "@bytemd/plugin-gfm";
import highlight from "@bytemd/plugin-highlight";
import zh_Hans from "bytemd/locales/zh_Hans.json";
import gfmZh from "@bytemd/plugin-gfm/locales/zh_Hans.json";
import "bytemd/dist/index.css";
import { http } from "@/lib/api";

type Props = {
  value?: string;
  onChange?: (md: string) => void;
  placeholder?: string;
  height?: number;
  toolbarConfig?: object; // 兼容旧编辑器接口，ByteMD 无需
  cacheId?: string; // 兼容旧接口；页面已自行处理草稿缓存
};

/** 上传单个文件到 /api/uploads，返回后端元数据。 */
async function uploadFile(file: File): Promise<{ url: string; name: string; size: number; type: string }> {
  const fd = new FormData();
  fd.append("file", file);
  return http.upload<{ url: string; name: string; size: number; type: string }>("/uploads", fd);
}

const IMAGE_EXT = new Set(["png", "jpg", "jpeg", "gif", "webp", "bmp"]);

export function BytemdEditor({ value = "", onChange, placeholder = "内容…", height = 360, cacheId }: Props) {
  // 插件实例保持稳定，避免每次渲染重建导致 @bytemd/react $set 抖动
  const plugins = useMemo(
    () => [
      gfm({ locale: gfmZh }),
      highlight(),
      {
        actions: [
          {
            type: "action" as const,
            title: "上传附件",
            icon: '<svg viewBox="0 0 16 16" width="16" height="16"><path fill="currentColor" d="M8.5 1.5a2.5 2.5 0 0 1 5 0V9a4 4 0 0 1-8 0V3.5a.75.75 0 0 1 1.5 0V9a2.5 2.5 0 0 0 5 0V1.5a1 1 0 0 0-2 0V8a.75.75 0 0 1-1.5 0V1.5Z"/><path fill="currentColor" d="M2 6.25a.75.75 0 0 1 1.5 0v2.75a4.5 4.5 0 0 0 9 0V6.25a.75.75 0 0 1 1.5 0v2.75a6 6 0 0 1-12 0V6.25Z"/></svg>',
            click: async (ctx: any) => {
              // 用隐藏 input 选择文件，上传后在光标处插入 Markdown 链接
              const input = document.createElement("input");
              input.type = "file";
              input.accept = ".pdf,.doc,.docx,.xls,.xlsx,.txt,.md,.csv,.zip,.png,.jpg,.jpeg,.gif,.webp";
              input.onchange = async () => {
                const file = input.files?.[0];
                if (!file) return;
                try {
                  const r = await uploadFile(file);
                  const editor = ctx.editor;
                  if (editor) {
                    const text = IMAGE_EXT.has(file.name.split(".").pop()?.toLowerCase() || "")
                      ? `![${file.name}](${r.url})`
                      : `[${file.name}](${r.url})`;
                    editor.replaceSelection(text);
                  }
                } catch (e: any) {
                  alert(e.message || "上传失败");
                }
              };
              input.click();
            },
          },
        ],
      },
    ],
    []
  );

  return (
    <div style={{ height }} className="bytemd-wrap overflow-hidden rounded-lg">
      <style>{`.bytemd-wrap > div { height: 100%; } .bytemd-wrap .bytemd { height: 100% !important; } .bytemd-wrap .bytemd-body { height: calc(100% - 58px); }`}</style>
      <Editor
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        mode="split"
        plugins={plugins}
        locale={zh_Hans}
        uploadImages={async (files: File[]) => {
          const results = [];
          for (const f of files) {
            try {
              const r = await uploadFile(f);
              results.push({ url: r.url, alt: f.name, title: f.name });
            } catch {
              /* 单文件失败跳过，其余继续 */
            }
          }
          return results;
        }}
      />
    </div>
  );
}
