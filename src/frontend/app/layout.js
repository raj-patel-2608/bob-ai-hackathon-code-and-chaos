import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/roboto-mono/400.css";
import "@fontsource/roboto-mono/500.css";
import "./globals.css";
import Sidebar from "../components/Sidebar";
import TopBar from "../components/TopBar";
import { THEME_BOOT_SCRIPT } from "../lib/theme";

export const metadata = {
  title: "CrimeFIR: FIR Intelligence & Crime Pattern Detector",
  description:
    "Auto-drafts the crime classification of each FIR, links FIRs across stations by shared evidence, flags repeat-offender groups and writes station crime briefs. Team Code & Chaos, IBM x NFSU Bob Hackathon.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
      </head>
      <body className="font-sans text-[14px]">
        <TopBar />
        <div className="flex">
          <Sidebar />
          <main className="flex-1 min-w-0 pb-12">{children}</main>
        </div>
      </body>
    </html>
  );
}
