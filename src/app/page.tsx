import fs from "fs";
import path from "path";

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

export default function HomePage() {
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
    .filter((date) => date !== latestDate)
    .sort()
    .reverse();

  return (
    <main className="layout">
      <section className="content">
        <h1>Kids News & Activities</h1>

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
          <h3>Past Editions</h3>
          <ul>
            {archiveDates.map((date) => (
              <li key={date}>
                <a href={`/${date}/`}>{date}</a>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </main>
  );
}
