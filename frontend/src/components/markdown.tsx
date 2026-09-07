import "katex/dist/katex.min.css";
import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import rehypeSlug from "rehype-slug";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { cn } from "@/lib/utils";

interface MarkdownProps {
  children: string;
  className?: string;
}

// The backend plants an `nxv:` comment in player-facing text; react-markdown
// renders raw HTML as literal text, so it is pulled out and re-rendered
// off-screen instead.
const CANARY = /\n*<!--\s*nxv:\s*(.*?)\s*-->/s;

const YOUTUBE = /^https?:\/\/(?:www\.)?(?:youtube\.com\/watch\?v=|youtu\.be\/)([\w-]{11})/;
const VIDEO_FILE = /\.(mp4|webm|mov)(\?|#|$)/i;
const AUDIO_FILE = /\.(mp3|wav|flac|ogg|m4a)(\?|#|$)/i;

function MarkdownLink({ href, children }: { href?: string; children?: ReactNode }) {
  const youtube = href?.match(YOUTUBE);
  if (youtube) {
    return (
      <iframe
        title="YouTube video"
        src={`https://www.youtube-nocookie.com/embed/${youtube[1]}`}
        allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowFullScreen
        className="aspect-video w-full rounded-lg border-0"
      />
    );
  }
  if (href && VIDEO_FILE.test(href)) {
    // biome-ignore lint/a11y/useMediaCaption: user-supplied video, no track available
    return <video src={href} controls className="w-full rounded-lg" />;
  }
  if (href && AUDIO_FILE.test(href)) {
    // biome-ignore lint/a11y/useMediaCaption: user-supplied audio, no track available
    return <audio src={href} controls className="w-full" />;
  }
  const external = href ? /^https?:\/\//.test(href) : false;
  return (
    <a
      href={href}
      target={external ? "_blank" : undefined}
      rel={external ? "noreferrer" : undefined}
    >
      {children}
    </a>
  );
}

export function Markdown({ children, className }: MarkdownProps) {
  const canary = children.match(CANARY);

  return (
    <div
      className={cn(
        "prose prose-sm dark:prose-invert max-w-none",
        "prose-p:my-1 prose-headings:mt-3 prose-headings:mb-1",
        // inline code — no backtick decorations, subtle bg
        "prose-code:before:content-none prose-code:after:content-none",
        "prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-code:font-mono",
        // fenced code blocks
        "prose-pre:bg-muted prose-pre:rounded-lg prose-pre:p-3 prose-pre:overflow-x-auto",
        "prose-blockquote:border-l-2 prose-blockquote:border-muted-foreground/30 prose-blockquote:pl-4 prose-blockquote:text-muted-foreground",
        "prose-a:text-primary prose-a:underline-offset-2",
        "prose-ul:my-1 prose-ol:my-1 prose-li:my-0",
        className,
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeSlug, rehypeHighlight, rehypeKatex]}
        components={{ a: MarkdownLink }}
      >
        {children.replace(CANARY, "")}
      </ReactMarkdown>
      {canary && (
        <span className="sr-only" aria-hidden="true">
          {canary[1]}
        </span>
      )}
    </div>
  );
}
