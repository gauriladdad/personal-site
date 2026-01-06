import fs from "fs";
import path from "path";
import Link from "next/link";

type Story = {
  id: number;
  title: string;
  date_line: string;
  location: string;
  section: string[];
  why_it_matters: string;
};

type NewsFile = {
  stories: Story[];
};

export default async function HomePage({
  params,
}: {
  params?: Promise<Record<string, string>>;
}) {
  await params;
  const dataDir = path.join(process.cwd(), "data");

  const index = JSON.parse(
    fs.readFileSync(path.join(dataDir, "index.json"), "utf-8")
  );
  const latestDate = index.latest;

  const news: NewsFile = JSON.parse(
    fs.readFileSync(path.join(dataDir, `${latestDate}.json`), "utf-8")
  );

  const archiveDates = fs
    .readdirSync(dataDir)
    .filter((f) => f.endsWith(".json"))
    .filter((f) => f !== "index.json")
    .map((f) => f.replace(".json", ""))
    .filter((d) => d !== latestDate)
    .sort()
    .reverse()
    .slice(0, 5);

  return (
    <main className="mx-auto max-w-[65ch] px-6 py-10">
      {/* Header */}
      <header className="mb-10 pb-6 border-b border-border/60">
        <h1 className="text-3xl font-semibold mb-3">Kids News & Activities</h1>
        <p className="text-sm text-muted dark:text-muted-dark dark:text-muted dark:text-muted-dark-dark">
          Calm, friendly stories for kids aged 6–9 · Updated daily
        </p>
      </header>

      {/* Stories */}
      <section className="space-y-4">
        {news.stories.map((story, index) => (
          <article key={story.id}>
            {index > 0 && (
              <hr className="my-8 border-border/80 dark:border-border/60" />
            )}
            <h2 className="text-2xl font-semibold mb-2">{story.title}</h2>

            <p className="text-sm text-muted dark:text-muted-dark mb-8">
              <span className="font-medium text-accent dark:text-accent-dark">
                Today
              </span>
              {" · "}
              {story.location}
            </p>

            <div className="space-y-3">
              {story.section.map((para, i) => (
                <p key={i} className="font-serif text-[1.05rem] leading-6">
                  {para}
                </p>
              ))}
            </div>

            <div className="mt-6 pl-4 border-l-2 border-accent/30 dark:border-accent-dark/30">
              <p className="text-sm leading-6">
                <span className="font-medium text-accent dark:text-accent-dark">
                  Why it matters:{" "}
                </span>
                {story.why_it_matters}
              </p>
            </div>
          </article>
        ))}
      </section>

      {/* Archives */}
      {archiveDates.length > 0 && (
        <footer className="mt-4 pt-8 border-t border-border">
          <h3 className="text-sm font-medium mb-3 text-muted dark:text-muted-dark">
            Past days
          </h3>
          <ul className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
            {archiveDates.map((date) => (
              <li key={date}>
                <Link
                  href={`/${date}/`}
                  className="text-accent dark:text-accent-dark hover:underline"
                >
                  {date}
                </Link>
              </li>
            ))}
          </ul>
        </footer>
      )}
    </main>
  );
}
