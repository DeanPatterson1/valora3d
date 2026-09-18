import { cx } from "./cx";

export type CardProps = React.HTMLAttributes<HTMLDivElement> & {
  /** Surface step. Cards sit one step above their container. */
  level?: 1 | 2 | 3;
  /** Adds the raise shadow for floating panels. */
  raised?: boolean;
  /** Turns off the default padding. */
  flush?: boolean;
};

const LEVEL = { 1: "bg-bg-1", 2: "bg-bg-2", 3: "bg-bg-3" } as const;

export function Card({ level = 1, raised = false, flush = false, className, children, ...rest }: CardProps) {
  return (
    <div
      className={cx(
        "rounded-lg border border-line",
        LEVEL[level],
        raised && "shadow-raise",
        !flush && "p-5",
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}
