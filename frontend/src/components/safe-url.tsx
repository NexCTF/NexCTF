import { ExternalLink } from "lucide-react";
import type { ReactNode } from "react";
import type { Link } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Whether `href` is an http(s) URL, the only kind rendered as a link. */
export function isHttpUrl(href: string): boolean {
  return /^https?:\/\//i.test(href);
}

/** The host an http(s) URL points to, or null when it is not one. */
export function urlHostname(href: string): string | null {
  if (!isHttpUrl(href)) return null;
  try {
    return new URL(href).hostname;
  } catch {
    return null;
  }
}

/** Renders an http(s) URL as a link, anything else as plain text. */
export function SafeUrl({
  href,
  children,
  className,
}: {
  href: string;
  children: ReactNode;
  className?: string;
}) {
  if (!isHttpUrl(href)) return children;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={cn("text-link hover:underline underline-offset-2", className)}
    >
      {children}
    </a>
  );
}

/** A player-supplied link, with the host it really leads to next to its label. */
export function PlayerLink({ link, className }: { link: Link; className?: string }) {
  const hostname = urlHostname(link.url);
  if (hostname === null) {
    return (
      <span className={className}>{link.label ? `${link.label} (${link.url})` : link.url}</span>
    );
  }
  return (
    <SafeUrl href={link.url} className={cn("inline-flex items-center gap-1", className)}>
      {link.label || link.url}
      {link.label && <span className="text-muted-foreground">({hostname})</span>}
      <ExternalLink className="size-3 opacity-60" />
    </SafeUrl>
  );
}

/** A wrapping list of player-supplied links, each showing its real host. */
export function PlayerLinks({ links, className }: { links: Link[]; className?: string }) {
  return (
    <div className="flex flex-wrap gap-2">
      {links.map((link, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: display-only, never reorders
        <PlayerLink key={i} link={link} className={className} />
      ))}
    </div>
  );
}
