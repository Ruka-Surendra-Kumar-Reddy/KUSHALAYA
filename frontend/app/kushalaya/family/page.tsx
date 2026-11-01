import { redirect } from "next/navigation";

// Never prerender this: a static redirect() is a 307 WITH an HTML body and a
// year-long s-maxage, and that body (root shell + footer) is what browsers
// showed when a service worker handed it back instead of following it. The
// middleware answers "/" and "/kushalaya/family" before this page normally.
export const dynamic = "force-dynamic";

export default function FamilyRootPage() {
  redirect("/kushalaya/family/dashboard");
}
