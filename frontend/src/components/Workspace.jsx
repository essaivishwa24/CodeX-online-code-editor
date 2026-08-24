import { useRef, useState } from "react";
import { STORAGE_KEYS } from "../constants/languages";
import { readStorage, writeStorage } from "../utils/storage";

const MIN_SPLIT = 36;
const MAX_SPLIT = 76;
const DEFAULT_SPLIT = 61;

function initialSplit() {
  const saved = Number(readStorage(STORAGE_KEYS.split, DEFAULT_SPLIT));
  return Number.isFinite(saved) ? Math.min(MAX_SPLIT, Math.max(MIN_SPLIT, saved)) : DEFAULT_SPLIT;
}

export default function Workspace({ editor, results }) {
  const containerRef = useRef(null);
  const dragRef = useRef(null);
  const [split, setSplit] = useState(initialSplit);
  const [isDragging, setIsDragging] = useState(false);

  const setClampedSplit = (next) => {
    const clamped = Math.min(MAX_SPLIT, Math.max(MIN_SPLIT, next));
    setSplit(clamped);
    return clamped;
  };

  const updateFromPointer = (clientX) => {
    const bounds = containerRef.current?.getBoundingClientRect();
    if (!bounds?.width) return;
    setClampedSplit(((clientX - bounds.left) / bounds.width) * 100);
  };

  const finishDrag = (event) => {
    if (!dragRef.current) return;
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    dragRef.current = null;
    setIsDragging(false);
    writeStorage(STORAGE_KEYS.split, String(split));
  };

  const resizeWithKeyboard = (event) => {
    const direction = event.key === "ArrowLeft" ? -1 : event.key === "ArrowRight" ? 1 : 0;
    if (!direction) return;
    event.preventDefault();
    setSplit((current) => {
      const next = Math.min(MAX_SPLIT, Math.max(MIN_SPLIT, current + direction * 2));
      writeStorage(STORAGE_KEYS.split, String(next));
      return next;
    });
  };

  return (
    <div
      className={`workspace ${isDragging ? "workspace-resizing" : ""}`}
      ref={containerRef}
      style={{ "--editor-split": `${split}%` }}
    >
      <div className="workspace-editor">{editor}</div>
      <button
        aria-label="Resize editor and results panels"
        aria-orientation="vertical"
        aria-valuemax={MAX_SPLIT}
        aria-valuemin={MIN_SPLIT}
        aria-valuenow={Math.round(split)}
        className="resize-handle"
        onDoubleClick={() => {
          setSplit(DEFAULT_SPLIT);
          writeStorage(STORAGE_KEYS.split, String(DEFAULT_SPLIT));
        }}
        onKeyDown={resizeWithKeyboard}
        onLostPointerCapture={finishDrag}
        onPointerDown={(event) => {
          event.preventDefault();
          dragRef.current = event.pointerId;
          event.currentTarget.setPointerCapture(event.pointerId);
          setIsDragging(true);
          updateFromPointer(event.clientX);
        }}
        onPointerMove={(event) => {
          if (dragRef.current === event.pointerId) updateFromPointer(event.clientX);
        }}
        onPointerUp={finishDrag}
        role="separator"
        title="Drag to resize · Double-click to reset"
        type="button"
      >
        <span />
      </button>
      <div className="workspace-results">{results}</div>
    </div>
  );
}
