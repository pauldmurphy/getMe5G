import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'getMe5G — 5G Home Internet Availability & Arbitrage Engine',
  description:
    'Comprehensive availability report of every 5G Home Internet and wireless broadband provider available at your address.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
