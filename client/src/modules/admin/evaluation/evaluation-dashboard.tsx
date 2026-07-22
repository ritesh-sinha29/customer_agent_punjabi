"use client";

import React, { useState, useEffect } from "react";
import {
  ShieldCheck,
  Target,
  Search,
  GitFork,
  Play,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Eye,
  Layers,
  Sparkles,
  Info,
  PlusCircle,
  Zap,
  Send,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import Image from "next/image";

const API_BASE = "http://localhost:8000/api";

interface EvalRun {
  id: string;
  suite_name: string;
  faithfulness_avg: number;
  relevance_avg: number;
  context_precision_avg: number;
  router_accuracy_avg: number;
  hallucination_rate: number;
  status: string;
  total_cases: number;
  created_at: string;
}

interface EvalResultItem {
  id: string;
  testcase_id: string;
  category: string;
  query: string;
  ground_truth: string;
  expected_route: string;
  actual_route: string;
  retrieved_contexts: string[];
  generated_answer: string;
  faithfulness_score: number;
  relevance_score: number;
  hallucination_flag: boolean;
  judge_rationale: string;
}

interface EvalRunDetails extends EvalRun {
  results: EvalResultItem[];
}

export function EvaluationDashboard() {
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<EvalRunDetails | null>(null);
  const [activeModalItem, setActiveModalItem] = useState<EvalResultItem | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [runningSuite, setRunningSuite] = useState(false);

  // Custom question tester states
  const [customQuery, setCustomQuery] = useState("");
  const [customTruth, setCustomTruth] = useState("");
  const [testingCustom, setTestingCustom] = useState(false);

  const fetchRuns = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/eval/runs`);
      if (res.ok) {
        const data = await res.json();
        setRuns(data.runs || []);
        if (data.runs && data.runs.length > 0 && !selectedRun) {
          fetchRunDetails(data.runs[0].id);
        }
      }
    } catch (err) {
      console.error("Error fetching runs:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchRunDetails = async (runId: string) => {
    try {
      const res = await fetch(`${API_BASE}/eval/runs/${runId}`);
      if (res.ok) {
        const data: EvalRunDetails = await res.json();
        setSelectedRun(data);
      }
    } catch (err) {
      console.error("Error fetching run details:", err);
    }
  };

  // Trigger quick 2-random sample benchmark (Saves API tokens & costs!)
  const handleTriggerQuickRun = async (count: number = 2) => {
    setRunningSuite(true);
    try {
      const res = await fetch(`${API_BASE}/eval/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          suite_name:
            count === 2 ? "Quick Benchmark (2 Samples)" : "Full Benchmark",
          sample_count: count,
        }),
      });
      if (res.ok) {
        setTimeout(() => {
          fetchRuns();
          setRunningSuite(false);
        }, 3500);
      } else {
        setRunningSuite(false);
      }
    } catch (err) {
      console.error("Error starting eval:", err);
      setRunningSuite(false);
    }
  };

  // Trigger admin custom query test
  const handleRunCustomQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customQuery.trim()) return;
    setTestingCustom(true);
    try {
      const res = await fetch(`${API_BASE}/eval/custom`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: customQuery,
          ground_truth: customTruth,
          expected_route: "RAG_SEARCH",
        }),
      });
      if (res.ok) {
        setCustomQuery("");
        setCustomTruth("");
        setTimeout(() => {
          fetchRuns();
          setTestingCustom(false);
        }, 3500);
      } else {
        setTestingCustom(false);
      }
    } catch (err) {
      console.error("Error running custom query eval:", err);
      setTestingCustom(false);
    }
  };

  useEffect(() => {
    fetchRuns();
  }, []);

  const latestRun = selectedRun || (runs.length > 0 ? runs[0] : null);

  return (
    <div className="p-2 space-y-8 bg-white min-h-screen ">
      {/* Header */}
      <div className="flex justify-between border rounded-md py-6 px-4 bg-linear-to-br from-emerald-600/40 to-white relative min-h-[190px]">
        <div className="flex flex-col">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-3xl font-semibold tracking-tight ">
                RAG & Agent Evaluation
              </h1>
              <Badge className="bg-[#5F7560] text-white text-xs font-semibold px-2 py-0.5">
                No Blind Trust Engine
              </Badge>
            </div>
            <p className="text-sm mt-2">
              Rag & Agent Benchmarking: Use RAGAS / LLM Judge For Evaluation/
              Golden dataset for Evaluation.
            </p>
          </div>

          <div className="flex items-center gap-3 mt-5">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchRuns}
              disabled={loading}
              className="border-border rounded-sm"
            >
              <RefreshCw
                className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`}
              />
              Refresh
            </Button>

            {/* Token Saver Quick 2-Sample Run */}
            <Button
              size="sm"
              onClick={() => handleTriggerQuickRun(2)}
              disabled={runningSuite}
              className="rounded-sm text-xs"
            >
              {runningSuite ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  Evaluating...
                </>
              ) : (
                <>
                  <Zap className="h-4 w-4 mr-2 text-amber-300 fill-amber-300" />
                  Quick Test (Random sample)
                </>
              )}
            </Button>
          </div>
        </div>

        <Image
          src="/evals.svg"
          alt="home"
          width={170}
          height={170}
          className="absolute -top-5 right-0"
        />
      </div>

      {/* Admin Custom Test Question Bar */}
      <Card className="border border-[#5F7560]/30 bg-gradient-to-r from-emerald-50/40 via-white to-amber-50/30 shadow-xs">
        <CardContent className="p-4 sm:p-6">
          <form
            onSubmit={handleRunCustomQuery}
            className="flex flex-col md:flex-row items-center gap-4"
          >
            <div className="flex-1 w-full space-y-2">
              <label className="text-xs font-bold uppercase tracking-wider text-[#2E3A2F] flex items-center gap-1.5">
                <PlusCircle className="h-4 w-4 text-[#5F7560]" />
                Test Custom Admin Question (Single Background Job)
              </label>
              <Input
                placeholder="e.g. What is the daily dosage of MaxaPro Liquid for buffaloes?"
                value={customQuery}
                onChange={(e) => setCustomQuery(e.target.value)}
                className="bg-white border-border text-sm"
              />
            </div>

            <div className="flex-1 w-full space-y-2">
              <label className="text-xs font-medium text-muted-foreground">
                Expected Ground Truth (Optional)
              </label>
              <Input
                placeholder="e.g. 100ml per day mixed in feed."
                value={customTruth}
                onChange={(e) => setCustomTruth(e.target.value)}
                className="bg-white border-border text-sm"
              />
            </div>

            <div className="self-end w-full md:w-auto">
              <Button
                type="submit"
                disabled={testingCustom || !customQuery.trim()}
                className="w-full md:w-auto bg-[#5F7560] hover:bg-[#2E3A2F] text-white font-semibold text-xs h-10 px-5 shadow-xs"
              >
                {testingCustom ? (
                  <>
                    <RefreshCw className="h-3.5 w-3.5 mr-2 animate-spin" />
                    Testing Query...
                  </>
                ) : (
                  <>
                    <Send className="h-3.5 w-3.5 mr-2" />
                    Evaluate Custom Query
                  </>
                )}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="border border-border/60 shadow-sm bg-white hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Faithfulness Index
            </CardTitle>
            <div className="p-2 bg-emerald-50 rounded-lg text-emerald-600">
              <ShieldCheck className="h-5 w-5" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-extrabold text-[#2E3A2F]">
              {latestRun ? `${latestRun.faithfulness_avg}%` : "--"}
            </div>
            <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
              Facts supported by PDF docs
            </p>
          </CardContent>
        </Card>

        <Card className="border border-border/60 shadow-sm bg-white hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Answer Relevancy
            </CardTitle>
            <div className="p-2 bg-blue-50 rounded-lg text-blue-600">
              <Target className="h-5 w-5" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-extrabold text-[#2E3A2F]">
              {latestRun ? `${latestRun.relevance_avg}%` : "--"}
            </div>
            <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
              <Sparkles className="h-3.5 w-3.5 text-blue-500" />
              Direct intent alignment
            </p>
          </CardContent>
        </Card>

        <Card className="border border-border/60 shadow-sm bg-white hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Context Precision
            </CardTitle>
            <div className="p-2 bg-amber-50 rounded-lg text-amber-600">
              <Search className="h-5 w-5" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-extrabold text-[#2E3A2F]">
              {latestRun ? `${latestRun.context_precision_avg}%` : "--"}
            </div>
            <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
              <Layers className="h-3.5 w-3.5 text-amber-500" />
              Pinecone + BM25 retriever efficiency
            </p>
          </CardContent>
        </Card>

        <Card className="border border-border/60 shadow-sm bg-white hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Hallucination Rate
            </CardTitle>
            <div className="p-2 bg-rose-50 rounded-lg text-rose-600">
              <AlertTriangle className="h-5 w-5" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-extrabold text-rose-600">
              {latestRun ? `${latestRun.hallucination_rate}%` : "--"}
            </div>
            <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
              {latestRun && latestRun.hallucination_rate > 0 ? (
                <span className="text-rose-500 font-medium">
                  Warning: Unsupported claims detected
                </span>
              ) : (
                <span className="text-emerald-600 font-medium">
                  0% Hallucinations detected
                </span>
              )}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Split */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Run Selector List (Left Column) */}
        <Card className="border border-border/60 bg-white shadow-sm lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-base font-bold text-[#2E3A2F] flex items-center gap-2">
              <Layers className="h-4 w-4 text-[#5F7560]" />
              Historical Benchmark Runs
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 max-h-[500px] overflow-y-auto pr-2">
            {runs.length === 0 ? (
              <div className="text-sm text-muted-foreground text-center py-6">
                No benchmark runs found. Click "Quick Test" to run 2 samples!
              </div>
            ) : (
              runs.map((r) => {
                const isSelected = selectedRun?.id === r.id;
                return (
                  <div
                    key={r.id}
                    onClick={() => fetchRunDetails(r.id)}
                    className={`p-4 rounded-xl border transition-all cursor-pointer ${
                      isSelected
                        ? "border-[#5F7560] bg-[#5F7560]/5 shadow-sm"
                        : "border-border hover:border-muted-foreground/30 hover:bg-muted/30"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-sm text-[#2E3A2F]">
                        {r.id}
                      </span>
                      <Badge
                        variant="outline"
                        className={
                          r.status === "COMPLETED"
                            ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                            : "bg-amber-50 text-amber-700 border-amber-200 animate-pulse"
                        }
                      >
                        {r.status}
                      </Badge>
                    </div>

                    <div className="mt-2 text-xs text-muted-foreground flex justify-between">
                      <span className="truncate max-w-[180px]">
                        {r.suite_name}
                      </span>
                      <span>{r.total_cases} case(s)</span>
                    </div>

                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs font-semibold pt-2 border-t border-border/50">
                      <div>
                        Faithful:{" "}
                        <span className="text-emerald-600">
                          {r.faithfulness_avg}%
                        </span>
                      </div>
                      <div>
                        Router:{" "}
                        <span className="text-blue-600">
                          {r.router_accuracy_avg}%
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </CardContent>
        </Card>

        {/* Detailed Test Case Inspector Table (Right 2 Columns) */}
        <Card className="border border-border/60 bg-white shadow-sm lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base font-bold text-[#2E3A2F] flex items-center gap-2">
              <Eye className="h-4 w-4 text-[#5F7560]" />
              Test Case Evaluation Inspector (
              {selectedRun?.results?.length || 0} samples)
            </CardTitle>
            {selectedRun && (
              <Badge variant="outline" className="text-xs">
                Run ID: {selectedRun.id}
              </Badge>
            )}
          </CardHeader>
          <CardContent>
            {!selectedRun ||
            !selectedRun.results ||
            selectedRun.results.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground text-sm">
                Select a run or execute a benchmark to view detailed test case
                results.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left border-collapse">
                  <thead>
                    <tr className="border-b border-border text-xs uppercase tracking-wider text-muted-foreground bg-muted/40">
                      <th className="py-3 px-3">Category</th>
                      <th className="py-3 px-3">Query</th>
                      <th className="py-3 px-3">Route</th>
                      <th className="py-3 px-3 text-center">Faithful</th>
                      <th className="py-3 px-3 text-center">Status</th>
                      <th className="py-3 px-3 text-right">Inspect</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {selectedRun.results.map((item) => {
                      const isHallucinated = item.hallucination_flag;
                      return (
                        <tr
                          key={item.id}
                          className="hover:bg-muted/20 transition-colors"
                        >
                          <td className="py-3 px-3 font-semibold text-xs text-[#5F7560]">
                            {item.category}
                          </td>
                          <td className="py-3 px-3 max-w-[220px] truncate font-medium text-xs">
                            {item.query}
                          </td>
                          <td className="py-3 px-3">
                            <Badge
                              variant="secondary"
                              className="text-[10px] font-mono"
                            >
                              {item.actual_route}
                            </Badge>
                          </td>
                          <td className="py-3 px-3 text-center font-semibold">
                            <span
                              className={
                                item.faithfulness_score >= 80
                                  ? "text-emerald-600"
                                  : "text-rose-600"
                              }
                            >
                              {item.faithfulness_score}%
                            </span>
                          </td>
                          <td className="py-3 px-3 text-center">
                            {isHallucinated ? (
                              <Badge className="bg-rose-100 text-rose-700 border-rose-200 text-[10px]">
                                Hallucination
                              </Badge>
                            ) : (
                              <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200 text-[10px]">
                                Verified
                              </Badge>
                            )}
                          </td>
                          <td className="py-3 px-3 text-right">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setActiveModalItem(item)}
                              className="h-7 text-xs hover:bg-[#5F7560]/10 text-[#2E3A2F]"
                            >
                              <Eye className="h-3.5 w-3.5 mr-1" />
                              Inspect
                            </Button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Side-by-Side Test Case Deep-Dive Modal */}
      <Dialog
        open={!!activeModalItem}
        onOpenChange={() => setActiveModalItem(null)}
      >
        <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto bg-white p-6 rounded-2xl">
          {activeModalItem && (
            <div className="space-y-6">
              <DialogHeader border-b pb-4>
                <div className="flex items-center justify-between">
                  <DialogTitle className="text-xl font-extrabold text-[#2E3A2F] flex items-center gap-2">
                    <Sparkles className="h-5 w-5 text-[#5F7560]" />
                    Test Case Deep-Dive Inspector
                  </DialogTitle>
                  <Badge
                    className={
                      activeModalItem.hallucination_flag
                        ? "bg-rose-100 text-rose-700 border-rose-200"
                        : "bg-emerald-100 text-emerald-700 border-emerald-200"
                    }
                  >
                    {activeModalItem.hallucination_flag
                      ? "Hallucination Alert"
                      : "Faithful Grounded"}
                  </Badge>
                </div>
              </DialogHeader>

              {/* User Question & Ground Truth */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 bg-muted/30 rounded-xl border border-border">
                  <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                    User Query
                  </span>
                  <p className="text-sm font-semibold text-[#2E3A2F] mt-1">
                    {activeModalItem.query}
                  </p>
                </div>
                <div className="p-4 bg-emerald-50/50 rounded-xl border border-emerald-200/60">
                  <span className="text-xs font-bold uppercase tracking-wider text-emerald-800">
                    Golden Ground Truth
                  </span>
                  <p className="text-sm text-emerald-900 font-medium mt-1">
                    {activeModalItem.ground_truth || "N/A"}
                  </p>
                </div>
              </div>

              {/* Score Badges Summary */}
              <div className="grid grid-cols-3 gap-4 text-center">
                <div className="p-3 bg-white border rounded-xl shadow-xs">
                  <div className="text-xs text-muted-foreground">
                    Faithfulness Score
                  </div>
                  <div className="text-xl font-extrabold text-emerald-600 mt-1">
                    {activeModalItem.faithfulness_score}%
                  </div>
                </div>
                <div className="p-3 bg-white border rounded-xl shadow-xs">
                  <div className="text-xs text-muted-foreground">
                    Answer Relevancy
                  </div>
                  <div className="text-xl font-extrabold text-blue-600 mt-1">
                    {activeModalItem.relevance_score}%
                  </div>
                </div>
                <div className="p-3 bg-white border rounded-xl shadow-xs">
                  <div className="text-xs text-muted-foreground">
                    Routing Check
                  </div>
                  <div className="text-xs font-bold text-[#2E3A2F] mt-1 font-mono">
                    Expected: {activeModalItem.expected_route} <br />
                    Actual: {activeModalItem.actual_route}
                  </div>
                </div>
              </div>

              {/* Side-by-Side: Retrieved Chunks vs Agent Generated Answer */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Left: Retrieved PDF Context Chunks */}
                <div className="space-y-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <Search className="h-3.5 w-3.5 text-[#5F7560]" />
                    Retrieved Chunks (Pinecone / BM25)
                  </h4>
                  <div className="p-4 bg-slate-900 text-slate-100 rounded-xl text-xs font-mono max-h-60 overflow-y-auto space-y-2">
                    {activeModalItem.retrieved_contexts.map((chunk, idx) => (
                      <div
                        key={idx}
                        className="pb-2 border-b border-slate-800 last:border-none"
                      >
                        <span className="text-amber-400 font-bold">
                          [Chunk {idx + 1}]
                        </span>
                        : {chunk}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Right: Agent Generated Answer */}
                <div className="space-y-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                    Agent Generated Response
                  </h4>
                  <div className="p-4 bg-muted/40 rounded-xl text-xs text-[#2E3A2F] leading-relaxed max-h-60 overflow-y-auto border border-border">
                    {activeModalItem.generated_answer}
                  </div>
                </div>
              </div>

              {/* LLM Judge Rationale */}
              <div className="p-4 bg-amber-50/60 rounded-xl border border-amber-200 text-xs space-y-1">
                <span className="font-bold text-amber-900 flex items-center gap-1">
                  <Info className="h-4 w-4 text-amber-700" />
                  LLM Evaluator Rationale:
                </span>
                <p className="text-amber-900 leading-relaxed">
                  {activeModalItem.judge_rationale}
                </p>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
