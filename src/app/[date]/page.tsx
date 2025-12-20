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

  const archiveDates = fs
    .readdirSync(dataDir)
    .filter((f) => f.endsWith(".json"))
    .filter((f) => f !== "index.json")
    .map((f) => f.replace(".json", ""))
    .filter((d) => d !== date)
    .sort()
    .reverse();

  return (
    <main className="layout">
      <section className="content">
        <Link href="/">Back to latest</Link>

        {news.stories.map((story) => (
          <article key={story.id} className="story">
            <h2 className="story-title">{story.title}</h2>

            <div className="story-meta">
              {story.date_line} · {story.location}
            </div>

            {story.section.map((para, i) => (
              <p key={i}>{para}</p>
            ))}

            <div className="story-why">
              <span>Why it matters</span>
              {story.why_it_matters}
            </div>
          </article>
        ))}
      </section>

      <aside className="sidebar">
        <div className="archive">
          <h3>Other Editions</h3>
          <ul>
            {archiveDates.map((d) => (
              <li key={d}>
                <a href={`/${d}/`}>{d}</a>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </main>
  );
}
