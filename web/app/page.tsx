"use client";

import { useEffect, useState } from "react";
import {
  Check,
  X,
  RotateCcw,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Clock,
  Film,
  Tag,
  FileText,
  AlertCircle,
  ExternalLink,
} from "lucide-react";

interface Scene {
  text: string;
  expression?: string;
  action?: string;
  prop?: string;
  camera_effect?: string;
}

interface Video {
  id: number;
  title: string;
  description: string;
  tags: string;
  video_url?: string;
  thumbnail_url?: string;
  status: string;
  created_at: string;
  parsed_script?: {
    scenes?: Scene[];
    title?: string;
    description?: string;
  };
}

export default function ReviewPage() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form states per video ID
  const [editedTitles, setEditedTitles] = useState<Record<number, string>>({});
  const [editedDescs, setEditedDescs] = useState<Record<number, string>>({});
  const [editedTags, setEditedTags] = useState<Record<number, string>>({});
  const [selectedSlots, setSelectedSlots] = useState<Record<number, string>>({});

  // Accordion toggle for script viewer
  const [expandedScripts, setExpandedScripts] = useState<Record<number, boolean>>({});

  // Action status per video
  const [actionInProgress, setActionInProgress] = useState<Record<number, boolean>>({});

  async function fetchPendingVideos() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/videos?status=pending_review");
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to load review queue");

      const list: Video[] = data.videos || [];
      setVideos(list);

      // Initialize edit fields
      const titles: Record<number, string> = {};
      const descs: Record<number, string> = {};
      const tags: Record<number, string> = {};
      const slots: Record<number, string> = {};

      list.forEach((v) => {
        titles[v.id] = v.title || "";
        descs[v.id] = v.description || "";
        tags[v.id] = v.tags || "";
        slots[v.id] = "auto";
      });

      setEditedTitles(titles);
      setEditedDescs(descs);
      setEditedTags(tags);
      setSelectedSlots(slots);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchPendingVideos();
  }, []);

  async function handleApprove(video: Video) {
    const id = video.id;
    setActionInProgress((prev) => ({ ...prev, [id]: true }));

    try {
      const title = editedTitles[id] ?? video.title;
      const description = editedDescs[id] ?? video.description;
      const tags = editedTags[id] ?? video.tags;
      const slot = selectedSlots[id];

      const res = await fetch(`/api/videos/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: "approved",
          title,
          description,
          tags,
          slot,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to approve video");

      // Remove from pending list
      setVideos((prev) => prev.filter((v) => v.id !== id));
    } catch (err: any) {
      alert(`Approval error: ${err.message}`);
    } finally {
      setActionInProgress((prev) => ({ ...prev, [id]: false }));
    }
  }

  async function handleReject(video: Video) {
    const id = video.id;
    if (!confirm(`Are you sure you want to REJECT "${video.title}"? It will not be uploaded.`)) {
      return;
    }

    setActionInProgress((prev) => ({ ...prev, [id]: true }));
    try {
      const res = await fetch(`/api/videos/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "rejected" }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to reject video");

      setVideos((prev) => prev.filter((v) => v.id !== id));
    } catch (err: any) {
      alert(`Reject error: ${err.message}`);
    } finally {
      setActionInProgress((prev) => ({ ...prev, [id]: false }));
    }
  }

  async function handleRegenerate(video: Video) {
    const id = video.id;
    if (
      !confirm(
        `REGENERATE "${video.title}"?\n\nThis will re-add this topic to the Ideas bank for the next generation run and discard this video.`
      )
    ) {
      return;
    }

    setActionInProgress((prev) => ({ ...prev, [id]: true }));
    try {
      const res = await fetch(`/api/videos/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: "regenerate",
          title: editedTitles[id] ?? video.title,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to regenerate video");

      setVideos((prev) => prev.filter((v) => v.id !== id));
    } catch (err: any) {
      alert(`Regenerate error: ${err.message}`);
    } finally {
      setActionInProgress((prev) => ({ ...prev, [id]: false }));
    }
  }

  function toggleScript(id: number) {
    setExpandedScripts((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  return (
    <div className="space-y-8">
      {/* Top Banner / Review Summary */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 p-6 bg-channel-dark border border-channel-border rounded-2xl shadow-xl">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-black text-white">Review Queue</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-channel-surface text-channel-accent border border-channel-border">
              {videos.length} Pending
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Review 9:16 Shorts generated every 3 days. Approved videos are uploaded automatically by daily cron.
          </p>
        </div>

        <button
          onClick={fetchPendingVideos}
          className="self-start sm:self-auto px-4 py-2 text-xs font-bold bg-channel-surface hover:bg-channel-border text-slate-200 border border-channel-border rounded-xl transition-all"
        >
          Refresh Queue
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-950/40 border border-red-900/60 rounded-xl text-sm text-red-300 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="py-20 text-center space-y-3">
          <div className="w-10 h-10 border-4 border-channel-purple border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm text-slate-400">Loading videos from Supabase...</p>
        </div>
      )}

      {/* Empty State */}
      {!loading && videos.length === 0 && !error && (
        <div className="py-20 px-6 text-center max-w-lg mx-auto bg-channel-dark border border-channel-border rounded-3xl space-y-5">
          <div className="w-16 h-16 mx-auto rounded-2xl bg-channel-surface flex items-center justify-center text-channel-accent">
            <Sparkles className="w-8 h-8" />
          </div>
          <div className="space-y-1">
            <h2 className="text-lg font-bold text-white">Review Queue is Clear!</h2>
            <p className="text-xs text-slate-400">
              No videos are currently pending review. Trigger the 9-video batch generation or check scheduled videos.
            </p>
          </div>
          <button
            onClick={async () => {
              const res = await fetch("/api/github/trigger", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ workflow: "generate.yml", count: 9 }),
              });
              const d = await res.json();
              alert(d.message || "Dispatched generation!");
            }}
            className="px-6 py-2.5 rounded-xl font-bold text-xs bg-gradient-to-r from-channel-purple to-channel-yellow text-channel-darkest hover:brightness-110 active:scale-95 transition-all shadow-lg"
          >
            🚀 Trigger 9-Batch Generation Now
          </button>
        </div>
      )}

      {/* Video Cards Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
        {videos.map((video) => {
          const isBusy = actionInProgress[video.id];
          const scenes = video.parsed_script?.scenes || [];
          const isScriptOpen = !!expandedScripts[video.id];

          return (
            <div
              key={video.id}
              className="bg-channel-dark border border-channel-border rounded-2xl overflow-hidden shadow-2xl flex flex-col justify-between hover:border-channel-borderHover transition-all"
            >
              <div className="p-6 space-y-6">
                {/* Header Info */}
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-channel-surface text-slate-300 border border-channel-border">
                      #{video.id}
                    </span>
                    <span className="text-xs px-2.5 py-0.5 rounded-full font-semibold bg-yellow-950/60 text-channel-accent border border-yellow-900/60">
                      Pending Review
                    </span>
                  </div>
                  <span className="text-xs text-slate-500">
                    {new Date(video.created_at).toLocaleDateString()}
                  </span>
                </div>

                {/* Media Container: 9:16 Video Player + Thumbnail */}
                <div className="grid grid-cols-1 sm:grid-cols-12 gap-4">
                  {/* Vertical Video Player */}
                  <div className="sm:col-span-7 bg-black rounded-xl overflow-hidden border border-channel-border aspect-[9/16] relative flex items-center justify-center">
                    {video.video_url ? (
                      <video
                        src={video.video_url}
                        controls
                        playsInline
                        preload="metadata"
                        poster={video.thumbnail_url}
                        className="w-full h-full object-contain"
                      />
                    ) : (
                      <div className="text-center p-4 text-slate-500 text-xs">
                        Video rendering or path missing.
                      </div>
                    )}
                  </div>

                  {/* Thumbnail & Quick Specs */}
                  <div className="sm:col-span-5 flex flex-col justify-between gap-3">
                    <div>
                      <span className="text-xs font-semibold text-slate-400 block mb-1">
                        9:16 Thumbnail
                      </span>
                      <div className="bg-channel-darkest rounded-xl overflow-hidden border border-channel-border aspect-[9/16] relative">
                        {video.thumbnail_url ? (
                          <img
                            src={video.thumbnail_url}
                            alt="Thumbnail"
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-xs text-slate-600">
                            No thumbnail
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="p-3 bg-channel-surface/60 rounded-xl border border-channel-border text-xs text-slate-400 space-y-1">
                      <div className="flex justify-between">
                        <span>Format:</span>
                        <span className="text-white font-medium">1080×1920</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Style:</span>
                        <span className="text-channel-accent font-medium">Stickman Mystery</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Scenes:</span>
                        <span className="text-white font-medium">{scenes.length}</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Editable Metadata */}
                <div className="space-y-4 pt-2">
                  {/* Title */}
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center gap-1.5">
                      <Film className="w-3.5 h-3.5 text-channel-accent" />
                      <span>Short Title</span>
                    </label>
                    <input
                      type="text"
                      value={editedTitles[video.id] ?? ""}
                      onChange={(e) =>
                        setEditedTitles((prev) => ({
                          ...prev,
                          [video.id]: e.target.value,
                        }))
                      }
                      className="w-full bg-channel-surface border border-channel-border rounded-xl px-3.5 py-2.5 text-sm font-bold text-white focus:outline-none focus:border-channel-accent"
                    />
                  </div>

                  {/* Description */}
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center gap-1.5">
                      <FileText className="w-3.5 h-3.5 text-channel-accent" />
                      <span>Description (with #Shorts)</span>
                    </label>
                    <textarea
                      rows={3}
                      value={editedDescs[video.id] ?? ""}
                      onChange={(e) =>
                        setEditedDescs((prev) => ({
                          ...prev,
                          [video.id]: e.target.value,
                        }))
                      }
                      className="w-full bg-channel-surface border border-channel-border rounded-xl px-3.5 py-2.5 text-xs text-slate-200 focus:outline-none focus:border-channel-accent"
                    />
                  </div>

                  {/* Tags */}
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center gap-1.5">
                      <Tag className="w-3.5 h-3.5 text-channel-accent" />
                      <span>Tags</span>
                    </label>
                    <input
                      type="text"
                      value={editedTags[video.id] ?? ""}
                      onChange={(e) =>
                        setEditedTags((prev) => ({
                          ...prev,
                          [video.id]: e.target.value,
                        }))
                      }
                      placeholder="comma-separated tags..."
                      className="w-full bg-channel-surface border border-channel-border rounded-xl px-3.5 py-2 text-xs text-slate-300 focus:outline-none focus:border-channel-accent"
                    />
                  </div>

                  {/* Slot selector */}
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-channel-accent" />
                      <span>Preferred Upload Slot</span>
                    </label>
                    <select
                      value={selectedSlots[video.id] || "auto"}
                      onChange={(e) =>
                        setSelectedSlots((prev) => ({
                          ...prev,
                          [video.id]: e.target.value,
                        }))
                      }
                      className="w-full bg-channel-surface border border-channel-border rounded-xl px-3.5 py-2 text-xs text-slate-300 focus:outline-none focus:border-channel-accent"
                    >
                      <option value="auto">Auto (Next Available Daily Slot)</option>
                      <option value="09:00">09:00 IST (Morning Peak)</option>
                      <option value="14:00">14:00 IST (Afternoon Slot)</option>
                      <option value="19:00">19:00 IST (Evening Peak)</option>
                    </select>
                  </div>

                  {/* Script Storyboard Accordion */}
                  {scenes.length > 0 && (
                    <div className="border border-channel-border rounded-xl overflow-hidden">
                      <button
                        onClick={() => toggleScript(video.id)}
                        className="w-full px-4 py-2.5 bg-channel-surface/60 hover:bg-channel-surface flex items-center justify-between text-xs font-semibold text-slate-300 transition-colors"
                      >
                        <span className="flex items-center gap-2">
                          <span>Story Script ({scenes.length} Scenes)</span>
                        </span>
                        {isScriptOpen ? (
                          <ChevronUp className="w-4 h-4 text-slate-400" />
                        ) : (
                          <ChevronDown className="w-4 h-4 text-slate-400" />
                        )}
                      </button>

                      {isScriptOpen && (
                        <div className="p-4 bg-channel-darkest/70 space-y-2.5 text-xs">
                          {scenes.map((scene, sIdx) => (
                            <div
                              key={sIdx}
                              className="p-2.5 rounded-lg bg-channel-surface/40 border border-channel-border/50 space-y-1"
                            >
                              <div className="flex items-center justify-between text-[11px] text-slate-400">
                                <span className="font-bold text-channel-accent">Scene {sIdx + 1}</span>
                                <div className="flex gap-2">
                                  {scene.expression && (
                                    <span className="px-1.5 py-0.5 rounded bg-channel-surface text-slate-300">
                                      {scene.expression}
                                    </span>
                                  )}
                                  {scene.prop && scene.prop !== "none" && (
                                    <span className="px-1.5 py-0.5 rounded bg-channel-surface text-channel-yellow">
                                      {scene.prop}
                                    </span>
                                  )}
                                </div>
                              </div>
                              <p className="text-slate-200">{scene.text}</p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Action Buttons: Approve, Reject, Regenerate */}
              <div className="p-4 sm:p-6 bg-channel-surface/40 border-t border-channel-border grid grid-cols-3 gap-3">
                <button
                  onClick={() => handleReject(video)}
                  disabled={isBusy}
                  className="py-3 px-3 rounded-xl font-bold text-xs bg-red-950/60 hover:bg-red-900/80 text-red-300 border border-red-900/60 transition-all flex items-center justify-center gap-1.5 disabled:opacity-50 active:scale-95"
                >
                  <X className="w-4 h-4" />
                  <span>Reject</span>
                </button>

                <button
                  onClick={() => handleRegenerate(video)}
                  disabled={isBusy}
                  className="py-3 px-3 rounded-xl font-bold text-xs bg-channel-surface hover:bg-channel-border text-channel-yellow border border-channel-border transition-all flex items-center justify-center gap-1.5 disabled:opacity-50 active:scale-95"
                  title="Re-add topic to ideas and discard this video"
                >
                  <RotateCcw className="w-4 h-4" />
                  <span>Regenerate</span>
                </button>

                <button
                  onClick={() => handleApprove(video)}
                  disabled={isBusy}
                  className="py-3 px-3 rounded-xl font-bold text-xs bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg transition-all flex items-center justify-center gap-1.5 disabled:opacity-50 active:scale-95"
                >
                  <Check className="w-4 h-4" />
                  <span>Approve</span>
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
