import { headers } from "next/headers";
import { type NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { db } from "@/db";
import { document } from "@/db/schema";
import { eq, desc } from "drizzle-orm";

export async function GET(_request: NextRequest) {
  try {
    // 1. Authenticate user session using Better Auth (with dev fallback)
    const activeHeaders = await headers();
    await auth.api.getSession({
      headers: activeHeaders,
    });

    // 2. Fetch documents from database
    const userDocs = await db
      .select()
      .from(document)
      .orderBy(desc(document.uploadedAt));

    return NextResponse.json({
      success: true,
      documents: userDocs.map((doc) => ({
        doc_id: doc.id,
        file_name: doc.fileName,
        file_size: doc.fileSize,
        uploaded_at: doc.uploadedAt,
        wasabi_file_key: doc.wasabiFileKey,
        url: doc.fileUrl,
      })),
    });
  } catch (error: unknown) {
    console.error("Error fetching documents from database:", error);
    const errorMessage =
      error instanceof Error ? error.message : "Failed to fetch documents";
    return NextResponse.json({ error: errorMessage }, { status: 500 });
  }
}

export async function DELETE(request: NextRequest) {
  try {
    // 1. Authenticate user session using Better Auth
    const activeHeaders = await headers();
    await auth.api.getSession({
      headers: activeHeaders,
    });

    // 2. Parse request body
    let body: { doc_id?: string };
    try {
      body = await request.json();
    } catch {
      return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
    }

    const { doc_id } = body;

    if (!doc_id) {
      return NextResponse.json(
        { error: "Document ID (doc_id) is required" },
        { status: 400 },
      );
    }

    // 3. Fetch the document to ensure existence
    const [existingDoc] = await db
      .select()
      .from(document)
      .where(eq(document.id, doc_id))
      .limit(1);

    if (!existingDoc) {
      return NextResponse.json({ error: "Document not found" }, { status: 404 });
    }

    // 4. Delete the document from PostgreSQL database
    await db.delete(document).where(eq(document.id, doc_id));
    console.log(`[Database Delete] Successfully deleted document ${doc_id} from database.`);

    return NextResponse.json({
      success: true,
      message: "Document deleted from database successfully",
    });
  } catch (error: unknown) {
    console.error("Error deleting document from database:", error);
    const errorMessage =
      error instanceof Error ? error.message : "Internal server error during document deletion";
    return NextResponse.json({ error: errorMessage }, { status: 500 });
  }
}
