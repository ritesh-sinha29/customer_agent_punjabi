import { headers } from "next/headers";
import { type NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { db } from "@/db";
import { query, user } from "@/db/schema";
import { desc, eq } from "drizzle-orm";

export async function GET(_request: NextRequest) {
  try {
    const activeHeaders = await headers();
    await auth.api.getSession({
      headers: activeHeaders,
    });

    const recentQuiries = await db
      .select({
        id: query.id,
        title: query.title,
        description: query.description,
        status: query.status,
        createdAt: query.createdAt,
        customerName: user.name,
        customerEmail: user.email,
        customerImage: user.image,
      })
      .from(query)
      .leftJoin(user, eq(query.userId, user.id))
      .orderBy(desc(query.createdAt))
      .limit(50);

    return NextResponse.json({
      success: true,
      quiries: recentQuiries,
    });
  } catch (error: unknown) {
    console.error("Error fetching quiries:", error);
    const errorMessage =
      error instanceof Error ? error.message : "Failed to fetch quiries";
    return NextResponse.json({ error: errorMessage }, { status: 500 });
  }
}

export async function PATCH(request: NextRequest) {
  try {
    const activeHeaders = await headers();
    await auth.api.getSession({
      headers: activeHeaders,
    });

    const body = await request.json();
    const { id, status } = body;

    if (!id || !status) {
      return NextResponse.json(
        { error: "Query ID and status are required" },
        { status: 400 }
      );
    }

    const [updatedQuery] = await db
      .update(query)
      .set({
        status,
        updatedAt: new Date(),
      })
      .where(eq(query.id, id))
      .returning();

    return NextResponse.json({
      success: true,
      query: updatedQuery,
    });
  } catch (error: unknown) {
    console.error("Error updating query status:", error);
    const errorMessage =
      error instanceof Error ? error.message : "Failed to update query status";
    return NextResponse.json({ error: errorMessage }, { status: 500 });
  }
}
