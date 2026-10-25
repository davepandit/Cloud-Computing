"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function NavBar() {
  const pathname = usePathname();
  return (
    <nav className="navbar">
      <span className="brand">green-cloud-scheduler</span>
      <Link href="/" className={pathname === "/" ? "active" : ""}>
        Live dashboard
      </Link>
      <Link href="/benchmarking" className={pathname === "/benchmarking" ? "active" : ""}>
        Benchmarking
      </Link>
    </nav>
  );
}
