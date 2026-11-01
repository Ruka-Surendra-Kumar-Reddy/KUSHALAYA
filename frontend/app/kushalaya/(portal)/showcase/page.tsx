"use client";

import { Suspense } from "react";
import HomeSafetyShowcasePage from "./ShowcaseContent";

export default function ShowcasePage() {
  return (
    <Suspense
      fallback={
        <div className="home-safety-app home-safety-loading">
          <p>Loading showcase…</p>
        </div>
      }
    >
      <HomeSafetyShowcasePage />
    </Suspense>
  );
}
