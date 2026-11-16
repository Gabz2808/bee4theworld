"use client";
import { useI18n } from "../i18n/provider";

// Selector de mes en el idioma del sitio. <input type="month"> usa el idioma del navegador,
// así que se reemplaza por dos selects. El valor sigue siendo "YYYY-MM", igual que espera la API.
type Props = {
  id: string;
  legend: string;
  value: string;
  min?: string;
  max?: string;
  invalid?: boolean;
  disabled?: boolean;
  onChange: (value: string) => void;
};

const pad = (n: number) => String(n).padStart(2, "0");

export function MonthField({ id, legend, value, min, max, invalid, disabled, onChange }: Props) {
  const { t } = useI18n();
  const monthName = new Intl.DateTimeFormat(t.numberLocale, { month: "long", timeZone: "UTC" });
  const [year, month] = value ? value.split("-").map(Number) : [NaN, NaN];
  const minYear = min ? Number(min.slice(0, 4)) : year;
  const maxYear = max ? Number(max.slice(0, 4)) : year;
  const years = Number.isFinite(minYear) && Number.isFinite(maxYear) ? Array.from({ length: maxYear - minYear + 1 }, (_, i) => minYear + i) : [];
  // Solo los meses dentro del rango disponible para el año elegido.
  const monthsFor = (y: number) => Array.from({ length: 12 }, (_, i) => i + 1).filter((m) => {
    const candidate = `${y}-${pad(m)}`;
    return (!min || candidate >= min) && (!max || candidate <= max);
  });
  const label = (m: number) => {
    const name = monthName.format(new Date(Date.UTC(2000, m - 1, 1)));
    return name.charAt(0).toUpperCase() + name.slice(1);
  };
  const changeYear = (y: number) => {
    const allowed = monthsFor(y);
    onChange(`${y}-${pad(allowed.includes(month) ? month : allowed[allowed.length - 1] ?? 1)}`);
  };
  const describedBy = invalid ? "period-error" : undefined;

  return <fieldset id={id} className="month-field" data-min={min} data-max={max} aria-describedby={describedBy}>
    <legend>{legend}</legend>
    <div className="month-field-row">
      <label className="sr-only" htmlFor={`${id}-month`}>{`${legend}: ${t.explorer.month}`}</label>
      <select id={`${id}-month`} value={value ? String(month) : ""} disabled={disabled || !value} aria-invalid={invalid} aria-describedby={describedBy} required onChange={(e) => onChange(`${year}-${pad(Number(e.target.value))}`)}>
        {!value && <option value="" />}
        {value && monthsFor(year).map((m) => <option key={m} value={m}>{label(m)}</option>)}
      </select>
      <label className="sr-only" htmlFor={`${id}-year`}>{`${legend}: ${t.explorer.year}`}</label>
      <select id={`${id}-year`} value={value ? String(year) : ""} disabled={disabled || !value} aria-invalid={invalid} aria-describedby={describedBy} required onChange={(e) => changeYear(Number(e.target.value))}>
        {!value && <option value="" />}
        {value && years.map((y) => <option key={y} value={y}>{y}</option>)}
      </select>
    </div>
  </fieldset>;
}
