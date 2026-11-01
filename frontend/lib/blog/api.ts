/** Blog API — backend app/api/v1/blog.py. Admin calls need a signed-in admin; public ones need nothing. */
import { api, postFormData } from "@/lib/api";

export type BlogStatus = "draft" | "published" | "scheduled";
export type BlogFaq = { q: string; a: string };

export type BlogCard = {
  id: number;
  slug: string;
  title: string;
  excerpt: string;
  cover_image_url: string;
  cover_image_alt: string;
  tags: string[];
  author_name: string;
  published_at: string | null;
  updated_at: string | null;
  reading_minutes: number;
};

export type BlogPublicPost = BlogCard & {
  body_md: string;
  seo_title: string;
  og_image_url: string;
  canonical_url: string;
  faq: BlogFaq[];
  related?: BlogCard[];
};

export type BlogAdminPost = BlogPublicPost & {
  status: BlogStatus;
  publish_at: string | null;
  created_at: string | null;
  live: boolean;
};

export type BlogList = {
  items: BlogCard[];
  total: number;
  page: number;
  pages: number;
  per_page: number;
  tag: string | null;
  tags: string[];
};

export type BlogInput = Partial<
  Pick<
    BlogAdminPost,
    | "title"
    | "slug"
    | "excerpt"
    | "body_md"
    | "cover_image_url"
    | "cover_image_alt"
    | "tags"
    | "author_name"
    | "status"
    | "publish_at"
    | "seo_title"
    | "og_image_url"
    | "canonical_url"
    | "faq"
  >
>;

export const listBlogPosts = () => api<BlogAdminPost[]>("/api/v1/blog/posts");
export const getBlogPost = (id: number) => api<BlogAdminPost>(`/api/v1/blog/posts/${id}`);
export const saveBlogPost = (id: number | null, body: BlogInput) =>
  api<BlogAdminPost>(id ? `/api/v1/blog/posts/${id}` : "/api/v1/blog/posts", {
    method: id ? "PUT" : "POST",
    body: JSON.stringify(body),
  });
export const deleteBlogPost = (id: number) => api(`/api/v1/blog/posts/${id}`, { method: "DELETE" });

export function uploadBlogImage(file: File, alt: string) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("alt", alt);
  return postFormData<{ id: number; url: string; alt: string }>("/api/v1/blog/images", fd);
}
