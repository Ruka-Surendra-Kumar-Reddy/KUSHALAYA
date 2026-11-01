import ResetPassword from "@/app/reset-password/ResetPassword";
import { publicBrandFamilyLabel } from "@/lib/public-brand";

export const metadata = { title: `Reset password · ${publicBrandFamilyLabel()}`, referrer: "no-referrer" as const };

/** family.kushalaya.com/reset-password (middleware rewrites it here). */
export default function FamilyResetPasswordPage() {
  return <ResetPassword />;
}
