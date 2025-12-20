import fs from "fs";
import path from "path";
import Link from "next/link";

//export const dynamic = "force-static";
//export const dynamicParams = false;

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

  const files = fs
    .readdirSync(dataDir)
    .filter((file) => file.endsWith(".json"))
    .filter((file) => file !== "index.json");

  return files.map((file) => ({
    date: file.replace(".json", ""),
  }));
}

export default async function ArchivePage({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date } = await params;

  const filePath = path.join(process.cwd(), "data", `${date}.json`);
  const news: NewsFile = JSON.parse(fs.readFileSync(filePath, "utf-8"));

  return (
    <main style={{ padding: "2rem", maxWidth: 900, margin: "auto" }}>
      <p style={{ marginBottom: "1.5rem" }}>
        <Link href="/" style={{ color: "#3366cc" }}>
          ← Back to latest
        </Link>
      </p>
      <h1>Kids News</h1>

      {news.stories.map((story) => (
        <article key={story.id} style={{ marginBottom: "3rem" }}>
          <h2>{story.title}</h2>

          <p style={{ color: "#555", fontSize: "0.9rem" }}>
            {story.date_line} · {story.location}
          </p>

          {story.section.map((para, i) => (
            <p key={i} style={{ fontSize: "1.15rem", lineHeight: "1.7" }}>
              {para}
            </p>
          ))}

          <p
            style={{
              background: "#f5f7ff",
              padding: "1rem",
              borderRadius: "8px",
            }}
          >
            <strong>Why it matters:</strong> {story.why_it_matters}
          </p>
        </article>
      ))}
    </main>
  );
}
