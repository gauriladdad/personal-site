import newsData from "../../data/news.json";

type Story = {
  id: number;
  title: string;
  date_line: string;
  location: string;
  section: string[];
  why_it_matters: string;
};

export default function Home() {
  const stories: Story[] = newsData.stories;

  return (
    <main
      style={{
        padding: "2rem",
        maxWidth: 900,
        margin: "auto",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      <h1>Kids News & Activities</h1>

      {stories.map((story) => (
        <article
          key={story.id}
          style={{
            marginBottom: "3rem",
            paddingBottom: "2rem",
            borderBottom: "1px solid #eee",
          }}
        >
          <h2>{story.title}</h2>

          <p style={{ fontSize: "0.9rem", color: "#555" }}>
            {story.date_line} · {story.location}
          </p>

          {/* Main story paragraphs */}
          {story.section.map((para, index) => (
            <p
              key={index}
              style={{
                lineHeight: "1.6",
                fontSize: "1.05rem",
                marginTop: "1rem",
              }}
            >
              {para}
            </p>
          ))}

          {/* Why it matters */}
          <p
            style={{
              marginTop: "1.2rem",
              padding: "0.75rem",
              background: "#f5f7ff",
              borderRadius: "6px",
              fontSize: "0.95rem",
            }}
          >
            <strong>Why it matters:</strong> {story.why_it_matters}
          </p>
        </article>
      ))}
    </main>
  );
}
