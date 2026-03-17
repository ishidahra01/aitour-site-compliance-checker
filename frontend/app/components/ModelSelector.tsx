"use client";

import { Model } from "@/app/lib/types";

interface Props {
  models: Model[];
  selected: string;
  onChange: (modelId: string) => void;
  disabled?: boolean;
}

export default function ModelSelector({ models, selected, onChange, disabled }: Props) {
  return (
    <div className="flex items-center gap-2">
      <label htmlFor="model-select" className="text-sm font-medium text-gray-600 dark:text-gray-400 whitespace-nowrap">
        Model:
      </label>
      <select
        id="model-select"
        value={selected}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="text-sm border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5
          bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100
          focus:outline-none focus:ring-2 focus:ring-blue-500
          disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {models.map((m) => (
          <option key={m.id} value={m.id}>
            {m.name}
          </option>
        ))}
      </select>
    </div>
  );
}
