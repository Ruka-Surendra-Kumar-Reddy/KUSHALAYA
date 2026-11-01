import PartnerResponse from "./PartnerResponse";

export const metadata = {
  title: "Emergency hand-off",
  referrer: "no-referrer" as const,
  robots: { index: false, follow: false },
};

/** Public page for an emergency partner (ambulance / hospital). The link in their email is the key. */
export default function EmergencyResponsePage({ params }: { params: { id: string; token: string } }) {
  return <PartnerResponse incidentId={params.id} token={params.token} />;
}
