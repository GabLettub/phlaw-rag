import { Suspense } from "react";

import AutomationPanel from "@/components/AutomationPanel";
import Chat from "@/components/Chat";

// Chat reads the ?ask= query parameter, which needs a Suspense boundary
// so the rest of the page can still be prerendered.
export default function Home() {
  return (
    <div className="flex flex-col gap-6">
      <Suspense fallback={null}>
        <Chat />
      </Suspense>
      <AutomationPanel />
    </div>
  );
}
