import Icon from "./Icon";

export default function Toast({ message, type = "success" }) {
  if (!message) return null;

  return (
    <div className={`toast toast-${type}`} role="status">
      <Icon name={type === "success" ? "check" : "info"} size={17} />
      <span>{message}</span>
    </div>
  );
}
