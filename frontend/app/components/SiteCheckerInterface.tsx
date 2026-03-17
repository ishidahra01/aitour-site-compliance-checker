"use client";

import { useState, useRef, useEffect } from "react";
import { CheckResult, LogEvent } from "@/app/lib/types";
import { submitCheck, getCheckStreamUrl } from "@/app/lib/api";

// ---------------------------------------------------------------------------
// Demo data constants
// ---------------------------------------------------------------------------

const SITES = [
  { id: "Site-2024-0847", name: "A市中央公園 (Site-2024-0847)" },
  { id: "Site-2024-1023", name: "B市駅前広場 (Site-2024-1023)" },
  { id: "Site-2024-1156", name: "C市海浜公園 (Site-2024-1156)" },
];

const CHECK_ITEMS = [
  { id: "municipality", label: "自治体条件突合" },
  { id: "design", label: "設計基準チェック" },
  { id: "alternative", label: "代替案分析" },
  { id: "cost", label: "コスト試算" },
];

// ---------------------------------------------------------------------------
// Small presentational components
// ---------------------------------------------------------------------------

function VerdictBadge({ verdict }: { verdict: string }) {
  const cfg =
    verdict === "go"
      ? { label: "GO", classes: "bg-green-500 text-white" }
      : verdict === "conditional_go"
      ? { label: "条件付き GO", classes: "bg-amber-500 text-white" }
      : { label: "NO-GO", classes: "bg-red-500 text-white" };

  return (
    <span
      className={`inline-flex items-center px-8 py-2 rounded-full text-3xl font-black tracking-wide ${cfg.classes}`}
    >
      {cfg.label}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const cfg =
    status === "pass"
      ? { label: "✓ 適合", classes: "bg-green-100 text-green-800 border-green-300" }
      : status === "fail"
      ? { label: "✗ 逸脱", classes: "bg-red-100 text-red-800 border-red-300" }
      : { label: "△ 条件付き", classes: "bg-amber-100 text-amber-800 border-amber-300" };

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded text-xs font-semibold border ${cfg.classes}`}
    >
      {cfg.label}
    </span>
  );
}

function SourceIcon({ type }: { type: string }) {
  return (
    <span>
      {type === "email" ? "✉️" : type === "meeting" ? "📋" : "📄"}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function SiteCheckerInterface() {
  const [selectedSite, setSelectedSite] = useState(SITES[0].id);
  const [selectedItems, setSelectedItems] = useState<Set<string>>(
    new Set(CHECK_ITEMS.map((i) => i.id))
  );
  const [freeText, setFreeText] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [result, setResult] = useState<CheckResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const logEndRef = useRef<HTMLDivElement>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // Clean up EventSource on unmount
  useEffect(() => () => esRef.current?.close(), []);

  const toggleItem = (id: string) => {
    setSelectedItems((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleRun = async () => {
    if (isRunning) return;
    setIsRunning(true);
    setLogs([]);
    setResult(null);
    setError(null);

    try {
      const checkId = await submitCheck({
        site_id: selectedSite,
        check_items: CHECK_ITEMS.filter((i) => selectedItems.has(i.id)).map(
          (i) => i.label
        ),
        free_text: freeText.trim() || undefined,
      });

      const es = new EventSource(getCheckStreamUrl(checkId));
      esRef.current = es;

      es.onmessage = (event) => {
        const data: LogEvent = JSON.parse(event.data);
        if (data.type === "log") {
          setLogs((prev) => [...prev, data.message]);
        } else if (data.type === "result") {
          setResult(data.data);
          es.close();
          setIsRunning(false);
        } else if (data.type === "error") {
          setError(data.message);
          setLogs((prev) => [...prev, `❌ ${data.message}`]);
          es.close();
          setIsRunning(false);
        }
      };

      es.onerror = () => {
        // Only flag as error if we don't have a result yet
        if (!result) {
          setError("接続エラーが発生しました。バックエンドが起動しているか確認してください。");
        }
        setIsRunning(false);
        es.close();
      };
    } catch (err) {
      setError(String(err));
      setIsRunning(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-10">
      <div className="w-[720px] mx-auto space-y-6">

        {/* ── Header ─────────────────────────────────────────────────── */}
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900">
            🗼 基地局設置チェッカー
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Powered by GitHub Copilot SDK · Work IQ MCP · M365 Copilot
          </p>
        </div>

        {/* ── Input Area ─────────────────────────────────────────────── */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-5">

          {/* Site dropdown */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              対象サイト
            </label>
            <select
              value={selectedSite}
              onChange={(e) => setSelectedSite(e.target.value)}
              disabled={isRunning}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm
                bg-white focus:outline-none focus:ring-2 focus:ring-blue-500
                disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {SITES.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          {/* Check items */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              チェック項目
            </label>
            <div className="flex flex-wrap gap-2">
              {CHECK_ITEMS.map((item) => (
                <button
                  key={item.id}
                  onClick={() => toggleItem(item.id)}
                  disabled={isRunning}
                  className={`px-4 py-1.5 rounded-full text-sm font-medium border transition-colors
                    disabled:opacity-50 disabled:cursor-not-allowed
                    ${
                      selectedItems.has(item.id)
                        ? "bg-blue-600 text-white border-blue-600"
                        : "bg-white text-gray-600 border-gray-300 hover:border-blue-400"
                    }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          {/* Free text input */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">
              追加指示
              <span className="ml-2 text-xs font-normal text-gray-400">
                （任意）入力すると上記の選択の代わりにエージェントへ送信されます
              </span>
            </label>
            <textarea
              value={freeText}
              onChange={(e) => setFreeText(e.target.value)}
              disabled={isRunning}
              placeholder="例: A市公園の許可条件を確認し、代替案のコストも含めてチェックしてください"
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm
                bg-white focus:outline-none focus:ring-2 focus:ring-blue-500
                disabled:opacity-50 placeholder-gray-400 resize-none"
            />
          </div>

          {/* Execute button */}
          <button
            onClick={handleRun}
            disabled={isRunning}
            className="w-full py-3 px-6 bg-blue-600 hover:bg-blue-700 text-white font-semibold
              rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed
              flex items-center justify-center gap-2"
          >
            {isRunning ? (
              <>
                <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                チェック実行中…
              </>
            ) : (
              "✓ 適合性チェックを実行"
            )}
          </button>
        </div>

        {/* ── Agent Log ──────────────────────────────────────────────── */}
        {(logs.length > 0 || isRunning) && (
          <div className="bg-gray-900 rounded-xl border border-gray-700 overflow-hidden">
            <div className="px-4 py-2 bg-gray-800 border-b border-gray-700 flex items-center gap-2">
              <span className="text-xs font-mono text-gray-400">エージェントログ</span>
              {isRunning && (
                <span className="flex items-center gap-1 text-xs text-green-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block animate-pulse" />
                  実行中
                </span>
              )}
            </div>
            <div className="p-4 font-mono text-xs text-green-400 space-y-1 max-h-64 overflow-y-auto">
              {logs.map((line, i) => (
                <div key={i} className="leading-relaxed whitespace-pre-wrap">
                  {line}
                </div>
              ))}
              <div ref={logEndRef} />
            </div>
          </div>
        )}

        {/* ── Error ──────────────────────────────────────────────────── */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
            ❌ {error}
          </div>
        )}

        {/* ── Results ────────────────────────────────────────────────── */}
        {result && (
          <div className="space-y-4">

            {/* Verdict banner */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
              <div className="flex items-center gap-4 mb-3">
                <VerdictBadge verdict={result.verdict} />
              </div>
              <p className="text-sm text-gray-600 leading-relaxed">
                {result.verdict_reason}
              </p>
            </div>

            {/* Coverage cards */}
            {result.coverage && (
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 text-center">
                  <div className="text-4xl font-black text-gray-800">
                    {result.coverage.current}%
                  </div>
                  <div className="text-xs text-gray-500 mt-1 font-medium">
                    カバレッジ現状
                  </div>
                </div>
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 text-center">
                  <div className="text-4xl font-black text-gray-800">
                    {result.coverage.standard}%
                  </div>
                  <div className="text-xs text-gray-500 mt-1 font-medium">
                    社内基準
                  </div>
                </div>
                {result.coverage.alternative != null && (
                  <div className="bg-white rounded-xl border border-green-300 shadow-sm p-5 text-center">
                    <div className="text-4xl font-black text-green-600">
                      {result.coverage.alternative}%
                    </div>
                    <div className="text-xs text-gray-500 mt-1 font-medium">
                      代替案適用後
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Check results table */}
            {result.checks && result.checks.length > 0 && (
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                <div className="px-5 py-3 border-b border-gray-100 bg-gray-50">
                  <h3 className="text-sm font-semibold text-gray-700">
                    チェック結果
                  </h3>
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-gray-400 uppercase tracking-wide">
                      <th className="px-5 py-2.5 text-left font-semibold">項目</th>
                      <th className="px-5 py-2.5 text-left font-semibold">基準</th>
                      <th className="px-5 py-2.5 text-left font-semibold">現状</th>
                      <th className="px-5 py-2.5 text-left font-semibold">判定</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.checks.map((check, i) => (
                      <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                        <td className="px-5 py-3 text-gray-800 font-medium">
                          {check.item}
                        </td>
                        <td className="px-5 py-3 text-gray-600">{check.standard}</td>
                        <td className="px-5 py-3 text-gray-600">{check.current}</td>
                        <td className="px-5 py-3">
                          <StatusBadge status={check.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Alternatives */}
            {result.alternatives && result.alternatives.length > 0 && (
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">代替案</h3>
                <div className="space-y-2">
                  {result.alternatives.map((alt, i) => (
                    <div
                      key={i}
                      className="flex flex-wrap items-center gap-4 text-sm bg-gray-50
                        rounded-lg px-4 py-3 border border-gray-100"
                    >
                      <span className="font-semibold text-gray-800">{alt.name}</span>
                      <span className="text-gray-500">
                        カバレッジ:{" "}
                        <strong className="text-gray-800">{alt.coverage}</strong>
                      </span>
                      <span className="text-gray-500">コスト影響: {alt.cost_delta}</span>
                      <span className="text-gray-500">工期: {alt.timeline_delta}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recommended actions */}
            {result.actions && result.actions.length > 0 && (
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">
                  推奨アクション
                </h3>
                <ol className="space-y-2">
                  {result.actions.map((action, i) => (
                    <li key={i} className="flex gap-3 text-sm text-gray-700">
                      <span
                        className="shrink-0 w-6 h-6 rounded-full bg-blue-100 text-blue-700
                          flex items-center justify-center text-xs font-bold"
                      >
                        {i + 1}
                      </span>
                      <span className="leading-relaxed">{action}</span>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {/* Sources */}
            {result.sources && result.sources.length > 0 && (
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">情報ソース</h3>
                <div className="flex flex-wrap gap-2">
                  {result.sources.map((src, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full
                        bg-gray-100 text-gray-700 text-xs border border-gray-200 font-medium"
                    >
                      <SourceIcon type={src.type} />
                      {src.title}
                      {src.date ? ` ${src.date}` : ""}
                    </span>
                  ))}
                </div>
              </div>
            )}

          </div>
        )}
      </div>
    </div>
  );
}
