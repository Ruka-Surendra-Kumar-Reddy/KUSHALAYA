import { redirect } from "next/navigation";

/** Server redirect so `/` never hangs on "Loading…" when client JS fails to load. */
export default function Home() {
  redirect("/login");
}
