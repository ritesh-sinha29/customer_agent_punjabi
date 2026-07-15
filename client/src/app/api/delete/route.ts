import { DeleteObjectCommand } from "@aws-sdk/client-s3";
import { headers } from "next/headers";
import { type NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { s3Client, WASABI_BUCKET_NAME } from "@/lib/wasabi";

export async function DELETE(request: NextRequest) {
  try {
    // 1. Authenticate user session using Better Auth
    const activeHeaders = await headers();
    const session = await auth.api.getSession({
      headers: activeHeaders,
    });

    if (!session) {
      return NextResponse.json(
        { error: "Unauthorized. Please sign in to delete files." },
        { status: 401 },
      );
    }

    const userId = session.user.id;

    // 2. Parse request body
    let body: { key?: string };
    try {
      body = await request.json();
    } catch {
      return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
    }

    const { key } = body;

    if (!key) {
      return NextResponse.json(
        { error: "File key is required" },
        { status: 400 },
      );
    }

    // 3. Security Check: Verify user can only delete their own uploaded files
    const userPrefix = `uploads/${userId}/`;
    if (!key.startsWith(userPrefix)) {
      return NextResponse.json(
        { error: "Forbidden. You can only delete your own files." },
        { status: 403 },
      );
    }

    // 4. Delete the file from Wasabi S3
    const command = new DeleteObjectCommand({
      Bucket: WASABI_BUCKET_NAME,
      Key: key,
    });

    await s3Client.send(command);

    return NextResponse.json({
      success: true,
      message: "File deleted successfully from Wasabi",
    });
  } catch (error: unknown) {
    console.error("Error in delete API handler:", error);
    const errorMessage =
      error instanceof Error
        ? error.message
        : "Internal server error during file deletion";
    return NextResponse.json({ error: errorMessage }, { status: 500 });
  }
}
