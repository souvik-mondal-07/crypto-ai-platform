/**
 * Helpers for rendering third-party (provider) text and URLs safely.
 * Provider descriptions arrive as HTML fragments and URL lists can
 * contain arbitrary strings, so neither is ever injected into the page
 * as markup or used as an href without passing through here.
 */

/**
 * Reduce an HTML fragment to plain text. Parsed with DOMParser (an
 * inert document — scripts never run and nothing is attached to the
 * live page) and read back via textContent, so no markup can survive.
 * The result is rendered as a normal React text node.
 */
export function htmlToPlainText(html: string | null | undefined): string {
  if (!html) return "";
  let text: string;
  if (typeof DOMParser !== "undefined") {
    const doc = new DOMParser().parseFromString(html, "text/html");
    // textContent would otherwise include the source text of these elements.
    doc.querySelectorAll("script, style").forEach((node) => node.remove());
    text = doc.body.textContent ?? "";
  } else {
    text = html.replace(/<[^>]*>/g, "");
  }
  return text.replace(/\r\n/g, "\n").replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n").trim();
}

/** Returns the URL only if it is a well-formed http(s) URL; otherwise null (e.g. `javascript:`). */
export function safeHttpUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url.trim());
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.toString() : null;
  } catch {
    return null;
  }
}

/** Display label for a link: the hostname without a leading "www.". Falls back to the raw text. */
export function linkLabel(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/** Shorten a long identifier (e.g. a contract address) in the middle, keeping both ends readable. */
export function truncateMiddle(value: string, head = 8, tail = 6): string {
  if (value.length <= head + tail + 1) return value;
  return `${value.slice(0, head)}…${value.slice(-tail)}`;
}

const HANDLE = /^[A-Za-z0-9_]{1,30}$/;

/** Link for a social handle, only if the handle is a plain identifier (never built from arbitrary text). */
export function socialProfileUrl(base: "https://x.com/" | "https://t.me/", handle: string | null | undefined): string | null {
  if (!handle || !HANDLE.test(handle)) return null;
  return `${base}${handle}`;
}
