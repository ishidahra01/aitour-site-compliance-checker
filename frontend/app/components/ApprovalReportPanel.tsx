"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  report: string | null;
  isStreaming: boolean;
}

export default function ApprovalReportPanel({ report, isStreaming }: Props) {
  if (!report) {
    return (
      <div className="flex flex-col h-full items-center justify-center text-center p-8
        bg-gray-50 dark:bg-gray-950">
        <div className="text-5xl mb-4">📋</div>
        <h2 className="text-lg font-semibold text-gray-600 dark:text-gray-400 mb-2">
          Site Approval Report
        </h2>
        <p className="text-sm text-gray-400 dark:text-gray-500 max-w-xs leading-relaxed">
          承認レポートはエージェントが Work IQ からコンテキストを収集し
          分析した後にここに表示されます。
        </p>
        <p className="text-xs text-gray-300 dark:text-gray-600 mt-3 max-w-xs">
          左の「📬 A市から設置許可メールが到着」ボタンを押してデモを開始してください。
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-white dark:bg-gray-900 overflow-hidden">
      {/* Panel header */}
      <div className="shrink-0 px-4 py-3 border-b border-gray-200 dark:border-gray-700
        bg-white dark:bg-gray-900 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-base">📋</span>
          <span className="text-sm font-semibold text-gray-800 dark:text-gray-200">
            Site Approval Report
          </span>
          {isStreaming && (
            <span className="flex items-center gap-1 text-xs text-blue-500 animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500 inline-block" />
              生成中…
            </span>
          )}
        </div>
        <button
          onClick={() => {
            const blob = new Blob([report], { type: "text/plain" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "site-approval-report.txt";
            a.click();
            URL.revokeObjectURL(url);
          }}
          title="レポートをダウンロード"
          className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
        >
          ⬇ Download
        </button>
      </div>

      {/* Report content */}
      <div className="flex-1 overflow-y-auto p-4">
        <pre className="text-xs font-mono text-gray-800 dark:text-gray-200
          whitespace-pre-wrap break-words leading-relaxed">
          {report}
        </pre>
      </div>
    </div>
  );
}
