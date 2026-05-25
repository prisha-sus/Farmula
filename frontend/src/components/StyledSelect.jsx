import React, { useState, useRef, useEffect } from "react";
import { ChevronDown, Check } from "lucide-react";

export default function StyledSelect({
  value,
  onChange,
  options,
  placeholder = "Select...",
  renderOption,
  renderValue,
  disabled = false,
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (ref.current && !ref.current.contains(event.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const selectedOption = options.find((option) => option.value === value);

  return (
    <div className={`styled-select ${disabled ? "disabled" : ""}`} ref={ref}>
      <button
        type="button"
        className={`styled-select-trigger ${open ? "open" : ""}`}
        onClick={() => !disabled && setOpen(!open)}
        disabled={disabled}
      >
        <span className="styled-select-value">
          {selectedOption
            ? renderValue
              ? renderValue(selectedOption)
              : selectedOption.label
            : placeholder}
        </span>
        <ChevronDown size={16} className={`chevron ${open ? "rotated" : ""}`} />
      </button>
      {open && (
        <div className="styled-select-menu">
          {options.map((option) => (
            <button
              type="button"
              key={option.value}
              className={`styled-select-option ${value === option.value ? "selected" : ""}`}
              onClick={() => {
                onChange(option.value);
                setOpen(false);
              }}
            >
              <span>{renderOption ? renderOption(option) : option.label}</span>
              {value === option.value && <Check size={14} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
