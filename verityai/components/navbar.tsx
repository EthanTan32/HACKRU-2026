"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { MouseEvent } from "react";

export default function Navbar() {
    const pathname = usePathname();

    // On the home page, the logo scrolls back to the top instead of reloading the page
    const scrollToTop = (e: MouseEvent<HTMLAnchorElement>) => {
        if (pathname !== "/") return;
        e.preventDefault();
        window.scrollTo({ top: 0 });
        history.replaceState(null, "", "/");
    };

    // Next's <Link> ignores a click when the URL already has the same #hash,
    // so on the home page scroll to the section ourselves every time
    const scrollToSection = (id: string) => (e: MouseEvent<HTMLAnchorElement>) => {
        if (pathname !== "/") return;
        e.preventDefault();
        document.getElementById(id)?.scrollIntoView();
        history.replaceState(null, "", `/#${id}`);
    };

    return (
        <div className="navbar sticky top-0 z-50">
  {/* Gradient blur: stacked blur layers, each masked to fade out lower down */}
  <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-0 -bottom-8 -z-10">
    <div className="absolute inset-0 backdrop-blur-sm mask-b-from-60% mask-b-to-100%" />
    <div className="absolute inset-0 backdrop-blur-md mask-b-from-30% mask-b-to-75%" />
    <div className="absolute inset-0 backdrop-blur-lg mask-b-from-0% mask-b-to-50%" />
    <div className="absolute inset-0 bg-linear-to-b from-base-100/90 via-base-100/50 to-transparent" />
  </div>
  <div className="navbar-start">
    <div className="dropdown">
      <div tabIndex={0} role="button" className="btn btn-ghost lg:hidden">
        <svg aria-label="Menu" xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"> <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h8m-8 6h16" /> </svg>
      </div>
      <ul
        tabIndex={-1}
        className="menu menu-sm dropdown-content bg-base-100 rounded-box z-1 mt-3 w-52 p-2 shadow">
        <li><Link href="/#demo" onClick={scrollToSection("demo")}>Demo</Link></li>
        <li><Link href="/#about" onClick={scrollToSection("about")}>About</Link></li>
      </ul>
    </div>
    <Link href="/" onClick={scrollToTop} className="flex items-center px-4 text-4xl font-semibold ml-50 text-success font-(family-name:--font-aleo) rounded-field focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-success">
      <Image src="/logo.svg" alt="" width={38} height={38} className="size-9.5 -translate-y-0.75" priority />
      VerityAI
    </Link>
    <ul className="menu menu-horizontal menu-lg px-1 ml-4 hidden lg:flex">
      <li><Link href="/#demo" onClick={scrollToSection("demo")}>Demo</Link></li>
      <li><Link href="/#about" onClick={scrollToSection("about")}>About</Link></li>
    </ul>
  </div>
  <div className="navbar-end">

  </div>
</div>
    );
}