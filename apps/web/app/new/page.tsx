"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { http } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { MarkdownView } from "@/components/ui";
import { AttachmentUploader, type AttachmentItem } from "@/components/AttachmentUploader";

export default function NewPostPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [cats, setCats] = useState<any[]>([]);
  const [categoryId, setCategoryId] = useState<number>(0);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [postType, setPostType] = useState("discussion");
  const [atAi, setAtAi] = useState(true);
  const [preview, setPreview] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [attachments, setAttachments] = useState<AttachmentItem[]>([]);

  useEffect(() => {
    if (!user) {
      router.push("/login");
      return;
    }
    http.get("/categories").then((d) => {
      setCats(d);
      if (d.length) setCategoryId(d[0].id);
    });
    const draft = localStorage.getItem("post_draft");
    if (draft) {
      try {
        const d = JSON.parse(draft);
        setTitle(d.title || "");
        setBody(d.body || "");
      } catch {
        /* ignore */
      }
    }
  }, [user, router]);

  useEffect(() => {
    if (title || body) {
      localStorage.setItem("post_draft", JSON.stringify({ title, body }));
    }
  }, [title, body]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!categoryId) return setError("请选择栏目");
    setLoading(true);
    try {
      const post = await http.post("/posts", { category_id: Number(categoryId), title, body_md: body, post_type: postType, at_ai: atAi, attachments });
      localStorage.removeItem("post_draft");
      router.push(`/post/${post.id}`);
    } catch (err: any) {
      setError(err.message || "发帖失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-[920px] px-4 py-6">
      <h1 className="mb-4 text-[28px] font-semibold text-[#24292f]">发帖</h1>
      <form onSubmit={submit} className="space-y-4">
        <div className="flex gap-3">
          <select value={categoryId} onChange={(e) => setCategoryId(Number(e.target.value))} className="rounded-md border border-[#d0d7de] bg-white px-3 py-2 text-sm outline-none focus:border-[#0969da]">
            {cats.map((c) => (
              <option key={c.id} value={c.id} disabled={!c.allow_post}>
                {c.icon} {c.name}
              </option>
            ))}
          </select>
          <select value={postType} onChange={(e) => setPostType(e.target.value)} className="rounded-md border border-[#d0d7de] bg-white px-3 py-2 text-sm outline-none">
            <option value="discussion">讨论</option>
            <option value="question">问答</option>
          </select>
          <label className="flex items-center gap-2 text-sm text-[#656d76]">
            <input type="checkbox" checked={atAi} onChange={(e) => setAtAi(e.target.checked)} />
            @ 栏目 AI 管理员
          </label>
        </div>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="标题"
          required
          className="w-full rounded-md border border-[#d0d7de] px-4 py-3 text-[20px] font-medium outline-none focus:border-[#0969da]"
        />
        <div className="rounded-lg border border-[#d0d7de] bg-white">
          <div className="flex items-center justify-between border-b border-[#d0d7de] px-3 py-2">
            <span className="text-[12px] text-[#656d76]">支持 Markdown 语法</span>
            <button type="button" onClick={() => setPreview(!preview)} className="rounded bg-[#eaeef2] px-2 py-1 text-[12px] text-[#656d76] hover:bg-[#d0d7de]">
              {preview ? "编辑" : "预览"}
            </button>
          </div>
          {preview ? (
            <div className="min-h-[320px] px-4 py-3">
              <MarkdownView content={body || "*（预览区）*"} />
            </div>
          ) : (
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="正文内容…（支持 Markdown、代码块、表格）"
              required
              className="min-h-[320px] w-full resize-y px-4 py-3 font-mono text-[14px] outline-none"
            />
          )}
        </div>
        <div className="rounded-lg border border-[#d0d7de] bg-white px-3 py-3">
          <AttachmentUploader attachments={attachments} onChange={setAttachments} />
        </div>
        {error && <div className="rounded-md bg-[#ffebe9] px-3 py-2 text-[13px] text-[#cf222e]">{error}</div>}
        <div className="flex items-center gap-3">
          <button disabled={loading} className="rounded-md bg-[#0969da] px-5 py-2 text-sm font-medium text-white hover:bg-[#0550ae] disabled:opacity-60">
            {loading ? "发布中…" : "发布"}
          </button>
          <span className="text-[12px] text-[#656d76]">发布后 AI 将自动进行合规审查；@ AI 管理员时若知识库有证据会自动回复</span>
        </div>
      </form>
    </div>
  );
}
