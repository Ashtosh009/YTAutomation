import { NextResponse } from "next/server";

export async function GET() {
  const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
  const GITHUB_REPO = process.env.GITHUB_REPO || "Ashtosh009/YTAutomation";

  if (!GITHUB_TOKEN) {
    return NextResponse.json({
      runs: [],
      warning: "GITHUB_TOKEN not configured. Set GITHUB_TOKEN to view live workflow runs.",
    });
  }

  try {
    const res = await fetch(
      `https://api.github.com/repos/${GITHUB_REPO}/actions/runs?per_page=5`,
      {
        headers: {
          Authorization: `Bearer ${GITHUB_TOKEN}`,
          Accept: "application/vnd.github.v3+json",
          "User-Agent": "YTAnimation-NextJS-Panel",
        },
        next: { revalidate: 15 },
      }
    );

    if (!res.ok) {
      const err = await res.text();
      return NextResponse.json(
        { error: `GitHub API error: ${err}` },
        { status: res.status }
      );
    }

    const data = await res.json();
    const runs = (data.workflow_runs || []).map((r: any) => ({
      id: r.id,
      name: r.name,
      status: r.status,
      conclusion: r.conclusion,
      html_url: r.html_url,
      created_at: r.created_at,
      head_branch: r.head_branch,
      event: r.event,
    }));

    return NextResponse.json({ runs });
  } catch (err: any) {
    return NextResponse.json(
      { error: err.message || "Failed to fetch GitHub runs" },
      { status: 500 }
    );
  }
}
