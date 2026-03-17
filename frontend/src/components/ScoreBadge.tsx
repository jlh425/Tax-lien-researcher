interface Props {
  score: number | null;
  size?: "sm" | "md" | "lg";
}

function scoreColor(score: number | null): string {
  if (score === null) return "bg-gray-200 text-gray-500";
  if (score >= 75) return "bg-green-100 text-green-800";
  if (score >= 55) return "bg-yellow-100 text-yellow-800";
  if (score >= 35) return "bg-orange-100 text-orange-800";
  return "bg-red-100 text-red-700";
}

export function ScoreBadge({ score, size = "md" }: Props) {
  const sizeClass = size === "sm" ? "text-xs px-1.5 py-0.5" : size === "lg" ? "text-xl px-3 py-1" : "text-sm px-2 py-0.5";
  return (
    <span className={`inline-block rounded-full font-semibold tabular-nums ${sizeClass} ${scoreColor(score)}`}>
      {score !== null ? score : "—"}
    </span>
  );
}
