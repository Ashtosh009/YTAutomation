"use client";

import { useEffect, useState } from "react";
import {
  Lightbulb,
  Plus,
  Trash2,
  CheckCircle2,
  Clock,
  Sparkles,
  AlertCircle,
  Tag,
} from "lucide-react";

interface Idea {
  id: number;
  topic: string;
  niche?: string;
  status?: string;
  used?: boolean;
  created_at: string;
}

export default function IdeasPage() {
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [loading, setLoading] = useState(true);
  const [newTopic, setNewTopic] = useState("");
  const [newNiche, setNewNiche] = useState("mystery");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function fetchIdeas() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/ideas");
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to load ideas");
      setIdeas(data.ideas || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchIdeas();
  }, []);

  async function handleAddIdea(e: React.FormEvent) {
    e.preventDefault();
    if (!newTopic.trim()) return;

    setSubmitting(true);
    try {
      const res = await fetch("/api/ideas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: newTopic.trim(), niche: newNiche }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to add idea");

      setNewTopic("");
      setIdeas((prev) => [data.idea, ...prev]);
    } catch (err: any) {
      alert(`Error adding idea: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeleteIdea(id: number) {
    if (!confirm("Are you sure you want to delete this idea?")) return;

    try {
      const res = await fetch(`/api/ideas/${id}`, { method: "DELETE" });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.error || "Failed to delete idea");
      }
      setIdeas((prev) => prev.filter((i) => i.id !== id));
    } catch (err: any) {
      alert(`Delete error: ${err.message}`);
    }
  }

  // Filter unused vs used
  const unusedIdeas = ideas.filter(
    (i) => !i.used && i.status !== "processed" && i.status !== "used"
  );
  const usedIdeas = ideas.filter(
    (i) => i.used || i.status === "processed" || i.status === "used"
  );

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="p-6 bg-channel-dark border border-channel-border rounded-2xl shadow-xl flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-black text-white">Ideas & Topics Bank</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-channel-surface text-channel-accent border border-channel-border">
              {unusedIdeas.length} Unused
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            The batch generation pipeline automatically picks unused ideas when creating new mystery shorts.
          </p>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-950/40 border border-red-900/60 rounded-xl text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Add Idea Card */}
      <div className="p-6 bg-channel-dark border border-channel-border rounded-2xl shadow-2xl">
        <h2 className="text-base font-bold text-white mb-3 flex items-center gap-2">
          <Plus className="w-4 h-4 text-channel-accent" />
          <span>Add New Story or Mystery Idea</span>
        </h2>

        <form onSubmit={handleAddIdea} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <div className="sm:col-span-3">
              <input
                type="text"
                value={newTopic}
                onChange={(e) => setNewTopic(e.target.value)}
                placeholder="e.g. The mysterious disappearance of Flight 19 in the Bermuda Triangle..."
                required
                className="w-full bg-channel-surface border border-channel-border rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-channel-accent"
              />
            </div>

            <div className="sm:col-span-1">
              <select
                value={newNiche}
                onChange={(e) => setNewNiche(e.target.value)}
                className="w-full bg-channel-surface border border-channel-border rounded-xl px-4 py-3 text-sm text-slate-200 focus:outline-none focus:border-channel-accent"
              >
                <option value="mystery">Stickman Mystery</option>
                <option value="storytime">Storytime / Humor</option>
                <option value="unsolved">Unsolved Case</option>
                <option value="bizarre">Bizarre Fact</option>
              </select>
            </div>
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={submitting || !newTopic.trim()}
              className="px-6 py-2.5 rounded-xl font-bold text-xs bg-channel-accent hover:brightness-110 active:scale-95 text-channel-darkest shadow-md transition-all disabled:opacity-50 flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              <span>{submitting ? "Adding..." : "Add to Idea Bank"}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Unused vs Used Ideas Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Unused Ideas */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-white flex items-center gap-2 text-sm">
              <Clock className="w-4 h-4 text-channel-accent" />
              <span>Ready for Generation ({unusedIdeas.length})</span>
            </h3>
          </div>

          {loading ? (
            <div className="py-8 text-center text-xs text-slate-500">Loading ideas...</div>
          ) : unusedIdeas.length === 0 ? (
            <div className="p-8 text-center bg-channel-dark/60 border border-channel-border rounded-2xl text-xs text-slate-500">
              No unused ideas remaining. Add some above or the generator will use viral presets!
            </div>
          ) : (
            <div className="space-y-2.5">
              {unusedIdeas.map((idea) => (
                <div
                  key={idea.id}
                  className="p-4 bg-channel-dark border border-channel-border rounded-xl flex items-center justify-between gap-3 hover:border-channel-borderHover transition-all group"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-white break-words">
                      {idea.topic}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[11px] font-semibold text-channel-accent">
                        {idea.niche || "mystery"}
                      </span>
                      <span className="text-[11px] text-slate-500">
                        {new Date(idea.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>

                  <button
                    onClick={() => handleDeleteIdea(idea.id)}
                    className="p-2 text-slate-500 hover:text-red-400 hover:bg-channel-surface rounded-lg transition-colors flex-shrink-0"
                    title="Delete idea"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Used Ideas */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-white flex items-center gap-2 text-sm">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>Already Produced ({usedIdeas.length})</span>
            </h3>
          </div>

          {loading ? (
            <div className="py-8 text-center text-xs text-slate-500">Loading ideas...</div>
          ) : usedIdeas.length === 0 ? (
            <div className="p-8 text-center bg-channel-dark/60 border border-channel-border rounded-2xl text-xs text-slate-500">
              No produced ideas recorded yet.
            </div>
          ) : (
            <div className="space-y-2.5">
              {usedIdeas.map((idea) => (
                <div
                  key={idea.id}
                  className="p-4 bg-channel-dark/40 border border-channel-border/50 rounded-xl flex items-center justify-between gap-3 opacity-75"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-300 break-words line-through">
                      {idea.topic}
                    </p>
                    <div className="flex items-center gap-2 mt-1 text-[11px] text-slate-500">
                      <span>{idea.niche || "mystery"}</span>
                      <span>• Produced</span>
                    </div>
                  </div>

                  <button
                    onClick={() => handleDeleteIdea(idea.id)}
                    className="p-2 text-slate-600 hover:text-red-400 rounded-lg transition-colors flex-shrink-0"
                    title="Delete idea"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
