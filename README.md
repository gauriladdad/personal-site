# Personal Site


This is an [Astro](https://astro.build/) project. It is live at [news.gattani.ca](https://news.gattani.ca).

## Why Astro?

We chose Astro for this personal site because of its performance-first approach:

- **Zero JS by Default**: Astro ships no JavaScript to the client unless explicitly requested, resulting in lightning-fast load times.
- **Islands Architecture**: Interactive components are isolated, keeping the rest of the page static.
- **Content Focused**: Astro is designed for content-heavy sites like blogs and portfolios.


## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:4321](http://localhost:4321) with your browser to see the result.

You can start editing the page by modifying `src/pages/index.astro`. The page auto-updates as you edit the file.

## Learn More

To learn more about Astro, take a look at the following resources:

- [Astro Documentation](https://docs.astro.build) - learn about Astro features and API.
- [Astro Showcase](https://astro.build/themes/) - explore themes and projects built with Astro.

## Deploy on Cloudflare Pages

This site is deployed using Cloudflare Pages.

To deploy your own version:
1. Push your code to a git repository (GitHub/GitLab).
2. Log in to the Cloudflare dashboard and select your account.
3. In Account Home, select **Workers & Pages** > **Create Application** > **Pages** > **Connect to Git**.
4. Select your repository and follow the setup instructions. The build command is `npm run build` and the output directory is `dist`.

Check out the [Cloudflare Pages documentation](https://developers.cloudflare.com/pages/framework-guides/deploy-an-astro-site/) for more details.
