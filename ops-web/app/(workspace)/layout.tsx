import { RequireAuth } from "@/components/RequireAuth";
import { Shell } from "@/components/Shell";

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <Shell>{children}</Shell>
    </RequireAuth>
  );
}
