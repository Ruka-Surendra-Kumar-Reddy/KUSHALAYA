import { permanentRedirect } from "next/navigation";

/** Renamed "KushCare Discovery" — old links and printed QR codes land on the new page. */
export default function ParentCareCheckPage() {
  permanentRedirect("/kushcare-discovery");
}
