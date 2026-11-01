/**
 * Wording for an elder viewing their own record (relationship "self"): the
 * shared notices and catalogue copy are written for a relative ("Lakshmi's
 * alert band", "Lets your parent sit…"); the elder reads them about themself.
 */

import { useEffect, useState } from "react";
import { fetchFamilyDashboard } from "./familyApi";

function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Upper-cases "your"/"you" at the start of the text or a sentence. */
function capitaliseStarts(text: string): string {
  return text.replace(/(^|[.!?]\s+)(your|you)\b/g, (_m, lead: string, w: string) => lead + w.charAt(0).toUpperCase() + w.slice(1));
}

/**
 * "Lakshmi's alert band hasn't checked in" -> "Your alert band hasn't checked in";
 * "Lets your parent sit while bathing" -> "Lets you sit while bathing".
 * Text is unchanged when `isSelf` is false.
 */
export function forSelf(text: string, elderName: string | null | undefined, isSelf = true): string {
  if (!isSelf || !text) return text;
  let out = text;
  const full = (elderName || "").trim();
  const names = [full, full.split(/\s+/)[0]].filter((n, i, all) => n && all.indexOf(n) === i);
  for (const n of names) {
    out = out.replace(new RegExp(`\\b${escapeRe(n)}(?:['’]s|['’])(?=\\s)`, "g"), "your");
  }
  out = out.replace(/\byour parent['’]s\b/gi, "your").replace(/\byour parent\b/gi, "you");
  return capitaliseStarts(out);
}

/** Is the signed-in person the elder? (From the deduped dashboard call.) */
export function useFamilySelf(): { isSelf: boolean; elderName: string } {
  const [state, setState] = useState({ isSelf: false, elderName: "" });
  useEffect(() => {
    let live = true;
    fetchFamilyDashboard()
      .then((d) => {
        if (live) setState({ isSelf: !!d.viewer_is_elder, elderName: d.senior_name || "" });
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);
  return state;
}
