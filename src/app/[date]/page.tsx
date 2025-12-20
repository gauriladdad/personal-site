import fs from "fs";
import path from "path";
import * as Accordion from "@radix-ui/react-accordion";
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

export default function ArchivePage({ params }: { params: { date: string } }) {
  const dataDir = path.join(process.cwd(), "data");
  const { date } = params;

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
    <main className="mx-auto max-w-6xl px-6 py-12 grid grid-cols-1 lg:grid-cols-[1fr_260px] gap-12">
      {/* CONTENT */}
      <section>
        <Link
          href="/"
          className="inline-block mb-6 text-sm text-accent hover:underline"
        >
          ← Back to latest
        </Link>

        <Accordion.Root
          type="single"
          collapsible
          className="border-t border-border"
        >
          {news.stories.map((story) => (
            <Accordion.Item
              key={story.id}
              value={String(story.id)}
              className="border-b border-border"
            >
              <Accordion.Header>
                <Accordion.Trigger className="w-full text-left py-5 focus:outline-none">
                  <div className="text-xl font-semibold">{story.title}</div>
                  <div className="text-sm text-muted mt-1">
                    {story.date_line} · {story.location}
                  </div>
                </Accordion.Trigger>
              </Accordion.Header>

              <Accordion.Content className="pb-8">
                {story.section.map((para, i) => (
                  <p key={i} className="text-base leading-relaxed mt-5">
                    {para}
                  </p>
                ))}

                <div className="mt-8 rounded-xl bg-card border border-border p-5">
                  <div className="font-semibold text-accent mb-1">
                    Why it matters
                  </div>
                  <div className="text-base leading-relaxed">
                    {story.why_it_matters}
                  </div>
                </div>
              </Accordion.Content>
            </Accordion.Item>
          ))}
        </Accordion.Root>
      </section>

      {/* SIDEBAR */}
      <aside className="border-l border-border pl-6">
        <h3 className="font-semibold mb-4">Other Editions</h3>
        <ul className="space-y-2 text-sm">
          {archiveDates.map((d) => (
            <li key={d}>
              <Link href={`/${d}/`} className="text-accent hover:underline">
                {d}
              </Link>
            </li>
          ))}
        </ul>
      </aside>
    </main>
  );
}
