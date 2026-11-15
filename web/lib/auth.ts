// Web Crypto HMAC-SHA256 signed session cookie (Edge & Node runtime compatible)

const COOKIE_NAME = "yt_panel_session";

async function getCryptoKey(secret: string): Promise<CryptoKey> {
  const enc = new TextEncoder();
  return crypto.subtle.importKey(
    "raw",
    enc.encode(secret || "fallback-secret-please-set-SESSION_SECRET-32ch"),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"]
  );
}

function bufferToHex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function hexToUint8Array(hex: string): Uint8Array {
  const len = hex.length / 2;
  const buffer = new ArrayBuffer(len);
  const arr = new Uint8Array(buffer);
  for (let i = 0; i < len; i++) {
    arr[i] = parseInt(hex.substring(i * 2, i * 2 + 2), 16);
  }
  return arr;
}

export async function createSessionCookie(secret: string): Promise<{ name: string; value: string; options: any }> {
  const payload = {
    authenticated: true,
    exp: Date.now() + 7 * 24 * 60 * 60 * 1000, // 7 days
  };
  const payloadStr = JSON.stringify(payload);
  const payloadB64 = Buffer.from(payloadStr).toString("base64url");

  const key = await getCryptoKey(secret);
  const signatureBuffer = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(payloadB64)
  );
  const signatureHex = bufferToHex(signatureBuffer);
  const cookieValue = `${payloadB64}.${signatureHex}`;

  return {
    name: COOKIE_NAME,
    value: cookieValue,
    options: {
      httpOnly: true,
      secure: process.env.VERCEL === "1",
      sameSite: "lax" as const,
      path: "/",
      maxAge: 7 * 24 * 60 * 60,
    },
  };
}

export async function verifySessionCookie(cookieValue: string | undefined, secret: string): Promise<boolean> {
  if (!cookieValue) return false;

  const parts = cookieValue.split(".");
  if (parts.length !== 2) return false;

  const [payloadB64, signatureHex] = parts;

  try {
    const key = await getCryptoKey(secret);
    const signatureBytes = hexToUint8Array(signatureHex);

    const valid = await crypto.subtle.verify(
      "HMAC",
      key,
      signatureBytes as unknown as BufferSource,
      new TextEncoder().encode(payloadB64)
    );

    if (!valid) return false;

    const payloadJson = Buffer.from(payloadB64, "base64url").toString("utf-8");
    const payload = JSON.parse(payloadJson);

    if (!payload.authenticated || typeof payload.exp !== "number") {
      return false;
    }

    if (Date.now() > payload.exp) {
      return false; // Expired
    }

    return true;
  } catch {
    return false;
  }
}

export { COOKIE_NAME };
