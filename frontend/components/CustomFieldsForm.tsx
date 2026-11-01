"use client";

import type { CustomFieldDef } from "@/lib/customFields";

type Props = {
  schema: CustomFieldDef[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
  title?: string;
};

export function CustomFieldsForm({
  schema,
  values,
  onChange,
  title = "Custom fields",
}: Props) {
  if (schema.length === 0) return null;

  const bySection = schema.reduce<Record<string, CustomFieldDef[]>>(
    (acc, f) => {
      const sec = f.section || "Custom";
      if (!acc[sec]) acc[sec] = [];
      acc[sec].push(f);
      return acc;
    },
    {},
  );

  return (
    <div className="form-section">
      <h3>{title}</h3>
      <p className="muted" style={{ marginBottom: "0.75rem" }}>
        Fields defined in Portal settings for your agency
      </p>
      {Object.entries(bySection).map(([section, fields]) => (
        <div key={section} style={{ marginBottom: "1rem" }}>
          {Object.keys(bySection).length > 1 && (
            <h4 style={{ margin: "0 0 0.5rem", fontSize: "0.95rem" }}>
              {section}
            </h4>
          )}
          <div className="grid-2">
            {fields.map((f) => (
              <div key={f.key}>
                <label>
                  {f.label}
                  {f.required ? " *" : ""}
                </label>
                {f.type === "textarea" ? (
                  <textarea
                    rows={3}
                    value={values[f.key] ?? ""}
                    onChange={(e) => onChange(f.key, e.target.value)}
                    required={f.required}
                  />
                ) : f.type === "select" && f.options ? (
                  <select
                    value={values[f.key] ?? ""}
                    onChange={(e) => onChange(f.key, e.target.value)}
                    required={f.required}
                  >
                    <option value="">—</option>
                    {f.options.map((o) => (
                      <option key={o} value={o}>
                        {o}
                      </option>
                    ))}
                  </select>
                ) : f.type === "boolean" ? (
                  <select
                    value={values[f.key] ?? "false"}
                    onChange={(e) => onChange(f.key, e.target.value)}
                  >
                    <option value="false">No</option>
                    <option value="true">Yes</option>
                  </select>
                ) : (
                  <input
                    type={
                      f.type === "number"
                        ? "number"
                        : f.type === "date"
                          ? "date"
                          : f.type === "email"
                            ? "email"
                            : f.type === "phone"
                              ? "tel"
                              : "text"
                    }
                    value={values[f.key] ?? ""}
                    onChange={(e) => onChange(f.key, e.target.value)}
                    required={f.required}
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
