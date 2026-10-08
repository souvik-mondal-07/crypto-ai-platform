import { describe, expect, it } from "vitest";

import { htmlToPlainText, linkLabel, safeHttpUrl, socialProfileUrl, truncateMiddle } from "./providerText";

describe("htmlToPlainText", () => {
  it("strips tags and keeps the text", () => {
    expect(htmlToPlainText('A <a href="https://x.org">link</a> and <b>bold</b> text.')).toBe(
      "A link and bold text."
    );
  });

  it("never lets script content run or survive as markup", () => {
    const out = htmlToPlainText('Hello<script>window.__pwned = true</script><img src=x onerror="alert(1)">');
    expect(out).toBe("Hello");
    expect((window as unknown as { __pwned?: boolean }).__pwned).toBeUndefined();
  });

  it("decodes entities to text rather than markup", () => {
    expect(htmlToPlainText("Fish &amp; chips &lt;3")).toBe("Fish & chips <3");
  });

  it("collapses runs of blank lines and returns empty for null/empty input", () => {
    expect(htmlToPlainText("a\r\n\r\n\r\n\r\nb")).toBe("a\n\nb");
    expect(htmlToPlainText(null)).toBe("");
    expect(htmlToPlainText("")).toBe("");
  });
});

describe("safeHttpUrl", () => {
  it("accepts http and https", () => {
    expect(safeHttpUrl("https://example.org/a")).toBe("https://example.org/a");
    expect(safeHttpUrl("http://example.org")).toBe("http://example.org/");
  });

  it.each(["javascript:alert(1)", "data:text/html,hi", "ftp://example.org", "not a url", "", null, undefined])(
    "rejects %s",
    (value) => {
      expect(safeHttpUrl(value as string | null | undefined)).toBeNull();
    }
  );
});

describe("linkLabel / truncateMiddle / socialProfileUrl", () => {
  it("labels links by hostname without www", () => {
    expect(linkLabel("https://www.example.org/path")).toBe("example.org");
    expect(linkLabel("garbage")).toBe("garbage");
  });

  it("shortens long identifiers but leaves short ones alone", () => {
    expect(truncateMiddle("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2")).toBe("0xc02aaa…756cc2");
    expect(truncateMiddle("short")).toBe("short");
  });

  it("only builds social links from plain handles", () => {
    expect(socialProfileUrl("https://x.com/", "examplecoin")).toBe("https://x.com/examplecoin");
    expect(socialProfileUrl("https://t.me/", "a/b?x=1")).toBeNull();
    expect(socialProfileUrl("https://x.com/", null)).toBeNull();
  });
});
