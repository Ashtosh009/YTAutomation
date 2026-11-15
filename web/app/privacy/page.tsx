import Link from "next/link";
import { Shield, ArrowLeft } from "lucide-react";

export default function PrivacyPolicyPage() {
  return (
    <div className="max-w-3xl mx-auto py-10 space-y-8">
      <div className="flex items-center justify-between pb-6 border-b border-channel-border">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-channel-surface text-channel-accent border border-channel-border">
            <Shield className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-black text-white">Privacy Policy</h1>
            <p className="text-xs text-slate-400">Effective Date: November 2026</p>
          </div>
        </div>

        <Link
          href="/"
          className="text-xs font-semibold text-slate-400 hover:text-white flex items-center gap-1.5"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Home</span>
        </Link>
      </div>

      <div className="prose prose-invert prose-sm text-slate-300 space-y-6 text-sm leading-relaxed">
        <section className="space-y-2">
          <h2 className="text-base font-bold text-white">Overview</h2>
          <p>
            <strong>No Brain Stickman Studio</strong> (accessible via this application) is an internal, private automation and content management tool operated exclusively by the channel owner.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-bold text-white">Google User Data & YouTube API</h2>
          <p>
            This application uses the <strong>YouTube Data API v3</strong> strictly to upload and schedule original animated videos to the channel owner&apos;s own YouTube channel (<em>No Brain Stickman</em>).
          </p>
          <ul className="list-disc pl-5 space-y-1 text-slate-400">
            <li>
              <strong>No Third-Party Data Collection:</strong> We do not collect, store, share, or sell any personal data, viewer information, or third-party user credentials.
            </li>
            <li>
              <strong>Internal Channel Scope:</strong> The OAuth credentials used are scoped exclusively to manage video uploads and publishing on the creator&apos;s authenticated YouTube channel.
            </li>
            <li>
              <strong>Google API Limited Use Compliance:</strong> The application&apos;s use of information received from Google APIs strictly adheres to the{" "}
              <a
                href="https://developers.google.com/terms/api-services-user-data-policy"
                target="_blank"
                rel="noopener noreferrer"
                className="text-channel-accent underline"
              >
                Google API Services User Data Policy
              </a>
              , including the Limited Use requirements.
            </li>
          </ul>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-bold text-white">Data Storage & Security</h2>
          <p>
            Any video files, scripts, and temporary metadata are stored securely within private Supabase database and storage instances owned and operated by the channel administrator.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-bold text-white">Contact</h2>
          <p>
            If you have questions regarding this privacy policy, please contact the channel administrator at{" "}
            <span className="text-channel-accent font-mono">support@nobrainstickman.com</span>.
          </p>
        </section>
      </div>
    </div>
  );
}
