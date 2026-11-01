"use client";

import { useEffect, useMemo, useState } from "react";
import { Flash } from "@/components/Flash";
import { DEFAULT_SOLUTION_LIBRARY } from "@/lib/livewell/solution-defaults";
import { fetchAdminSolutions, saveAdminSolutions } from "@/lib/livewell/solutionApi";
import {
  newSolutionId,
  normalizeSolutionLibrary,
  resetLocalSolutionLibrary,
  type SafeHomeSolution,
  type SolutionLibrary,
} from "@/lib/livewell/solutions";
import {
  SOLUTION_PRIORITY_META,
  SOLUTION_PRIORITY_ORDER,
  type SolutionPriority,
} from "@/lib/livewell/solution-types";
import { useSafetyRubric } from "@/lib/livewell/useSafetyRubric";

function linesToList(text: string): string[] {
  return text
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

function listToLines(items: string[]): string {
  return items.join("\n");
}

export function SolutionsAdminEditor() {
  const rubric = useSafetyRubric();
  const rubricOptions = useMemo(
    () =>
      rubric.flatMap((cat) =>
        cat.items.map((item) => ({
          id: item.id,
          label: `${cat.title}: ${item.label}`,
        })),
      ),
    [rubric],
  );

  const [library, setLibrary] = useState<SolutionLibrary>(DEFAULT_SOLUTION_LIBRARY);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    fetchAdminSolutions()
      .then(setLibrary)
      .catch(() => setLibrary(DEFAULT_SOLUTION_LIBRARY))
      .finally(() => setLoading(false));
  }, []);

  const normalized = normalizeSolutionLibrary(library);

  function persist(next: SolutionLibrary) {
    setLibrary(normalizeSolutionLibrary(next));
  }

  async function saveLibrary() {
    setError("");
    try {
      const saved = await saveAdminSolutions(library);
      setLibrary(saved);
      setMessage("Solution library saved. Assessments will use these mappings.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    }
  }

  function resetLibrary() {
    if (!window.confirm("Reset solution library to factory defaults?")) return;
    const defaults = resetLocalSolutionLibrary();
    setLibrary(defaults);
    setMessage("Reset locally — click Save to push to server.");
  }

  function updateSolution(id: string, patch: Partial<SafeHomeSolution>) {
    persist({
      solutions: library.solutions.map((s) => (s.id === id ? { ...s, ...patch } : s)),
    });
  }

  function addSolution() {
    const section = "Custom";
    persist({
      solutions: [
        ...library.solutions,
        {
          id: newSolutionId(section),
          section,
          finding: "New finding",
          riskDescription: "",
          priority: "medium",
          recommendedSolutions: [],
          contractorType: "",
          productCategories: [],
          estimatedCost: "",
          installationTime: "",
          scoreImprovement: 2,
          maintenanceRequirement: "",
          futureUpgrades: "",
          rubricItemIds: [],
          sort_order: library.solutions.length + 1,
        },
      ],
    });
  }

  function removeSolution(id: string) {
    if (!window.confirm("Remove this solution?")) return;
    persist({ solutions: library.solutions.filter((s) => s.id !== id) });
  }

  function toggleRubricLink(solutionId: string, itemId: string) {
    const solution = library.solutions.find((s) => s.id === solutionId);
    if (!solution) return;
    const has = solution.rubricItemIds.includes(itemId);
    updateSolution(solutionId, {
      rubricItemIds: has
        ? solution.rubricItemIds.filter((x) => x !== itemId)
        : [...solution.rubricItemIds, itemId],
    });
  }

  if (loading) return <p className="muted">Loading solution library…</p>;

  const bySection = normalized.solutions.reduce<Record<string, SafeHomeSolution[]>>((acc, s) => {
    const key = s.section || "Other";
    acc[key] = acc[key] ?? [];
    acc[key].push(s);
    return acc;
  }, {});

  return (
    <div className="home-safety-solutions-admin">
      <Flash message={message} error={error} onClear={() => { setMessage(""); setError(""); }} />

      <p className="muted">
        Map assessment findings to corrective actions. When an assessor rates a linked checklist
        item <strong>Unsafe</strong> or <strong>Acceptable</strong>, the improvement plan includes
        this solution ({normalized.solutions.length} entries).
      </p>

      {Object.entries(bySection).map(([section, items]) => (
        <section key={section} className="card home-safety-solutions-section">
          <h2 style={{ marginTop: 0 }}>{section}</h2>
          {items.map((solution) => {
            const open = expandedId === solution.id;
            return (
              <article key={solution.id} className="home-safety-solution-card">
                <header className="home-safety-solution-card-head">
                  <button
                    type="button"
                    className="home-safety-solution-toggle"
                    onClick={() => setExpandedId(open ? null : solution.id)}
                  >
                    <strong>{solution.id}</strong>
                    <span>{solution.finding}</span>
                    <span
                      className={`home-safety-priority-pill home-safety-priority-${solution.priority}`}
                    >
                      {SOLUTION_PRIORITY_META[solution.priority].label}
                    </span>
                  </button>
                  <button
                    type="button"
                    className="secondary danger"
                    onClick={() => removeSolution(solution.id)}
                  >
                    Remove
                  </button>
                </header>

                {open && (
                  <div className="home-safety-solution-edit">
                    <div className="home-safety-field-row">
                      <label className="home-safety-field">
                        Solution ID
                        <input
                          value={solution.id}
                          onChange={(e) => updateSolution(solution.id, { id: e.target.value })}
                        />
                      </label>
                      <label className="home-safety-field">
                        Section
                        <input
                          value={solution.section}
                          onChange={(e) => updateSolution(solution.id, { section: e.target.value })}
                        />
                      </label>
                    </div>
                    <label className="home-safety-field">
                      Finding
                      <input
                        value={solution.finding}
                        onChange={(e) => updateSolution(solution.id, { finding: e.target.value })}
                      />
                    </label>
                    <label className="home-safety-field">
                      Risk description
                      <input
                        value={solution.riskDescription}
                        onChange={(e) =>
                          updateSolution(solution.id, { riskDescription: e.target.value })
                        }
                      />
                    </label>
                    <div className="home-safety-field-row">
                      <label className="home-safety-field">
                        Priority
                        <select
                          value={solution.priority}
                          onChange={(e) =>
                            updateSolution(solution.id, {
                              priority: e.target.value as SolutionPriority,
                            })
                          }
                        >
                          {SOLUTION_PRIORITY_ORDER.map((p) => (
                            <option key={p} value={p}>
                              {SOLUTION_PRIORITY_META[p].label} — {SOLUTION_PRIORITY_META[p].window}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="home-safety-field">
                        Score improvement (+)
                        <input
                          type="number"
                          min={0}
                          max={20}
                          value={solution.scoreImprovement}
                          onChange={(e) =>
                            updateSolution(solution.id, {
                              scoreImprovement: Number(e.target.value) || 0,
                            })
                          }
                        />
                      </label>
                    </div>
                    <label className="home-safety-field">
                      Recommended solutions (one per line)
                      <textarea
                        className="home-safety-notes"
                        rows={3}
                        value={listToLines(solution.recommendedSolutions)}
                        onChange={(e) =>
                          updateSolution(solution.id, {
                            recommendedSolutions: linesToList(e.target.value),
                          })
                        }
                      />
                    </label>
                    <div className="home-safety-field-row">
                      <label className="home-safety-field">
                        Contractor type
                        <input
                          value={solution.contractorType}
                          onChange={(e) =>
                            updateSolution(solution.id, { contractorType: e.target.value })
                          }
                        />
                      </label>
                      <label className="home-safety-field">
                        Estimated cost
                        <input
                          value={solution.estimatedCost}
                          onChange={(e) =>
                            updateSolution(solution.id, { estimatedCost: e.target.value })
                          }
                        />
                      </label>
                    </div>
                    <div className="home-safety-field-row">
                      <label className="home-safety-field">
                        Installation time
                        <input
                          value={solution.installationTime}
                          onChange={(e) =>
                            updateSolution(solution.id, { installationTime: e.target.value })
                          }
                        />
                      </label>
                      <label className="home-safety-field">
                        Product categories (one per line)
                        <textarea
                          className="home-safety-notes"
                          rows={2}
                          value={listToLines(solution.productCategories)}
                          onChange={(e) =>
                            updateSolution(solution.id, {
                              productCategories: linesToList(e.target.value),
                            })
                          }
                        />
                      </label>
                    </div>
                    <fieldset className="home-safety-profile-fieldset">
                      <legend>Linked checklist items</legend>
                      <p className="muted home-safety-section-hint">
                        Triggers when rated Unsafe or Acceptable.
                      </p>
                      <div className="home-safety-solution-rubric-links">
                        {rubricOptions.map((opt) => (
                          <label key={opt.id} className="home-safety-solution-rubric-link">
                            <input
                              type="checkbox"
                              checked={solution.rubricItemIds.includes(opt.id)}
                              onChange={() => toggleRubricLink(solution.id, opt.id)}
                            />
                            <span>{opt.label}</span>
                          </label>
                        ))}
                      </div>
                    </fieldset>
                  </div>
                )}
              </article>
            );
          })}
        </section>
      ))}

      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "1rem" }}>
        <button type="button" className="secondary" onClick={addSolution}>
          + Add solution
        </button>
        <button type="button" className="primary" onClick={() => void saveLibrary()}>
          Save solution library
        </button>
        <button type="button" className="secondary" onClick={resetLibrary}>
          Reset to defaults
        </button>
      </div>
    </div>
  );
}
