import "./globals.css";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body
        suppressHydrationWarning
        className="bg-bg text-text dark:bg-bg-dark dark:text-text-dark"
      >
        {children}
      </body>
    </html>
  );
}
