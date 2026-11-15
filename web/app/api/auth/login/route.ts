import { NextRequest, NextResponse } from "next/server";
import { createSessionCookie } from "@/lib/auth";

// In-memory brute-force throttle
const failedAttempts = new Map<string, { count: number; lastTime: number }>();

export async function POST(request: NextRequest) {
  try {
    const ip = request.headers.get("x-forwarded-for") || "unknown-ip";
    const now = Date.now();

    // Check throttle
    const record = failedAttempts.get(ip);
    if (record && record.count >= 5 && now - record.lastTime < 60000) {
      return NextResponse.json(
        { error: "Too many failed attempts. Please wait 1 minute." },
        { status: 429 }
      );
    }

    const { password } = await request.json();

    const expectedPassword = process.env.PANEL_PASSWORD || "admin";
    const secret = process.env.SESSION_SECRET || "default-secret-string-min-32-chars-long";

    if (!password || password !== expectedPassword) {
      // Artificial delay to prevent timing attacks / slow down attackers
      await new Promise((resolve) => setTimeout(resolve, 800));

      const count = (record?.count || 0) + 1;
      failedAttempts.set(ip, { count, lastTime: now });

      return NextResponse.json(
        { error: "Invalid password" },
        { status: 401 }
      );
    }

    // Reset throttle on success
    failedAttempts.delete(ip);

    const { name, value, options } = await createSessionCookie(secret);

    const response = NextResponse.json({ success: true });
    response.cookies.set(name, value, options);

    return response;
  } catch (err: any) {
    return NextResponse.json(
      { error: err.message || "Internal server error" },
      { status: 500 }
    );
  }
}
