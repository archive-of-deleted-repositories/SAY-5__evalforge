import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Nav } from "./components/Nav";
import { LiveFeed } from "./pages/LiveFeed";
import { PromptCompare } from "./pages/PromptCompare";
import { ReviewQueue } from "./pages/ReviewQueue";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false, refetchInterval: 5000 },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Nav />
        <Routes>
          <Route path="/" element={<LiveFeed />} />
          <Route path="/queue" element={<ReviewQueue />} />
          <Route path="/compare" element={<PromptCompare />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
