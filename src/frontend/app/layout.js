import "./globals.css";
import Sidebar from "../components/Sidebar";

export const metadata = {
  title: "CrimeFIR: FIR Intelligence & Crime Pattern Detector",
  description:
    "Auto-drafts the crime classification of each FIR, links FIRs across stations by shared evidence, flags repeat-offender clusters and writes station crime briefs. Team Code & Chaos, IBM x NFSU Bob Hackathon.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="font-sans">
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 min-w-0">{children}</main>
        </div>
      </body>
    </html>
  );
}
