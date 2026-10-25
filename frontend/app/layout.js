import "./globals.css";
import NavBar from "../components/NavBar";

export const metadata = {
  title: "Green Cloud Scheduler",
  description: "Live dashboard and algorithm benchmarking for the Green Cloud Scheduler project",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <NavBar />
        <main className="page">{children}</main>
      </body>
    </html>
  );
}
