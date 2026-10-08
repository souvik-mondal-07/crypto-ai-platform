import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { NewsCard } from "./NewsCard";
import { buildArticle } from "../../test-fixtures/news";

function renderCard(props: Parameters<typeof NewsCard>[0]) {
  return render(
    <MemoryRouter>
      <NewsCard {...props} />
    </MemoryRouter>
  );
}

describe("NewsCard", () => {
  it("links the headline to the original article in a new tab, safely", () => {
    renderCard({ article: buildArticle({ source_url: "https://publisher.example/original" }) });
    const link = screen.getByRole("link", { name: /test headline one/i });
    expect(link).toHaveAttribute("href", "https://publisher.example/original");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("shows source, published time, summary and related coins linking to Coin Details", () => {
    renderCard({
      article: buildArticle({
        related_coins: [{ coin_id: "abc", symbol: "BTC", name: "Bitcoin", logo_url: null }],
      }),
    });
    expect(screen.getByText("Example Publisher")).toBeInTheDocument();
    expect(screen.getByText("Test summary one.")).toBeInTheDocument();
    expect(screen.getByText(/ago|just now/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "BTC" })).toHaveAttribute("href", "/coins/abc");
  });

  it("shows a sentiment indicator only when the article has been analyzed", () => {
    const { rerender } = renderCard({ article: buildArticle() });
    expect(screen.queryByText(/positive|negative|neutral/i)).not.toBeInTheDocument();
    rerender(
      <MemoryRouter>
        <NewsCard
          article={buildArticle({
            sentiment: { label: "negative", score: -0.7, confidence: 0.8, probabilities: {}, model: "m", analyzed_at: "2026-10-01T00:00:00Z" },
          })}
        />
      </MemoryRouter>
    );
    expect(screen.getByText("Negative")).toBeInTheDocument();
  });

  it("renders an image only when the provider supplied one, and drops it if it fails to load", () => {
    const { container, rerender } = renderCard({ article: buildArticle() });
    expect(container.querySelector("img")).toBeNull();
    rerender(
      <MemoryRouter>
        <NewsCard article={buildArticle({ image_url: "https://img.example/a.jpg" })} />
      </MemoryRouter>
    );
    const img = container.querySelector("img")!;
    expect(img).toHaveAttribute("src", "https://img.example/a.jpg");
    fireEvent.error(img);
    expect(container.querySelector("img")).toBeNull();
  });

  it("compact mode hides the summary and image; showCoins=false hides coin chips", () => {
    renderCard({
      article: buildArticle({
        image_url: "https://img.example/a.jpg",
        related_coins: [{ coin_id: "abc", symbol: "BTC", name: null, logo_url: null }],
      }),
      compact: true,
      showCoins: false,
    });
    expect(screen.queryByText("Test summary one.")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "BTC" })).not.toBeInTheDocument();
  });

  it("uses theme-aware classes (light and dark variants) for text and surfaces", () => {
    const { container } = renderCard({ article: buildArticle() });
    const html = container.innerHTML;
    expect(html).toMatch(/bg-white/);
    expect(html).toMatch(/dark:bg-slate-900/);
    expect(html).toMatch(/dark:text-slate-100/);
  });
});
