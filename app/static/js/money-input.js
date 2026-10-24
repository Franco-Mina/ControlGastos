/* Live thousand separators for money inputs: 1234567.8 -> 1,234,567.80 */
(() => {
  const groupThousands = (digits) => digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",");

  // Keep digits, dots and commas. When the text comes from a paste, also accept
  // a decimal comma ("1.234,56" or "12,50"); typed commas are treated as
  // thousands separators so the formatter can place them automatically.
  const normalize = (raw, allowDecimalComma) => {
    const cleaned = raw.replace(/[^\d.,]/g, "");

    if (allowDecimalComma) {
      const lastDot = cleaned.lastIndexOf(".");
      const lastComma = cleaned.lastIndexOf(",");
      if (lastComma > lastDot) {
        const decimals = cleaned.slice(lastComma + 1);
        if (/^\d{1,2}$/.test(decimals)) {
          const whole = cleaned
            .slice(0, lastComma)
            .replace(/[.,]/g, "");
          return `${whole}.${decimals}`;
        }
      }
    }

    return cleaned.replace(/,/g, "");
  };

  const format = (raw, allowDecimalComma = false) => {
    const cleaned = normalize(raw, allowDecimalComma);
    const dot = cleaned.indexOf(".");

    if (dot === -1) {
      return groupThousands(cleaned.replace(/^0+(?=\d)/, ""));
    }

    const whole = cleaned.slice(0, dot).replace(/^0+(?=\d)/, "") || "0";
    const decimals = cleaned
      .slice(dot + 1)
      .replace(/\./g, "")
      .slice(0, 2);
    return `${groupThousands(whole)}.${decimals}`;
  };

  const restoreCaret = (input, raw, caret) => {
    if (caret >= raw.length) {
      input.setSelectionRange(input.value.length, input.value.length);
      return;
    }

    // Keep the caret after the same number of digits it was before formatting.
    const digits = raw.slice(0, caret).replace(/\D/g, "").length;
    let seen = 0;
    let position = 0;
    while (position < input.value.length && seen < digits) {
      if (/\d/.test(input.value[position])) seen += 1;
      position += 1;
    }
    input.setSelectionRange(position, position);
  };

  const onInput = (event) => {
    const input = event.currentTarget;
    const raw = input.value;
    const caret = input.selectionStart ?? raw.length;
    const formatted = format(raw, event.inputType === "insertFromPaste");

    if (formatted !== raw) {
      input.value = formatted;
    }
    restoreCaret(input, raw, caret);
  };

  document.querySelectorAll("[data-money-input]").forEach((input) => {
    input.addEventListener("input", onInput);
    if (/^[\d.,]+$/.test(input.value.trim())) {
      input.value = format(input.value, true);
    }
  });
})();
