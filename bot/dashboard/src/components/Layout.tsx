import type { ReactNode } from "react";

export default function Layout({ sidebar, mobileNav, bar, children }: {
  sidebar: ReactNode; mobileNav: ReactNode; bar: ReactNode; children: ReactNode;
}) {
  return (
    <div className="grid h-screen grid-rows-[auto_1fr_auto] md:grid-cols-[220px_1fr] md:grid-rows-[1fr_auto]">
      <div className="hidden md:row-span-1 md:block">{sidebar}</div>
      <div className="md:hidden">{mobileNav}</div>
      <main className="overflow-y-auto p-4 md:p-6">{children}</main>
      <div className="md:col-span-2">{bar}</div>
    </div>
  );
}
