// Vercel Serverless Function to trigger GitHub Actions
export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
  const GITHUB_REPO = process.env.GITHUB_REPO; // e.g. "username/YTanimation"
  const { action = 'batch_generate', topic = '' } = req.body;

  if (!GITHUB_TOKEN || !GITHUB_REPO) {
    return res.status(500).json({
      error: 'Missing GITHUB_TOKEN or GITHUB_REPO in environment variables.'
    });
  }

  try {
    const response = await fetch(
      `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/pipeline.yml/dispatches`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${GITHUB_TOKEN}`,
          'Accept': 'application/vnd.github.v3+json',
          'Content-Type': 'application/json',
          'User-Agent': 'Vercel-Shorts-Control-Panel'
        },
        body: JSON.stringify({
          ref: 'main',
          inputs: { action, topic }
        })
      }
    );

    if (!response.ok) {
      const errText = await response.text();
      return res.status(response.status).json({ error: errText });
    }

    return res.status(200).json({ success: true, message: `Workflow '${action}' dispatched!` });
  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
}
