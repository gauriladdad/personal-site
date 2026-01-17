Today (manual JSON)

Data lives in repo

Build-time reading

Needs redeploy to update

With RSS + Lambda

Data lives in S3

Runtime fetching

## No redeploy needed

The system supports multiple content providers behind a single publishing contract. AI is optional and user-supplied.

(We designed the system around a single content contract.
By default it uses a free RSS-based provider that is deterministic and safe.
For teams that want higher-quality narrative content, there’s an optional OpenAI-backed provider that requires supplying your own API key.
Both paths go through the same validation and publishing pipeline, so the frontend is completely decoupled from content provenance.)

Everything revolves around one interface:

interface NewsProvider {
generate(date: string): Promise<NewsFile>;
}

High-level architecture

Two implementations. Same output.

                    ┌────────────────────────┐
                    │   Content Provider     │
                    │ (selected at runtime)  │
                    └───────────┬────────────┘
                                │
        ┌───────────────────────┴───────────────────────┐
        │                                                   │

┌──────────────┐ ┌─────────────────┐
│ RSS Provider │ │ OpenAI Provider │
│ (default) │ │ (optional) │
└──────┬───────┘ └──────┬──────────┘
│ │
▼ ▼
┌──────────────────────────┐ ┌──────────────────────────┐
│ Normalize + Simplify │ │ Prompt + Guardrails │
└──────────┬───────────────┘ └──────────┬───────────────┘
│ │
└──────────────────┬──────────────────────────┘
▼
┌───────────────────┐
│ Validator │
│ (schema + safety) │
└─────────┬─────────┘
▼
┌───────────────────┐
│ Publisher (S3) │
└───────────────────┘
