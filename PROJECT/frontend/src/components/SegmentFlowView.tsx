import { useEffect, useMemo, useState } from "react";
import { useApp } from "../context/AppContext";
import { api } from "../services/api";
import type { HopOption, Segment } from "../types";
import "./SegmentFlowView.css";

const MODE_META: Record<string, { icon: string; color: string; label: string }> = {
  bus: { icon: "directions_bus", color: "#6c5ce7", label: "Bus" },
  metro: { icon: "subway", color: "#00cec9", label: "Metro" },
  train: { icon: "train", color: "#e17055", label: "Train" },
  walk: { icon: "directions_walk", color: "#95a5a6", label: "Walk" },
  ride: { icon: "local_taxi", color: "#f39c12", label: "Cab" },
};

function legColor(mode: string): string {
  return MODE_META[mode]?.color ?? "#6c5ce7";
}

export default function SegmentFlowView() {
  const { source, dest, journey, setJourney, setFlyTo } = useApp();
  const [segments, setSegments] = useState<Segment[]>(journey.segments?.segments ?? []);
  const [confirmed, setConfirmed] = useState<HopOption[]>(journey.chosenLegs as HopOption[]);
  const [loadingNext, setLoadingNext] = useState(false);
  const [complete, setComplete] = useState(journey.segments?.journeyComplete ?? false);
  const [selectedPerColumn, setSelectedPerColumn] = useState<Record<number, HopOption | null>>({});

  const loadInitial = async () => {
    if (!source || !dest) return;
    setLoadingNext(true);
    try {
      const r = await api.routeSegments(source, dest, 1, 500);
      setSegments(r.segments);
      setComplete(r.journeyComplete);
      setJourney({ segments: r });
    } finally {
      setLoadingNext(false);
    }
  };

  useEffect(() => {
    if (journey.segments?.segments?.length) {
      setSegments(journey.segments.segments);
    } else {
      loadInitial();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const connectFilter = (colIdx: number): Segment[] => {
    const prevSelected = selectedPerColumn[colIdx - 1];
    if (!prevSelected) return segments.slice(colIdx);
    const ds = prevSelected.destinationStop?.name?.toLowerCase();
    return segments.slice(colIdx).map((seg) => ({
      ...seg,
      options: seg.options.filter(
        (o) => !ds || !o.connectedFrom || o.connectedFrom.toLowerCase() === ds,
      ),
    }));
  };

  const confirmHop = async (colIdx: number, opt: HopOption) => {
    // selecting a hop resets all downstream selections (no ghost paths)
    const nextSel = { ...selectedPerColumn };
    for (const k of Object.keys(nextSel)) if (Number(k) > colIdx) delete nextSel[Number(k)];
    nextSel[colIdx] = opt;
    setSelectedPerColumn(nextSel);

    // confirm into breadcrumb
    const chosen = [...confirmed];
    while (chosen.length > colIdx) chosen.pop();
    chosen.push(opt);
    setConfirmed(chosen);

    if (opt.geometry?.length) {
      const lastPt = opt.geometry[opt.geometry.length - 1];
      setFlyTo({ lat: Number(lastPt[1]), lng: Number(lastPt[0]) });
    }

    // lazy fetch when reaching the final pre-fetched column
    if (colIdx >= segments.length - 1 && !complete) {
      setLoadingNext(true);
      try {
        const r = await api.segmentNext(journey.segments?.journey ?? {}, chosen, 1, 500);
        setSegments((prev) => [...prev, ...(r.segments ?? [])]);
        setComplete(r.journeyComplete);
        setJourney({ segments: r });
      } finally {
        setLoadingNext(false);
      }
    }
  };

  const visibleCols = useMemo(() => {
    const cols: { seg: Segment; idx: number }[] = [];
    for (let i = 0; i < segments.length; i++) {
      const filtered = connectFilter(i);
      if (i === 0 || filtered[0]?.options?.length) {
        cols.push({ seg: segments[i], idx: i });
      }
    }
    return cols;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [segments, selectedPerColumn]);

  const breadcrumb = useMemo(() => {
    const items: { label: string; mode?: string }[] = [];
    if (source) items.push({ label: source.name || "Source" });
    confirmed.forEach((c) => {
      items.push({ label: `${c.routeNumber ?? ""} ${c.mode ?? ""}`.trim(), mode: c.mode });
      items.push({ label: c.destinationStop?.name ?? "…" });
    });
    if (dest && !complete) items.push({ label: dest.name || "Destination", mode: "walk" });
    return items;
  }, [source, dest, confirmed, complete]);

  const totalTime = useMemo(() =>
    confirmed.reduce((a, c) => a + (c.durationMin ?? 0), 0),
    [confirmed]);
  const totalFare = useMemo(() =>
    confirmed.reduce((a, c) => a + (c.fare ?? 0), 0),
    [confirmed]);

  const reset = () => {
    setConfirmed([]);
    setSelectedPerColumn({});
    setSegments(journey.segments?.segments ?? []);
    setComplete(false);
  };

  return (
    <div className="flow-view">
      {journey.active && (
        <div className="live-banner glass-strong">
          <span className="row"><span className="pulse-dot" /> <b>Journey active</b></span>
        </div>
      )}

      <div className="breadcrumb glass">
        {breadcrumb.map((b, i) => (
          <span key={i} className="crumb row">
            <span className="crumb-dot" style={{ background: b.mode ? legColor(b.mode) : undefined }} />
            <span className={`truncate ${i % 2 === 1 ? "crumb-route" : ""}`}>{b.label}</span>
            {i < breadcrumb.length - 1 && <span className="muted">›</span>}
          </span>
        ))}
      </div>

      <div className="columns">
        {visibleCols.map(({ seg, idx }) => (
          <div key={idx} className="hop-col">
            <div className="col-head">
              Segment {idx + 1}
              <span className="muted small">({seg.options?.length ?? 0} options)</span>
            </div>
            <div className="hop-list">
              {seg.options?.map((opt, oi) => {
                const meta = MODE_META[opt.mode ?? ""] ?? MODE_META.bus;
                const selected = selectedPerColumn[idx]?.optionId === opt.optionId;
                const best = opt.isTopRecommended;
                return (
                  <button
                    key={opt.optionId || oi}
                    className={`hop-card glass hover-lift ${selected ? "selected" : ""} ${opt.mode === "walk" ? "walk" : ""}`}
                    style={{ borderLeftColor: meta.color }}
                    onClick={() => confirmHop(idx, opt)}
                    onMouseEnter={() => {
                      if (opt.geometry?.length) {
                        const lastPt = opt.geometry[opt.geometry.length - 1];
                        setFlyTo({ lat: Number(lastPt[1]), lng: Number(lastPt[0]) });
                      }
                    }}
                  >
                    <div className="spread">
                      <span className="row">
                        <span className="material-symbols-outlined" style={{ color: meta.color }}>{meta.icon}</span>
                        <b>{opt.mode === "walk" ? "Walk" : opt.routeNumber ?? meta.label}</b>
                      </span>
                      {best && <span className="badge gold">★ Top</span>}
                    </div>
                    <div className="small truncate mt4">
                      → {opt.destinationStop?.name}
                    </div>
                    <div className="spread mt8">
                      <span className="small">{opt.durationMin ?? "—"} min</span>
                      {opt.distanceKm != null && opt.distanceKm > 0 && (
                        <span className="small muted">{opt.distanceKm.toFixed(1)} km</span>
                      )}
                    </div>
                    <div className="spread">
                      {opt.departureTime && <span className="muted small">⏱ {opt.departureTime}</span>}
                      <span className="small">{opt.fare != null ? `₹${opt.fare}` : opt.mode === "walk" ? "Free" : "—"}</span>
                    </div>
                    {opt.transitOptionsFromThisStop != null && (
                      <div className="muted small mt4">↻ {opt.transitOptionsFromThisStop} onward options</div>
                    )}
                  </button>
                );
              })}
              {loadingNext && <div className="skeleton hop-skel" />}
            </div>
          </div>
        ))}
      </div>

      {complete ? (
        <div className="complete glass-strong anim-scale">
          <div className="row">
            <span className="material-symbols-outlined done">check_circle</span>
            <h3>You reached {dest?.name ?? "destination"}!</h3>
          </div>
          <div className="row mt8">
            <span className="stat"><b>{totalTime}</b> min</span>
            <span className="stat"><b>₹{totalFare}</b> total</span>
            <span className="stat"><b>{confirmed.length}</b> legs</span>
          </div>
          <button className="btn ghost mt12" onClick={reset}>Reset journey</button>
        </div>
      ) : (
        confirmed.length > 0 && (
          <button className="btn full mt8" onClick={() => setJourney({ active: true })}>
            <span className="material-symbols-outlined">navigation</span> Start journey
          </button>
        )
      )}
    </div>
  );
}
