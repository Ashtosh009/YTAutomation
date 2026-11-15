import { NextRequest, NextResponse } from "next/server";
import { getSupabaseAdmin, getSignedMediaUrl } from "@/lib/supabase";

export async function GET(request: NextRequest) {
  try {
    const supabase = getSupabaseAdmin();
    const { searchParams } = new URL(request.url);
    const status = searchParams.get("status");

    let query = supabase
      .from("videos")
      .select("*")
      .order("created_at", { ascending: false });

    if (status) {
      if (status === "pending_review") {
        query = query.in("status", ["pending_review", "ready_for_review"]);
      } else {
        query = query.eq("status", status);
      }
    }

    const { data: videos, error } = await query;

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    // Attach signed URLs for media
    const enrichedVideos = await Promise.all(
      (videos || []).map(async (v) => {
        const videoRawPath = v.storage_path || v.video_path;
        const thumbRawPath = v.thumbnail_path;

        const signedVideoUrl = await getSignedMediaUrl(videoRawPath);
        const signedThumbUrl = await getSignedMediaUrl(thumbRawPath);

        // Normalize script json
        let parsedScript = v.script || v.script_json;
        if (typeof parsedScript === "string") {
          try {
            parsedScript = JSON.parse(parsedScript);
          } catch {
            // Keep as string if parsing fails
          }
        }

        return {
          ...v,
          video_url: signedVideoUrl,
          thumbnail_url: signedThumbUrl,
          parsed_script: parsedScript,
        };
      })
    );

    return NextResponse.json({ videos: enrichedVideos });
  } catch (err: any) {
    return NextResponse.json(
      { error: err.message || "Failed to fetch videos" },
      { status: 500 }
    );
  }
}
