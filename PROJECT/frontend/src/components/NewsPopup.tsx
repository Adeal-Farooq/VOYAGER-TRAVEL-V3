import { useEffect, useState } from "react";
import { useApp } from "../context/AppContext";
import { api } from "../services/api";
import "./NewsPopup.css";

const CAT_COLOR: Record<string, string> = {
  traffic: "#e74c3c", weather: "#3498db", event: "#f1c40f", general: "#95a5a6",
};

export default function NewsPopup() {
  const { userLoc, news, setNews } = useApp();
  const [open, setOpen] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (dismissed) return;
    const poll = async () => {
      try {
        const items = await api.news(userLoc?.lat, userLoc?.lng, "", 15);
        setNews(items.slice(0, 15));
      } catch { /* keep last-good cache */ }
    };
    poll();
    const id = setInterval(poll, 2 * 60 * 1000); // 2-min poll
    return () => clearInterval(id);
  }, [userLoc, setNews, dismissed]);

  if (dismissed) return null;

  return (
    <div className={`news-popup glass-strong ${open ? "open" : ""}`}>
      <div className="news-head" onClick={() => setOpen(!open)}>
        <span className="row">
          <span className="pulse-dot" /> <b>LIVE</b>
          <span className="muted small">News</span>
        </span>
        <button className="close" onClick={(e) => { e.stopPropagation(); setDismissed(true); }}>×</button>
      </div>
      {open && (
        <div className="news-list anim-in">
          {news.length === 0 && <div className="muted small">No news items yet.</div>}
          {news.map((n, i) => (
            <div key={i} className="news-item" style={{ borderLeftColor: CAT_COLOR[n.category ?? "general"] ?? "#95a5a6" }}>
              <b className="small">{n.title}</b>
              {n.summary && <div className="muted small">{n.summary}</div>}
              <span className="badge" style={{ background: "transparent", color: CAT_COLOR[n.category ?? "general"] }}>
                {n.category ?? "general"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
