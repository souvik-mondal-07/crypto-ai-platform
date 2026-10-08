import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";

import { PageContainer } from "../components/layout/PageContainer";
import { Loader } from "../components/common/Loader";
import { ErrorMessage } from "../components/common/ErrorMessage";
import { EmptyState } from "../components/common/EmptyState";
import { fetchCoins, searchCoins } from "../services/api/coins.api";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import type { Coin } from "../types/coin";

const PAGE_SIZE = 25;

/**
 * Development-only page proving the frontend can consume real
 * backend market data — NOT the final Markets page. No hard-coded
 * coins anywhere: every list below comes from a live API call, and a
 * failed/empty response is shown as such rather than falling back to
 * sample data.
 */
export function MarketTest() {
  const [searchInput, setSearchInput] = useState("");
  const debouncedSearch = useDebouncedValue(searchInput, 350);

  const [page, setPage] = useState(1);
  const [coins, setCoins] = useState<Coin[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [totalPages, setTotalPages] = useState(1);

  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const isSearching = debouncedSearch.trim().length > 0;

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setStatus("loading");
      setErrorMessage(null);
      try {
        if (isSearching) {
          const result = await searchCoins(debouncedSearch.trim());
          if (cancelled) return;
          setCoins(result.items);
          setTotal(result.count);
          setTotalPages(1);
        } else {
          const result = await fetchCoins({ page, limit: PAGE_SIZE });
          if (cancelled) return;
          setCoins(result.items);
          setTotal(result.total);
          setTotalPages(result.pages);
        }
        if (!cancelled) setStatus("success");
      } catch (error) {
        if (cancelled) return;
        setErrorMessage(error instanceof Error ? error.message : "Failed to load market data.");
        setStatus("error");
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [page, debouncedSearch, isSearching]);

  return (
    <PageContainer>
      <h1 className="text-2xl font-bold text-slate-900">Market Data — Test Page</h1>
      <p className="mt-1 text-sm text-slate-500">
        Development page verifying the coin/market API. This is not the
        final Markets page.
      </p>

      <div className="mt-6 flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <Search className="h-4 w-4 text-slate-400" aria-hidden="true" />
        <input
          type="text"
          value={searchInput}
          onChange={(event) => {
            setSearchInput(event.target.value);
            setPage(1);
          }}
          placeholder="Search coins by name or symbol (e.g. bitcoin, ETH)..."
          className="w-full bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400 dark:text-slate-100"
        />
      </div>

      <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
        <span>
          {total !== null
            ? `${total.toLocaleString()} coin${total === 1 ? "" : "s"} ${isSearching ? "matched" : "available"}`
            : " "}
        </span>
        {!isSearching && status === "success" && totalPages > 1 && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="rounded p-1 disabled:opacity-30"
              aria-label="Previous page"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span>
              Page {page} of {totalPages}
            </span>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="rounded p-1 disabled:opacity-30"
              aria-label="Next page"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>

      <div className="mt-3 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
        {status === "loading" && <Loader label={isSearching ? "Searching..." : "Loading coins..."} />}

        {status === "error" && errorMessage && (
          <div className="p-4">
            <ErrorMessage message={errorMessage} />
          </div>
        )}

        {status === "success" && coins.length === 0 && (
          <EmptyState
            message={
              isSearching
                ? `No coins matched "${debouncedSearch.trim()}".`
                : "No market data available."
            }
          />
        )}

        {status === "success" && coins.length > 0 && (
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-100 text-xs uppercase text-slate-400">
              <tr>
                <th className="px-4 py-2 font-medium">Rank</th>
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Symbol</th>
              </tr>
            </thead>
            <tbody>
              {coins.map((coin) => (
                <tr key={coin.id} className="border-b border-slate-50 last:border-0">
                  <td className="px-4 py-2 text-slate-500">{coin.market_cap_rank ?? "—"}</td>
                  <td className="px-4 py-2 font-medium text-slate-800">{coin.name}</td>
                  <td className="px-4 py-2 text-slate-500">{coin.symbol}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </PageContainer>
  );
}
