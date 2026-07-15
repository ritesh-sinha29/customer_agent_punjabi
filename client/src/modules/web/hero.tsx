"use client";

import {
  ArrowRight,
  Crown,
  HeartPulse,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function Hero() {
  const images = [
    {
      src: "/cow.jpg",
      alt: "Healthy Dairy Cow",
      title: "Dairy Cows",
      rotate: "-rotate-6 hover:-rotate-1",
      zIndex: "z-10",
      caption: "ਪਸ਼ੂਆਂ ਲਈ ਉੱਤਮ ਖੁਰਾਕ", // Premium feed for animals
    },
    {
      src: "/poultry.jpg",
      alt: "Healthy Poultry",
      title: "Poultry Farming",
      rotate: "rotate-3 hover:rotate-1",
      zIndex: "z-10",
      caption: "ਪੋਲਟਰੀ ਫਾਰਮਿੰਗ ਦੇਖਭਾਲ", // Poultry farming care
    },
    {
      src: "/buffalo.jpg",
      alt: "Strong Buffalo",
      title: "High Yield Buffaloes",
      rotate: "-rotate-3 hover:-rotate-0",
      zIndex: "z-20", // Middle one slightly on top
      caption: "ਵੱਧ ਦੁੱਧ ਉਤਪਾਦਨ ਲਈ", // For higher milk production
    },
    {
      src: "/hen.jpg",
      alt: "Laying Hen",
      title: "Egg Layer Care",
      rotate: "rotate-6 hover:rotate-2",
      zIndex: "z-10",
      caption: "ਤੰਦਰੁਸਤ ਮੁਰਗੀਆਂ", // Healthy hens
    },
    {
      src: "/horses.jpg",
      alt: "Majestic Horses",
      title: "Equine Nutrition",
      rotate: "-rotate-2 hover:rotate-1",
      zIndex: "z-10",
      caption: "ਘੋੜਿਆਂ ਲਈ ਖਾਸ ਦਵਾਈਆਂ", // Special medicines for horses
    },
  ];

  return (
    <section className="relative z-10 bg-white pt-16 pb-28 md:pb-40 overflow-x-clip overflow-y-visible font-sans border-b border-white select-none">
      {/* Decorative background elements */}
      <div className="absolute top-10 left-1/10 w-72 h-72 bg-[#5F7560]/5 rounded-full filter blur-3xl pointer-events-none" />
      <div className="absolute bottom-20 right-1/10 w-96 h-96 bg-[#2E3A2F]/5 rounded-full filter blur-3xl pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
        {/* Top Badge */}
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#5F7560] border border-[#5F7560]/20 text-white text-[10px] uppercase mb-5">
          <Crown className="w-3.5 h-3.5 text-white" />
          <span>Punjab's Trusted Livestock Care</span>
        </div>

        {/* English Main Heading */}
        <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight text-black max-w-4xl mx-auto leading-[1.1]">
          Nourishing Livestock,{" "}
          <span className="text-[#5F7560] relative inline-block">
            Empowering Farmers
          </span>
        </h1>

        {/* Punjabi Subheading with custom font */}
        <p className="font-gurmukhi text-lg sm:text-2xl md:text-3xl text-[#2E3A2F] mt-6 max-w-3xl mx-auto leading-relaxed font-semibold">
          ਪੋਸ਼ਣ ਤੇ ਦਵਾਈ - ਹਰ ਪਸ਼ੂ ਲਈ ਸੰਪੂਰਨ ਦੇਖਭਾਲ
        </p>

        {/* CTA Buttons */}
        <div className="flex flex-col sm:flex-row justify-center items-center gap-4 mt-8 mb-6 relative z-30">
          <Button
            asChild
            className="bg-[#2E3A2F] py-5! rounded-md cursor-pointer"
          >
            <Link href="/ai" className="flex items-center gap-2">
              Get started with AI
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
            </Link>
          </Button>
          <Button
            asChild
            variant="outline"
            className="border-2 border-[#2E3A2F] text-[#2E3A2F] hover:bg-[#2E3A2F]/5 rounded-md py-5! cursor-pointer"
          >
            <Link href="/ai">ਏ.ਆਈ. ਨਾਲ ਸ਼ੁਰੂ ਕਰੋ</Link>
          </Button>
        </div>

        {/* Polaroid Images Spread Container - directly below subtext */}
        <div className="mt-12 md:mt-16 relative">
          {/* Desktop Layout: Beautifully overlapping and rotated Polaroids */}
          <div className="hidden md:flex justify-center items-center gap-1.5 md:gap-2 lg:gap-3 xl:gap-4 relative px-4 -mb-36 lg:-mb-52 z-20">
            {images.map((img, idx) => (
              <div
                key={idx}
                className={`relative bg-white p-2.5 pb-8 shadow-2xl rounded-sm border border-zinc-100/80 transition-all duration-300 ${img.rotate} hover:scale-110 hover:z-50 hover:shadow-[0_25px_50px_-12px_rgba(0,0,0,0.4)] cursor-pointer w-40 md:w-44 lg:w-52 xl:w-60 shrink-0`}
              >
                <div className="relative aspect-[4/4] w-full overflow-hidden bg-zinc-50 border border-zinc-100 rounded-sm mb-3">
                  <Image
                    src={img.src}
                    alt={img.alt}
                    fill
                    sizes="(max-w-7xl) 20vw"
                    className="object-cover transition-transform duration-500 hover:scale-105"
                  />
                </div>
                <div className="text-left px-1">
                  <h3 className="font-semibold text-[11px] md:text-xs text-[#2E3A2F] tracking-tight">
                    {img.title}
                  </h3>
                  <p className="font-gurmukhi text-[10px] md:text-[11px] text-[#5F7560] mt-0.5 font-medium">
                    {img.caption}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* Mobile Layout: Swipeable Horizontal Carousel */}
          <div className="md:hidden flex overflow-x-auto gap-5 px-6 pb-12 pt-4 snap-x snap-mandatory scrollbar-none -mb-32 z-20 relative">
            {images.map((img, idx) => (
              <div
                key={idx}
                className="snap-center shrink-0 bg-white p-4 pb-10 shadow-xl rounded-sm border border-zinc-100 w-72 snap-always"
              >
                <div className="relative aspect-[4/3] w-full overflow-hidden bg-zinc-50 rounded-sm mb-3">
                  <Image
                    src={img.src}
                    alt={img.alt}
                    fill
                    sizes="72vw"
                    className="object-cover"
                  />
                </div>
                <div className="text-left px-1">
                  <h3 className="font-semibold text-sm text-[#2E3A2F]">
                    {img.title}
                  </h3>
                  <p className="font-gurmukhi text-xs text-[#5F7560] mt-1 font-medium">
                    {img.caption}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
