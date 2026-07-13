import Navbar from "@/modules/web/navbar";
import Hero from "@/modules/web/hero";

export default function WebHome() {
  return (
    <div className="flex flex-col min-h-screen bg-white text-[#2E3A2F]">
      <Navbar />

      <main className="flex-grow">
        <Hero />
        <section className="bg-[#2E3A2F] text-white pt-24 pb-16 px-4 sm:px-6 lg:px-8 relative z-0 select-none"></section>
      </main>
    </div>
  );
}
