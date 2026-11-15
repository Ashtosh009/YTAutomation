import Link from "next/link";
import { Play, Sparkles, Film, ArrowRight, ShieldCheck } from "lucide-react";

export default function AboutPage() {
  return (
    <div className="max-w-3xl mx-auto py-10 space-y-8">
      <div className="flex items-center justify-between pb-6 border-b border-channel-border">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-channel-purple to-channel-yellow flex items-center justify-center shadow-lg">
            <Play className="w-6 h-6 text-channel-darkest fill-channel-darkest ml-0.5" />
          </div>
          <div>
            <h1 className="text-2xl font-black text-white">No Brain Stickman</h1>
            <p className="text-xs text-slate-400">Original Stick-Figure Mystery Shorts</p>
          </div>
        </div>

        <Link
          href="/"
          className="text-xs font-semibold px-4 py-2 bg-channel-surface hover:bg-channel-border text-white border border-channel-border rounded-xl transition-all"
        >
          Control Panel
        </Link>
      </div>

      <div className="space-y-6 text-sm text-slate-300 leading-relaxed">
        <section className="p-6 bg-channel-dark border border-channel-border rounded-2xl space-y-3">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-channel-accent" />
            <span>Channel Concept</span>
          </h2>
          <p>
            <strong>No Brain Stickman</strong> is an original animated YouTube Shorts channel featuring fast-paced, humorous stick-figure mystery stories, unsolved historical enigmas, and bizarre everyday conundrums.
          </p>
          <p>
            Each short is crafted in vertical 9:16 format with expressive cartoon vector art, natural voiceover narration, and dynamic word-level karaoke subtitles.
          </p>
        </section>

        <section className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="p-5 bg-channel-surface/60 border border-channel-border rounded-2xl space-y-2">
            <Film className="w-5 h-5 text-channel-purple" />
            <h3 className="font-bold text-white text-sm">Original Vector Engine</h3>
            <p className="text-xs text-slate-400">
              Parametric stick-figure characters with dynamic facial expressions, comedy poses, and cinematic motion effects.
            </p>
          </div>

          <div className="p-5 bg-channel-surface/60 border border-channel-border rounded-2xl space-y-2">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
            <h3 className="font-bold text-white text-sm">Safe & Policy Compliant</h3>
            <p className="text-xs text-slate-400">
              Mandatory creator review before publishing, ensuring high quality, original writing, and strictly royalty-free assets.
            </p>
          </div>
        </section>

        <section className="p-6 bg-channel-dark border border-channel-border rounded-2xl space-y-2">
          <h2 className="text-base font-bold text-white">OAuth Verification Notice</h2>
          <p className="text-xs text-slate-400">
            This domain hosts the creator review panel and public endpoints for the Google Cloud project powering scheduled uploads to the official <em>No Brain Stickman</em> channel.
          </p>
          <div className="pt-2">
            <Link
              href="/privacy"
              className="inline-flex items-center gap-1.5 text-xs text-channel-accent hover:underline font-semibold"
            >
              <span>Read Full Privacy Policy</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}
