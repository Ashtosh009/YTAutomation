import { createClient, SupabaseClient } from "@supabase/supabase-js";

let supabaseAdmin: SupabaseClient | null = null;

export function getSupabaseAdmin(): SupabaseClient {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_KEY;

  if (!url || !key) {
    throw new Error("Missing SUPABASE_URL or SUPABASE_KEY in environment variables.");
  }

  if (!supabaseAdmin) {
    supabaseAdmin = createClient(url, key, {
      auth: {
        persistSession: false,
        autoRefreshToken: false,
      },
    });
  }

  return supabaseAdmin;
}

export async function getSignedMediaUrl(
  filePathOrUrl: string | null | undefined,
  expiresIn = 7200
): Promise<string | null> {
  if (!filePathOrUrl) return null;

  const bucket = process.env.SUPABASE_BUCKET || "shorts";

  try {
    const supabase = getSupabaseAdmin();

    // Check if it's already an absolute storage URL or local relative key
    let objectPath = filePathOrUrl;

    if (filePathOrUrl.startsWith("http://") || filePathOrUrl.startsWith("https://")) {
      // If it contains /storage/v1/object/public/<bucket>/ or /sign/<bucket>/
      const publicPattern = `/storage/v1/object/public/${bucket}/`;
      const signPattern = `/storage/v1/object/sign/${bucket}/`;

      if (filePathOrUrl.includes(publicPattern)) {
        objectPath = filePathOrUrl.split(publicPattern)[1]?.split("?")[0] || filePathOrUrl;
      } else if (filePathOrUrl.includes(signPattern)) {
        // Already a signed or sign URL
        return filePathOrUrl;
      } else {
        // External URL (e.g. YouTube or CDN), return as-is
        return filePathOrUrl;
      }
    }

    // Clean leading slashes
    objectPath = objectPath.replace(/^\/+/, "");

    const { data, error } = await supabase.storage
      .from(bucket)
      .createSignedUrl(objectPath, expiresIn);

    if (error || !data?.signedUrl) {
      // Fallback: return public URL if signed URL fails or bucket is public
      const { data: pubData } = supabase.storage.from(bucket).getPublicUrl(objectPath);
      return pubData?.publicUrl || filePathOrUrl;
    }

    return data.signedUrl;
  } catch (err) {
    console.error("[Supabase Storage] Error generating signed URL:", err);
    return filePathOrUrl;
  }
}
