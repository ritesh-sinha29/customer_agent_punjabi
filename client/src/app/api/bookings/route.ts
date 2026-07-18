import { headers } from "next/headers";
import { type NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { db } from "@/db";
import { booking, user } from "@/db/schema";
import { desc, eq } from "drizzle-orm";

export async function GET(_request: NextRequest) {
  try {
    const activeHeaders = await headers();
    const session = await auth.api.getSession({
      headers: activeHeaders,
    });

    // Fetch the 10 most recent bookings from all users
    const recentBookings = await db
      .select({
        id: booking.id,
        productName: booking.productName,
        qty: booking.qty,
        status: booking.status,
        createdAt: booking.createdAt,
        customerName: user.name,
        customerEmail: user.email,
      })
      .from(booking)
      .leftJoin(user, eq(booking.userId, user.id))
      .orderBy(desc(booking.createdAt))
      .limit(10);

    return NextResponse.json({
      success: true,
      bookings: recentBookings,
    });
  } catch (error: unknown) {
    console.error("Error fetching bookings:", error);
    const errorMessage =
      error instanceof Error ? error.message : "Failed to fetch bookings";
    return NextResponse.json({ error: errorMessage }, { status: 500 });
  }
}
