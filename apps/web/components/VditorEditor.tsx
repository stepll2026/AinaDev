"use client";

/** Vditor 编辑器封装：工具栏 + 附件/图片上传（上传到 /api/uploads，需登录鉴权）。 */

import { useEffect, useRef } from "react";
import { getToken } from "@/lib/api";

type Props = {
  value?: string;
  onChange?: (md: string) => void;
  placeholder?: string;
  height?: number;
  toolbarConfig?: object;
  cacheId?: string; // 传则启用本地草稿缓存 key
};

export function VditorEditor({ value = "", onChange, placeholder = "内容…", height = 360, toolbarConfig, cacheId }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const vditorRef = useRef<any>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    let disposed = false;
    let timer: any = null;

    const init = async () => {
      // 动态加载 Vditor（浏览器环境），避免 SSR
      const Vditor = (await import("vditor")).default;
      if (disposed || !ref.current) return;
      const token = getToken();

      const toolbar = [
        "headings", "bold", "italic", "strike", "|",
        "list", "ordered-list", "check", "outdent", "indent", "|",
        "quote", "line", "code", "inline-code", "insert-before", "insert-after", "|",
        "table", "link", "emoji", "|",
        "upload", "|",
        "undo", "redo", "|",
        "fullscreen", "edit-mode", "both",
      ];

      const ed = new Vditor(ref.current, {
        value: value || "",
        mode: "ir",
        placeholder,
        height,
        // 静态资源自托管（public/vditor），避免依赖外网 unpkg CDN（内网/受限网络下会 404）
        cdn: "/vditor",
        cache: cacheId ? { enable: true, id: cacheId } : { enable: false },
        toolbar,
        toolbarConfig,
        upload: {
          url: "/api/uploads",
          fieldName: "file",
          max: 10 * 1024 * 1024,
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          // 后端返回 {url,name,size,type} → 转成 Vditor 期望的 JSON 字符串
          format: (files: File[], responseText: string) => {
            try {
              const data = JSON.parse(responseText);
              if (data.url) {
                const succMap: Record<string, string> = {};
                succMap[data.name || files?.[0]?.name || "file"] = data.url;
                return JSON.stringify({ msg: "", code: 0, data: { errFiles: [], succMap } });
              }
              return JSON.stringify({ msg: "上传失败", code: 1, data: { errFiles: [], succMap: {} } });
            } catch {
              return JSON.stringify({ msg: "上传响应解析失败", code: 1, data: { errFiles: [], succMap: {} } });
            }
          },
        },
        input: (md: string) => {
          onChangeRef.current?.(md);
        },
        after: () => {
          vditorRef.current = ed;
        },
      });
    };

    // 小延迟确保 DOM 挂载（Next.js 客户端渲染时序）
    timer = setTimeout(init, 50);
    return () => {
      disposed = true;
      clearTimeout(timer);
      try {
        vditorRef.current?.destroy();
      } catch {
        /* ignore */
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <div ref={ref} />;
}

/** 外部调用：读取 Markdown 内容 */
export function getVditorValue(ref: any): string {
  try {
    return ref?.getValue() || "";
  } catch {
    return "";
  }
}
