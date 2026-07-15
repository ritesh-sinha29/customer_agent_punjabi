import { S3Client } from "@aws-sdk/client-s3";

const accessKeyId = process.env.AWS_ACCESS_KEY_ID;
const secretAccessKey = process.env.AWS_SECRET_ACCESS_KEY;
const region = process.env.AWS_REGION || "eu-west-1";
const endpoint =
  process.env.AWS_S3_ENDPOINT || "https://s3.eu-west-1.wasabisys.com";
const bucketName = process.env.AWS_BUCKET_NAME || "customer-pb-agent";

if (!accessKeyId || !secretAccessKey) {
  console.warn("Wasabi AWS credentials are not set in environment variables!");
}

export const s3Client = new S3Client({
  region,
  endpoint,
  credentials: {
    accessKeyId: accessKeyId || "",
    secretAccessKey: secretAccessKey || "",
  },
  forcePathStyle: true, // Required for Wasabi compatibility
});

export const WASABI_BUCKET_NAME = bucketName;

// Allowed file extensions
export const ALLOWED_EXTENSIONS = [".txt", ".pdf", ".docx", ".md"];

// Mapping of allowed extensions to typical mime types
export const ALLOWED_MIME_TYPES = [
  "text/plain",
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document", // .docx
  "application/msword", // .doc
  "text/markdown",
  "text/x-markdown",
];

export function validateFile(
  fileName: string,
  mimeType: string,
): { valid: boolean; error?: string } {
  if (!fileName) {
    return { valid: false, error: "File name is required" };
  }

  const lastDotIndex = fileName.lastIndexOf(".");
  if (lastDotIndex === -1) {
    return { valid: false, error: "File must have an extension" };
  }

  const extension = fileName.substring(lastDotIndex).toLowerCase();

  if (!ALLOWED_EXTENSIONS.includes(extension)) {
    return {
      valid: false,
      error: `Invalid file extension. Allowed extensions are: ${ALLOWED_EXTENSIONS.join(", ")}`,
    };
  }

  // Double check MIME type, but fallback to extension validation since OS/browsers may send generic mime-types (e.g. application/octet-stream for .md files)
  const isMimeAllowed =
    ALLOWED_MIME_TYPES.includes(mimeType) ||
    mimeType === "application/octet-stream" ||
    mimeType === "";

  if (!isMimeAllowed) {
    return {
      valid: false,
      error: `Invalid MIME type (${mimeType}). Allowed document files: txt, pdf, docx, md`,
    };
  }

  return { valid: true };
}
