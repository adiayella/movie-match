import { Route, Routes } from "react-router-dom";
import Home from "./pages/Home";
import CreateShare from "./pages/CreateShare";
import Join from "./pages/Join";
import Prefs from "./pages/Prefs";
import Waiting from "./pages/Waiting";
import Swipe from "./pages/Swipe";
import Match from "./pages/Match";
import FinalChoice from "./pages/FinalChoice";
import Rate from "./pages/Rate";

export default function App() {
  return (
    <div className="app-shell">
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/s/:sessionId/create" element={<CreateShare />} />
        <Route path="/s/:sessionId" element={<Join />} />
        <Route path="/s/:sessionId/prefs" element={<Prefs />} />
        <Route path="/s/:sessionId/waiting" element={<Waiting />} />
        <Route path="/s/:sessionId/swipe" element={<Swipe />} />
        <Route path="/s/:sessionId/match" element={<Match />} />
        <Route path="/s/:sessionId/final" element={<FinalChoice />} />
        <Route path="/s/:sessionId/rate" element={<Rate />} />
      </Routes>
    </div>
  );
}
