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

type IndexFile = {
  latest: string;
};

export default function Home() {
  const dataDir = path.join(process.cwd(), "data");

  const index: IndexFile = JSON.parse(
    fs.readFileSync(path.join(dataDir, "index.json"), "utf-8")
  );

  const latestDate = index.latest;

  const archiveDates = fs
    .readdirSync(dataDir)
    .filter((file) => file.endsWith(".json"))
    .filter((file) => file !== "index.json")
    .map((file) => file.replace(".json", ""))
    .filter((date) => date !== latestDate)
    .sort()
    .reverse();

  const news: NewsFile = JSON.parse(
    fs.readFileSync(path.join(dataDir, `${latestDate}.json`), "utf-8")
  );
  return (
    <main style={{ padding: "2rem", maxWidth: 900, margin: "auto" }}>
      <h1>Kids News & Activities</h1>

      {news.stories.map((story) => (
        <article key={story.id} style={{ marginBottom: "3rem" }}>
          <h2>{story.title}</h2>

          <p
            style={{
              color: "#b5b5b5",
              fontSize: "0.95rem",
              marginTop: "0.25rem",
            }}
          >
            {story.date_line} · {story.location}
          </p>

          {/* THIS WAS MISSING */}
          {story.section.map((paragraph, index) => (
            <p
              key={index}
              style={{
                fontSize: "1.15rem",
                lineHeight: "1.8",
                marginTop: "1.25rem",
                color: "#eaeaea",
              }}
            >
              {paragraph}
            </p>
          ))}

          <p
            style={{
              background: "#1f2933",
              color: "#ffffff",
              padding: "1.25rem",
              borderRadius: "10px",
              marginTop: "2rem",
              fontSize: "1.05rem",
              lineHeight: "1.6",
            }}
          >
            <strong style={{ color: "#93c5fd" }}>Why it matters:</strong>{" "}
            {story.why_it_matters}
          </p>
        </article>
      ))}

      <hr style={{ margin: "3rem 0" }} />

      <h2>Past Editions</h2>

      <ul style={{ paddingLeft: "1.2rem" }}>
        {archiveDates.map((date) => (
          <li key={date} style={{ marginBottom: "0.5rem" }}>
            <Link href={`/${date}/`} style={{ color: "#3366cc" }}>
              {date}
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
