"use client";

import { ChevronDown, MapPin, Menu, Phone, Search, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { signIn, signOut, useSession } from "@/lib/auth-client";

export default function Navbar() {
  const [isOpen, setIsOpen] = useState(false);
  const { data: session, isPending } = useSession();
  const router = useRouter();

  const handleSignIn = async () => {
    try {
      await signIn.social({
        provider: "google",
        callbackURL: window.location.origin,
      });
    } catch (err) {
      console.error(err);
    }
  };

  const handleSignOut = async () => {
    try {
      await signOut({
        fetchOptions: {
          onSuccess: () => {
            router.push("/");
            router.refresh();
          },
        },
      });
    } catch (err) {
      console.error(err);
    }
  };

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
            {isPending ? (
              <div className="w-8 h-8 rounded-full bg-zinc-100 animate-pulse" />
            ) : session ? (
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  {session.user.image ? (
                    <img
                      src={session.user.image}
                      alt={session.user.name}
                      className="w-8 h-8 rounded-full border border-zinc-200"
                    />
                  ) : (
                    <div className="w-8 h-8 rounded-full bg-[#2E3A2F]/10 text-[#2E3A2F] flex items-center justify-center font-bold text-xs">
                      {session.user.name[0].toUpperCase()}
                    </div>
                  )}
                  <span className="text-xs font-semibold text-[#2E3A2F]">
                    {session.user.name.split(" ")[0]}
                  </span>
                </div>
                <Button
                  onClick={handleSignOut}
                  variant="outline"
                  className="border-zinc-200 text-zinc-700 hover:bg-zinc-50 hover:text-zinc-900 rounded-full px-4 py-1.5 text-xs transition-all font-medium"
                >
                  Sign Out
                </Button>
              </div>
            ) : (
              <Button
                onClick={handleSignIn}
                variant="outline"
                className="border-zinc-200 text-zinc-700 hover:bg-zinc-50 hover:text-zinc-900 rounded-full px-4 py-1.5 text-xs flex items-center gap-2 transition-all font-medium"
              >
                <svg
                  className="w-3.5 h-3.5"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                    fill="#4285F4"
                  />
                  <path
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    fill="#34A853"
                  />
                  <path
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                    fill="#FBBC05"
                  />
                  <path
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                    fill="#EA4335"
                  />
                </svg>
                Sign In
              </Button>
            )}

            <Button
              asChild
              className="bg-[#2E3A2F] text-white hover:bg-[#3E4E3F] hover:shadow-md transition-all rounded-full px-5 py-2 text-xs"
            >
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
            {isPending ? (
              <div className="w-full h-9 rounded-full bg-zinc-100 animate-pulse mt-2" />
            ) : session ? (
              <div className="flex flex-col gap-3 mt-2 border-t border-zinc-100 pt-4">
                <div className="flex items-center gap-3">
                  {session.user.image ? (
                    <img
                      src={session.user.image}
                      alt={session.user.name}
                      className="w-9 h-9 rounded-full border border-zinc-200"
                    />
                  ) : (
                    <div className="w-9 h-9 rounded-full bg-[#2E3A2F]/10 text-[#2E3A2F] flex items-center justify-center font-bold text-sm">
                      {session.user.name[0].toUpperCase()}
                    </div>
                  )}
                  <div className="flex flex-col">
                    <span className="text-sm font-semibold text-[#2E3A2F]">
                      {session.user.name}
                    </span>
                    <span className="text-xs text-zinc-500">
                      {session.user.email}
                    </span>
                  </div>
                </div>
                <Button
                  onClick={() => {
                    handleSignOut();
                    setIsOpen(false);
                  }}
                  variant="outline"
                  className="border-zinc-200 text-zinc-700 hover:bg-zinc-50 hover:text-zinc-900 w-full rounded-full py-2 text-xs font-semibold uppercase tracking-wider transition-all"
                >
                  Sign Out
                </Button>
              </div>
            ) : (
              <Button
                onClick={() => {
                  handleSignIn();
                  setIsOpen(false);
                }}
                variant="outline"
                className="border-zinc-200 text-zinc-700 hover:bg-zinc-50 hover:text-zinc-900 w-full rounded-full mt-2 py-2 text-xs font-semibold uppercase tracking-wider flex items-center justify-center gap-2 transition-all"
              >
                <svg
                  className="w-4 h-4"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                    fill="#4285F4"
                  />
                  <path
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    fill="#34A853"
                  />
                  <path
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                    fill="#FBBC05"
                  />
                  <path
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                    fill="#EA4335"
                  />
                </svg>
                Sign In
              </Button>
            )}
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
