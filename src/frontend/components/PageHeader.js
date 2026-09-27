export default function PageHeader({ eyebrow, title, description, action }) {
  return (
    <div className="border-b border-ink-700 px-8 py-6 flex items-start justify-between gap-6">
      <div>
        {eyebrow ? (
          <div className="text-[11px] text-paper-500 mb-1">{eyebrow}</div>
        ) : null}
        <h1 className="font-serif text-2xl text-paper-100">{title}</h1>
        {description ? (
          <p className="text-sm text-paper-500 mt-1.5 max-w-2xl">{description}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}
