export default function PageHeader({ eyebrow, title, description, action }) {
  return (
    <div className="px-8 pt-6 pb-4 border-b border-ink-700 bg-surface flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow ? <div className="label mb-1">{eyebrow}</div> : null}
        <h1 className="text-[22px] font-semibold text-paper-100">{title}</h1>
        {description ? <p className="text-sm text-paper-500 mt-1 max-w-3xl">{description}</p> : null}
      </div>
      {action ? <div className="flex flex-wrap items-center gap-2">{action}</div> : null}
    </div>
  );
}
