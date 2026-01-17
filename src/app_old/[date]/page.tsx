import fs from "fs";
import path from "path";
import Link from "next/link";

export const dynamic = "force-static";
export const dynamicParams = false;

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

export function generateStaticParams() {
  const dataDir = path.join(process.cwd(), "data");

  return fs
    .readdirSync(dataDir)
    .filter((f) => f.endsWith(".json"))
    .filter((f) => f !== "index.json")
    .map((f) => ({
      date: f.replace(".json", ""),
    }));
}

export default async function ArchivePage({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date } = await params;
  const dataDir = path.join(process.cwd(), "data");

  const news: NewsFile = JSON.parse(
    fs.readFileSync(path.join(dataDir, `${date}.json`), "utf-8")
  );

  return (
    <main className="mx-auto max-w-[65ch] px-6 py-10">
      <header className="mb-10 pb-6 border-b border-border/60">
        <Link
          href="/"
          className="text-sm text-accent dark:text-accent-dark hover:underline"
        >
          ← Back to latest
        </Link>
      </header>

      <section className="space-y-3">
        {news.stories.map((story, index) => (
          <article key={story.id}>
            {index > 0 && (
              <hr className="my-8 border-border/80 dark:border-border/60" />
            )}
            <h2 className="text-2xl font-semibold mb-2">{story.title}</h2>
            <p className="text-sm text-muted dark:text-muted-dark mb-4">
              {story.date_line} · {story.location}
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
    </main>
  );
}
