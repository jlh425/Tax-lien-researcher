interface Props {
  instrumentType: string | null;
}

export function InstrumentBadge({ instrumentType }: Props) {
  if (!instrumentType) return null;
  const isLien = instrumentType === "lien_certificate";
  return (
    <span
      className={`inline-block rounded text-xs font-bold uppercase px-1.5 py-0.5 ${
        isLien
          ? "bg-blue-100 text-blue-800"
          : "bg-purple-100 text-purple-800"
      }`}
    >
      {isLien ? "LIEN CERT" : "TAX DEED"}
    </span>
  );
}
