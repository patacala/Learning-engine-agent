interface Props {
  confidence: number;
}

export function ConfidenceBadge({ confidence }: Props) {
  const pct = Math.round(confidence * 100);
  return <span className="text-[12px] text-[#6e6e80]">{pct}%</span>;
}
