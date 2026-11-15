"use client";

import { useEffect, useState } from "react";
import {
  ListOrdered,
  ExternalLink,
  CheckCircle2,
  Clock,
  AlertCircle,
  XCircle,
  Sparkles,
  RefreshCw,
} from "lucide-react";

interface Video {
  id: number;
  title: string;
  status: string;
  scheduled_at?: string;
  scheduled_publish_at?: string;
  youtube_video_id?: string;
  error?: string;
  error_log?: string;
  created_at: string;
}

export default function QueuePage() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");
  const [error, setError] = useState<string | null>(null);

  async function fetchVideos() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/videos");
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to load queue");
      setVideos(data.videos || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchVideos();
  }, []);

  const statuses = [
    { key: "all", label: "All Videos" },
    { key: "pending_review", label: "Pending Review" },
    { key: "approved", label: "Approved" },
    { key: "scheduled", label: "Scheduled" },
    { key: "published", label: "Published" },
    { key: "failed", label: "Failed" },
  ];

  const filteredVideos = videos.filter((v) => {
    if (filter === "all") return true;
    if (filter === "pending_review") {
      return v.status === "pending_review" || v.status === "ready_for_review";
    }
    return v.status === filter;
  });

  function getStatusBadge(status: string) {
    switch (status) {
      case "published":
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-purple-950/60 text-purple-300 border border-purple-800/60 flex items-center gap-1 w-fit">
            <CheckCircle2 className="w-3.5 h-3.5 text-purple-400" />
            <span>Published</span>
          </span>
        );
      case "scheduled":
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-blue-950/60 text-blue-300 border border-blue-800/60 flex items-center gap-1 w-fit">
            <Clock className="w-3.5 h-3.5 text-blue-400" />
            <span>Scheduled</span>
          </span>
        );
      case "approved":
      case "approved_for_upload":
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-950/60 text-emerald-300 border border-emerald-800/60 flex items-center gap-1 w-fit">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>Approved</span>
          </span>
        );
      case "pending_review":
      case "ready_for_review":
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-yellow-950/60 text-yellow-300 border border-yellow-800/60 flex items-center gap-1 w-fit">
            <Sparkles className="w-3.5 h-3.5 text-channel-accent" />
            <span>Pending Review</span>
          </span>
        );
      case "failed":
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-red-950/60 text-red-300 border border-red-800/60 flex items-center gap-1 w-fit">
            <AlertCircle className="w-3.5 h-3.5 text-red-400" />
            <span>Failed</span>
          </span>
        );
      case "rejected":
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-slate-900 text-slate-400 border border-slate-800 flex items-center gap-1 w-fit">
            <XCircle className="w-3.5 h-3.5" />
            <span>Rejected</span>
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-channel-surface text-slate-300 border border-channel-border">
            {status}
          </span>
        );
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 p-6 bg-channel-dark border border-channel-border rounded-2xl shadow-xl">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-black text-white">Video Queue & History</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-channel-surface text-channel-accent border border-channel-border">
              {videos.length} Total
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Tracking lifecycle from generation → review → YouTube scheduled publishing.
          </p>
        </div>

        <button
          onClick={fetchVideos}
          className="self-start sm:self-auto px-4 py-2 text-xs font-bold bg-channel-surface hover:bg-channel-border text-slate-200 border border-channel-border rounded-xl transition-all flex items-center gap-2"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-950/40 border border-red-900/60 rounded-xl text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        {statuses.map((tab) => {
          const active = filter === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setFilter(tab.key)}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all whitespace-nowrap ${
                active
                  ? "bg-channel-accent text-channel-darkest shadow-md"
                  : "bg-channel-dark hover:bg-channel-surface text-slate-400 border border-channel-border"
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Table Card */}
      <div className="bg-channel-dark border border-channel-border rounded-2xl overflow-hidden shadow-2xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-channel-darkest/70 border-b border-channel-border text-xs text-slate-400 uppercase tracking-wider">
              <tr>
                <th className="py-3.5 px-4">ID</th>
                <th className="py-3.5 px-4">Title</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Scheduled Release</th>
                <th className="py-3.5 px-4">YouTube</th>
                <th className="py-3.5 px-4">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-channel-border">
              {loading ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-400 text-xs">
                    Loading queue...
                  </td>
                </tr>
              ) : filteredVideos.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-500 text-xs">
                    No videos match the selected filter.
                  </td>
                </tr>
              ) : (
                filteredVideos.map((video) => {
                  const scheduledTime = video.scheduled_at || video.scheduled_publish_at;
                  const errorMsg = video.error || video.error_log;

                  return (
                    <tr key={video.id} className="hover:bg-channel-surface/40 transition-colors">
                      <td className="py-4 px-4 font-mono text-xs text-slate-400">
                        #{video.id}
                      </td>
                      <td className="py-4 px-4 font-semibold text-white max-w-xs">
                        <div className="truncate">{video.title}</div>
                        {errorMsg && (
                          <div className="text-[11px] text-red-400 mt-1 truncate" title={errorMsg}>
                            Error: {errorMsg}
                          </div>
                        )}
                      </td>
                      <td className="py-4 px-4">{getStatusBadge(video.status)}</td>
                      <td className="py-4 px-4 text-xs text-slate-300 whitespace-nowrap">
                        {scheduledTime ? (
                          <span className="flex items-center gap-1.5 text-blue-300">
                            <Clock className="w-3.5 h-3.5" />
                            <span>{new Date(scheduledTime).toLocaleString()}</span>
                          </span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>
                      <td className="py-4 px-4 whitespace-nowrap">
                        {video.youtube_video_id ? (
                          <a
                            href={`https://youtube.com/shorts/${video.youtube_video_id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs font-bold text-channel-accent hover:underline"
                          >
                            <span>Watch</span>
                            <ExternalLink className="w-3.5 h-3.5" />
                          </a>
                        ) : (
                          <span className="text-slate-600 text-xs">—</span>
                        )}
                      </td>
                      <td className="py-4 px-4 text-xs text-slate-500 whitespace-nowrap">
                        {new Date(video.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
