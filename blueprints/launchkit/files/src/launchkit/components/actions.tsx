import type { Action, Link } from "../types";

export function ActionLinks({ actions }: { actions: Action[] }) {
  return (
    <div className="action-group">
      {actions.map((action) => (
        <a className={`button ${action.tone}`} href={action.href} key={action.href}>
          {action.label}
        </a>
      ))}
    </div>
  );
}

export function LinkList({
  links,
  className = "link-list",
}: {
  links: Link[];
  className?: string;
}) {
  return (
    <ul className={className}>
      {links.map((link) => (
        <li key={`${link.label}:${link.href}`}>
          <a href={link.href}>{link.label}</a>
        </li>
      ))}
    </ul>
  );
}
