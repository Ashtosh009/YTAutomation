"use client";

import { useEffect, useState } from "react";
import { X, RefreshCw, ExternalLink, CheckCircle2, XCircle, Clock } from "lucide-react";

interface WorkflowRun {
  id: number;
  name: string;
  status: string;
  conclusion: string | null;
  html_url: string;
  created_at: string;
  head_branch: string;
  event: string;
}

export default function WorkflowRunsModal({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function fetchRuns() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/github/runs");
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to fetch runs");
      setRuns(data.runs || []);
      if (data.warning) setError(data.warning);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (isOpen) {
      fetchRuns();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
      <div className="bg-channel-dark border border-channel-border rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col max-h-[85vh]">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-channel-border">
          <div className="flex items-center gap-3">
            <h3 className="font-bold text-lg text-white">GitHub Actions Runs</h3>
            <span className="text-xs text-slate-400">Last 5 runs</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchRuns}
              disabled={loading}
              className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-channel-surface transition-colors disabled:opacity-50"
              title="Refresh runs"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
            <button
              onClick={onClose}
              className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-channel-surface transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-4">
          {error && (
            <div className="p-3 bg-amber-950/40 border border-amber-900/60 rounded-xl text-xs text-amber-300">
              {error}
            </div>
          )}

          {runs.length === 0 && !loading && !error && (
            <div className="text-center py-8 text-slate-500 text-sm">
              No recent workflow runs found.
            </div>
          )}

          <div className="space-y-3">
            {runs.map((run) => {
              const isCompleted = run.status === "completed";
              const isSuccess = run.conclusion === "success";
              const isFailed = run.conclusion === "failure";

              return (
                <div
                  key={run.id}
                  className="p-4 bg-channel-surface/60 border border-channel-border rounded-xl flex items-center justify-between gap-4 hover:border-channel-borderHover transition-all"
                >
                  <div className="flex items-start gap-3 min-w-0">
                    <div className="mt-0.5">
                      {isCompleted ? (
                        isSuccess ? (
                          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                        ) : isFailed ? (
                          <XCircle className="w-5 h-5 text-red-400" />
                        ) : (
                          <Clock className="w-5 h-5 text-slate-400" />
                        )
                      ) : (
                        <RefreshCw className="w-5 h-5 text-channel-yellow animate-spin" />
                      )}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-bold text-sm text-white truncate">
                          {run.name}
                        </span>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-channel-dark border border-channel-border text-slate-400">
                          {run.head_branch}
                        </span>
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
                            isSuccess
                              ? "bg-emerald-950/60 text-emerald-400 border border-emerald-900/60"
                              : isFailed
                              ? "bg-red-950/60 text-red-400 border border-red-900/60"
                              : "bg-yellow-950/60 text-yellow-400 border border-yellow-900/60"
                          }`}
                        >
                          {run.conclusion || run.status}
                        </span>
                      </div>
                      <div className="text-xs text-slate-400 mt-1">
                        Trigger: {run.event} • {new Date(run.created_at).toLocaleString()}
                      </div>
                    </div>
                  </div>

                  <a
                    href={run.html_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-2 text-slate-400 hover:text-channel-accent hover:bg-channel-dark rounded-lg transition-colors flex-shrink-0"
                    title="View on GitHub"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </div>
              );
            })}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-channel-border bg-channel-darkest/50 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-channel-surface hover:bg-channel-border text-white transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
