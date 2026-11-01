import { redirect } from "next/navigation";

/**
 * The old stand-alone assessor home (its own shell, no Ops sidebar) looked like
 * leaving Ops. Old bookmarks, the installed assessor app (manifest start_url)
 * and the assessor pages' "Back" links land here, so send them to the same
 * list inside Ops.
 */
export default function HomeSafetyListPage() {
  redirect("/kushalaya/assessments");
}
