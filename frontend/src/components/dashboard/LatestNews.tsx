import { Link } from "react-router-dom";

import { useNewsList } from "../../hooks/useNewsList";
import { EmptyState } from "../common/EmptyState";
import { Loader } from "../common/Loader";
import { RetryError } from "../common/RetryError";
import { SectionHeading } from "../common/SectionHeading";
import { NewsCard } from "../news/NewsCard";

const QUERY = { page: 1, limit: 5 };

/** Dashboard "Market News": the five newest real articles, with a link to the full News page. */
export function LatestNews() {
  const { data, loading, error, retry } = useNewsList(QUERY);
  return (
    <section aria-labelledby="market-news-heading">
      <SectionHeading
        id="market-news-heading"
        title="Market News"
        actions={
          <Link to="/news" className="text-xs font-medium text-sky-700 hover:underline dark:text-sky-400">
            All news
          </Link>
        }
      />
      {loading && <Loader label="Loading news..." />}
      {error && !data && <RetryError compact message={error.message} onRetry={retry} />}
      {data && data.items.length === 0 && !error && <EmptyState message="No news articles are stored yet." />}
      {data && data.items.length > 0 && (
        <ul className="space-y-2">
          {data.items.map((article) => (
            <li key={article.news_id}>
              <NewsCard article={article} compact />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
