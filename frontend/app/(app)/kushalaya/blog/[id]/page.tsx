"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { BlogEditor } from "@/components/ops/BlogEditor";
import { isAdmin as isAdminUser } from "@/lib/roles";

/** /kushalaya/blog/new or /kushalaya/blog/<id> — admins only (the API refuses everyone else too). */
export default function BlogEditPage({ params }: { params: { id: string } }) {
  const isAdmin = isAdminUser();
  const router = useRouter();
  useEffect(() => {
    if (!isAdmin) router.replace("/unauthorized");
  }, [isAdmin, router]);
  if (!isAdmin) return null;
  const id = params.id === "new" ? null : Number(params.id);
  if (id !== null && !Number.isInteger(id)) return <p className="muted">Post not found.</p>;
  return <BlogEditor postId={id} />;
}
