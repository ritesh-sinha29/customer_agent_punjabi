import { ListObjectsV2Command, PutObjectCommand } from "@aws-sdk/client-s3";
import { headers } from "next/headers";
import { type NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { s3Client, validateFile, WASABI_BUCKET_NAME } from "@/lib/wasabi";

export async function GET(_request: NextRequest) {
  try {
    // 1. Authenticate user session using Better Auth
    const activeHeaders = await headers();
    const session = await auth.api.getSession({
      headers: activeHeaders,
    });

    if (!session) {
      return NextResponse.json(
        { error: "Unauthorized. Please sign in to view files." },
        { status: 401 },
      );
    }

    const userId = session.user.id;

    // 2. Fetch objects from user's folder in Wasabi
    const command = new ListObjectsV2Command({
      Bucket: WASABI_BUCKET_NAME,
      Prefix: `uploads/${userId}/`,
    });

    const response = await s3Client.send(command);

    const endpoint =
      process.env.AWS_S3_ENDPOINT || "https://s3.eu-west-1.wasabisys.com";
    const cleanEndpoint = endpoint.endsWith("/")
      ? endpoint.slice(0, -1)
      : endpoint;

    // 3. Format response items
    const files = (response.Contents || []).map((item) => {
      const key = item.Key || "";
      const filename = key.substring(key.lastIndexOf("/") + 1);

      // Attempt to clean the timestamp-uuid- prefix from the display name
      const originalNameMatch = filename.match(/^\d+-[a-z0-9]+-(.+)$/);
      const displayName = originalNameMatch ? originalNameMatch[1] : filename;
      const publicUrl = `${cleanEndpoint}/${WASABI_BUCKET_NAME}/${key}`;

      return {
        key,
        name: displayName,
        size: item.Size || 0,
        lastModified: item.LastModified,
        url: publicUrl,
      };
    });

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
    // 1. Authenticate user session using Better Auth
    const activeHeaders = await headers();
    const session = await auth.api.getSession({
      headers: activeHeaders,
    });

    if (!session) {
      return NextResponse.json(
        { error: "Unauthorized. Please sign in to upload files." },
        { status: 401 },
      );
    }

    const userId = session.user.id;

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
    const command = new PutObjectCommand({
      Bucket: WASABI_BUCKET_NAME,
      Key: key,
      Body: buffer,
      ContentType: file.type || "application/octet-stream",
    });

    await s3Client.send(command);

    // Formulate URL
    // Public endpoint structure: endpoint/bucket/key
    const endpoint =
      process.env.AWS_S3_ENDPOINT || "https://s3.eu-west-1.wasabisys.com";
    const cleanEndpoint = endpoint.endsWith("/")
      ? endpoint.slice(0, -1)
      : endpoint;
    const publicUrl = `${cleanEndpoint}/${WASABI_BUCKET_NAME}/${key}`;

    return NextResponse.json({
      success: true,
      message: "File uploaded successfully",
      data: {
        key,
        name: file.name,
        size: file.size,
        type: file.type,
        url: publicUrl,
      },
    });
  } catch (error: unknown) {
    console.error("Error in upload API handler:", error);
    const errorMessage =
      error instanceof Error
        ? error.message
        : "Internal server error during file upload";
    return NextResponse.json({ error: errorMessage }, { status: 500 });
  }
}
