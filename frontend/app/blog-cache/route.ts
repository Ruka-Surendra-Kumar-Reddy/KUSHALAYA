import { revalidatePath, revalidateTag } from "next/cache";
import { NextResponse } from "next/server";

/**
 * POST /blog-cache — the ops Blog editor calls this after publish / unpublish /
 * delete so www /blog shows the change now instead of within 5 minutes (ISR).
 * Only drops cached copies of public pages (they refetch published posts from
 * the API), so it needs no sign-in and leaks nothing.
 */
export async function POST() {
  revalidateTag("blog");
  revalidatePath("/marketing/blog", "layout");
  revalidatePath("/sitemap.xml");
  return NextResponse.json({ ok: true });
}
