"use client";

import { useState } from "react";
import Link from "next/link";
import { MapPin, Phone, Menu, X, Search, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Navbar() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <header className="w-full z-50 flex flex-col font-sans">
      {/* Main Brand & Nav Bar */}
      <div className="bg-white py-4 px-4 sm:px-6  relative">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          {/* Brand/Logo on Left */}
          <div className="flex items-center gap-3">
            <div>
              <h1 className="font-bold text-lg leading-tight tracking-tight text-[#2E3A2F]">
                VRSA AGROTECH
              </h1>
            </div>
          </div>

          {/* Desktop Nav Links */}
          <nav className="hidden md:flex items-center gap-8 font-medium text-sm text-[#2E3A2F]">
            <Link
              href="/"
              className="hover:text-[#5F7560] transition-colors relative after:absolute after:bottom-[-4px] after:left-0 after:w-full after:h-0.5 after:bg-[#5F7560] after:scale-x-0 hover:after:scale-x-100 after:transition-transform"
            >
              Home
            </Link>
            <div className="relative group">
              <button className="flex items-center gap-1 hover:text-[#5F7560] transition-colors font-medium">
                Our Products{" "}
                <ChevronDown className="w-3 h-3 transition-transform group-hover:rotate-180" />
              </button>
              <div className="absolute top-full left-0 mt-2 w-48 bg-white rounded-md shadow-lg border border-zinc-100 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50 py-2">
                <Link
                  href="/products/cattle-feed"
                  className="block px-4 py-2 text-xs hover:bg-[#2E3A2F]/5 text-[#2E3A2F] font-medium"
                >
                  Cattle Feed
                </Link>
                <Link
                  href="/products/medicines"
                  className="block px-4 py-2 text-xs hover:bg-[#2E3A2F]/5 text-[#2E3A2F] font-medium"
                >
                  Veterinary Medicines
                </Link>
                <Link
                  href="/products/supplements"
                  className="block px-4 py-2 text-xs hover:bg-[#2E3A2F]/5 text-[#2E3A2F] font-medium"
                >
                  Supplements
                </Link>
              </div>
            </div>
            <Link
              href="/success"
              className="hover:text-[#5F7560] transition-colors relative after:absolute after:bottom-[-4px] after:left-0 after:w-full after:h-0.5 after:bg-[#5F7560] after:scale-x-0 hover:after:scale-x-100 after:transition-transform"
            >
              Success Stories
            </Link>
            <Link
              href="/about"
              className="hover:text-[#5F7560] transition-colors relative after:absolute after:bottom-[-4px] after:left-0 after:w-full after:h-0.5 after:bg-[#5F7560] after:scale-x-0 hover:after:scale-x-100 after:transition-transform"
            >
              About Us
            </Link>
            <Link
              href="/contact"
              className="hover:text-[#5F7560] transition-colors relative after:absolute after:bottom-[-4px] after:left-0 after:w-full after:h-0.5 after:bg-[#5F7560] after:scale-x-0 hover:after:scale-x-100 after:transition-transform"
            >
              Contact
            </Link>
          </nav>

          {/* Right Action buttons */}
          <div className="hidden md:flex items-center gap-4">
            <Button asChild className="bg-[#2E3A2F] text-white hover:bg-[#3E4E3F] hover:shadow-md transition-all rounded-full px-5 py-2 text-xs">
              <Link href="/ai">Consult AI Expert</Link>
            </Button>
          </div>

          {/* Mobile Menu Button */}
          <div className="md:hidden flex items-center gap-2">
            <button
              onClick={() => setIsOpen(!isOpen)}
              className="p-2 hover:bg-[#2E3A2F]/5 rounded-full transition-colors text-[#2E3A2F]"
              aria-label="Toggle menu"
            >
              {isOpen ? (
                <X className="w-6 h-6" />
              ) : (
                <Menu className="w-6 h-6" />
              )}
            </button>
          </div>
        </div>

        {/* Mobile Dropdown Menu */}
        {isOpen && (
          <div className="md:hidden absolute top-full left-0 w-full bg-white border-t border-zinc-100 shadow-md py-4 px-6 z-50 flex flex-col gap-4 transition-all duration-200">
            <Link
              href="/"
              onClick={() => setIsOpen(false)}
              className="hover:text-[#5F7560] font-medium py-1 transition-colors text-sm"
            >
              Home
            </Link>
            <div className="flex flex-col gap-2 pl-2 border-l border-zinc-200">
              <span className="font-semibold text-xs text-zinc-500 uppercase tracking-widest">
                Our Products
              </span>
              <Link
                href="/products/cattle-feed"
                onClick={() => setIsOpen(false)}
                className="hover:text-[#5F7560] text-sm py-1 transition-colors"
              >
                Cattle Feed
              </Link>
              <Link
                href="/products/medicines"
                onClick={() => setIsOpen(false)}
                className="hover:text-[#5F7560] text-sm py-1 transition-colors"
              >
                Veterinary Medicines
              </Link>
              <Link
                href="/products/supplements"
                onClick={() => setIsOpen(false)}
                className="hover:text-[#5F7560] text-sm py-1 transition-colors"
              >
                Supplements
              </Link>
            </div>
            <Link
              href="/success"
              onClick={() => setIsOpen(false)}
              className="hover:text-[#5F7560] font-medium py-1 transition-colors text-sm"
            >
              Success Stories
            </Link>
            <Link
              href="/about"
              onClick={() => setIsOpen(false)}
              className="hover:text-[#5F7560] font-medium py-1 transition-colors text-sm"
            >
              About Us
            </Link>
            <Link
              href="/contact"
              onClick={() => setIsOpen(false)}
              className="hover:text-[#5F7560] font-medium py-1 transition-colors text-sm"
            >
              Contact
            </Link>
            <Button
              asChild
              className="bg-[#2E3A2F] text-white hover:bg-[#3E4E3F] w-full rounded-full mt-2 text-xs font-semibold py-2.5 uppercase tracking-wider"
              onClick={() => setIsOpen(false)}
            >
              <Link href="/ai">Consult AI Expert</Link>
            </Button>
          </div>
        )}
      </div>
    </header>
  );
}
