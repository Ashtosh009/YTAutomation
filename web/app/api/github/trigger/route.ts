import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
  const GITHUB_REPO = process.env.GITHUB_REPO || "Ashtosh009/YTAutomation";

  if (!GITHUB_TOKEN) {
    return NextResponse.json(
      { error: "GITHUB_TOKEN is not configured in environment variables." },
      { status: 500 }
    );
  }

  try {
    const body = await request.json().catch(() => ({}));
    const { workflow = "generate.yml", count = "9", dry_run = false, action = "batch_generate" } = body;

    // Detect target workflow file
    // Supports generate.yml, upload.yml, or legacy pipeline.yml
    const inputs: Record<string, string> = {};

    if (workflow === "generate.yml") {
      inputs.count = String(count);
      inputs.dry_run = String(dry_run);
    } else if (workflow === "upload.yml") {
      inputs.dry_run = String(dry_run);
    } else if (workflow === "pipeline.yml") {
      inputs.action = action;
    }

    const response = await fetch(
      `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/${workflow}/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${GITHUB_TOKEN}`,
          Accept: "application/vnd.github.v3+json",
          "Content-Type": "application/json",
          "User-Agent": "YTAnimation-NextJS-Panel",
        },
        body: JSON.stringify({
          ref: "master",
          inputs,
        }),
      }
    );

    if (!response.ok) {
      const errText = await response.text();
      // If ref 'master' failed, try 'main'
      if (errText.includes("No ref found")) {
        const retryRes = await fetch(
          `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/${workflow}/dispatches`,
          {
            method: "POST",
            headers: {
              Authorization: `Bearer ${GITHUB_TOKEN}`,
              Accept: "application/vnd.github.v3+json",
              "Content-Type": "application/json",
              "User-Agent": "YTAnimation-NextJS-Panel",
            },
            body: JSON.stringify({
              ref: "main",
              inputs,
            }),
          }
        );
        if (!retryRes.ok) {
          const retryErr = await retryRes.text();
          return NextResponse.json({ error: retryErr }, { status: retryRes.status });
        }
        return NextResponse.json({
          success: true,
          message: `Dispatched ${workflow} on 'main'`,
        });
      }

      return NextResponse.json({ error: errText }, { status: response.status });
    }

    return NextResponse.json({
      success: true,
      message: `Successfully dispatched workflow '${workflow}'!`,
    });
  } catch (err: any) {
    return NextResponse.json(
      { error: err.message || "Failed to trigger GitHub Actions" },
      { status: 500 }
    );
  }
}
