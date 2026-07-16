import {
  GetObjectCommand,
  ListObjectsV2Command,
  PutObjectCommand,
} from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { headers } from "next/headers";
import { type NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { s3Client, validateFile, WASABI_BUCKET_NAME } from "@/lib/wasabi";
import { db } from "@/db";
import { document, user } from "@/db/schema";
import { eq } from "drizzle-orm";

export async function GET(_request: NextRequest) {
  try {
    // 1. Authenticate user session using Better Auth (with dev fallback)
    const activeHeaders = await headers();
    const session = await auth.api.getSession({
      headers: activeHeaders,
    });

    const userId = session ? session.user.id : "admin-client-user";

    // 2. Fetch objects from user's folder in Wasabi
    const command = new ListObjectsV2Command({
      Bucket: WASABI_BUCKET_NAME,
      Prefix: `uploads/${userId}/`,
    });

    const response = await s3Client.send(command);

    // 3. Format response items with pre-signed URLs
    const files = await Promise.all(
      (response.Contents || []).map(async (item) => {
        const key = item.Key || "";
        const filename = key.substring(key.lastIndexOf("/") + 1);

        // Attempt to clean the timestamp-uuid- prefix from the display name
        const originalNameMatch = filename.match(/^\d+-[a-z0-9]+-(.+)$/);
        const displayName = originalNameMatch ? originalNameMatch[1] : filename;

        // Generate pre-signed URL (expires in 24 hours / 86400 seconds)
        const getCommand = new GetObjectCommand({
          Bucket: WASABI_BUCKET_NAME,
          Key: key,
        });
        const signedUrl = await getSignedUrl(s3Client, getCommand, {
          expiresIn: 86400,
        });

        return {
          key,
          name: displayName,
          size: item.Size || 0,
          lastModified: item.LastModified,
          url: signedUrl,
        };
      }),
    );

    // Sort by last modified date descending (newest first)
    files.sort((a, b) => {
      const aTime = a.lastModified ? new Date(a.lastModified).getTime() : 0;
      const bTime = b.lastModified ? new Date(b.lastModified).getTime() : 0;
      return bTime - aTime;
    });

    return NextResponse.json({
      success: true,
      files,
    });
  } catch (error: unknown) {
    console.error("Error listing files from Wasabi:", error);
    const errorMessage =
      error instanceof Error ? error.message : "Failed to list files";
    return NextResponse.json({ error: errorMessage }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    // 1. Authenticate user session using Better Auth (with dev fallback)
    const activeHeaders = await headers();
    const session = await auth.api.getSession({
      headers: activeHeaders,
    });

    const userId = session ? session.user.id : "admin-client-user";

    // 2. Parse FormData
    const formData = await request.formData();
    const file = formData.get("file") as File | null;

    if (!file) {
      return NextResponse.json({ error: "No file provided" }, { status: 400 });
    }

    // 3. Validate file name and type
    const validation = validateFile(file.name, file.type);
    if (!validation.valid) {
      return NextResponse.json({ error: validation.error }, { status: 400 });
    }

    // 4. Read file content into a Buffer
    const arrayBuffer = await file.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    // 5. Generate a unique key for the file to prevent overwrite collisions
    const timestamp = Date.now();
    const uniqueId = Math.random().toString(36).substring(2, 8);
    // Sanitize filename to avoid weird character issues in S3 URLs
    const sanitizedFileName = file.name.replace(/[^a-zA-Z0-9.-]/g, "_");
    // Place uploads in a user-specific folder for security and organization
    const key = `uploads/${userId}/${timestamp}-${uniqueId}-${sanitizedFileName}`;

    // 6. Upload to Wasabi
    console.log(
      `[Wasabi Upload] Initializing upload to bucket: "${WASABI_BUCKET_NAME}", key: "${key}", Content-Type: "${file.type}"`,
    );
    const command = new PutObjectCommand({
      Bucket: WASABI_BUCKET_NAME,
      Key: key,
      Body: buffer,
      ContentType: file.type || "application/octet-stream",
      ACL: "public-read",
    });

    await s3Client.send(command);
    console.log(
      `[Wasabi Upload] SUCCESSFULLY uploaded file "${file.name}" to Wasabi. Key: "${key}"`,
    );

    // Generate pre-signed URL (expires in 24 hours / 86400 seconds)
    const getCommand = new GetObjectCommand({
      Bucket: WASABI_BUCKET_NAME,
      Key: key,
    });
    const signedUrl = await getSignedUrl(s3Client, getCommand, {
      expiresIn: 86400,
    });
    console.log(`[Presigned URL] Generated pre-signed URL: ${signedUrl}`);

    // Ensure fallback user row exists in DB to prevent foreign key violation
    if (userId === "admin-client-user") {
      const existingUser = await db
        .select()
        .from(user)
        .where(eq(user.id, "admin-client-user"))
        .limit(1);
      if (existingUser.length === 0) {
        await db.insert(user).values({
          id: "admin-client-user",
          name: "Admin Client",
          email: "admin@vrsa.com",
          emailVerified: true,
        });
      }
    }

    // Pre-generate unique document ID using UUID
    const docId = crypto.randomUUID();

    // Insert document metadata record immediately into database
    const [insertedDoc] = await db
      .insert(document)
      .values({
        id: docId,
        fileName: file.name,
        fileSize: file.size,
        wasabiFileKey: key,
        fileUrl: signedUrl,
        userId: userId,
      })
      .returning();

    console.log(`[Database Insert] Saved document to database with ID: ${insertedDoc.id}`);

    return NextResponse.json({
      success: true,
      message: "File uploaded and recorded successfully",
      data: {
        id: insertedDoc.id,
        key: insertedDoc.wasabiFileKey,
        name: insertedDoc.fileName,
        size: insertedDoc.fileSize,
        url: insertedDoc.fileUrl,
        uploadedAt: insertedDoc.uploadedAt,
      },
    });
  } catch (error: unknown) {
    console.error("[Wasabi Upload] ERROR uploading to Wasabi:", error);
    const errorMessage =
      error instanceof Error
        ? error.message
        : "Internal server error during file upload";
    return NextResponse.json({ error: errorMessage }, { status: 500 });
  }
}

