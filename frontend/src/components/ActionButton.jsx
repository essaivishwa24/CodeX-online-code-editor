import Icon from "./Icon";

export default function ActionButton({
  icon,
  label,
  onClick,
  disabled = false,
  active = false,
  className = "",
  children,
}) {
  return (
    <button
      aria-label={label}
      className={`toolbar-button ${active ? "toolbar-button-active" : ""} ${className}`}
      disabled={disabled}
      onClick={onClick}
      title={label}
      type="button"
    >
      {icon ? <Icon name={icon} size={16} /> : null}
      {children}
    </button>
  );
}
