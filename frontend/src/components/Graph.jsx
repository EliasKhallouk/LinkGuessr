import { useEffect, useRef, useState } from "react";
import { DataSet, Network } from "vis-network/standalone";
import { apiUrl } from "../config";

// Graph: can fetch the full graph from backend when no props are provided,
// or render a supplied graph via `nodesData`/`edgesData` props (used by Game.jsx)
export default function Graph({ nodesData = null, edgesData = null, height = "480px", title = "Graphe des relations" }) {
  const [nodes, setNodes] = useState(nodesData || []);
  const [edges, setEdges] = useState(edgesData || []);
  const [loading, setLoading] = useState(!nodesData || !edgesData);
  const networkRef = useRef(null);
  const networkInstance = useRef(null);

  useEffect(() => {
    let cancelled = false;

    const build = (nodesArr, edgesArr) => {
      setNodes(nodesArr || []);
      setEdges(edgesArr || []);

      if (!networkRef.current) return;

      // cleanup previous instance
      if (networkInstance.current) {
        try {
          networkInstance.current.destroy();
        } catch (e) {
          // ignore
        }
        networkInstance.current = null;
      }

      // vis-network dessine sur un canvas : on lit les couleurs du thème au moment du rendu.
      const css = getComputedStyle(document.documentElement);
      const color = (name) => css.getPropertyValue(name).trim();
      const visNodes = new DataSet(nodesArr || []);
      const visEdges = new DataSet(edgesArr || []);

      networkInstance.current = new Network(
        networkRef.current,
        { nodes: visNodes, edges: visEdges },
        {
          physics: { stabilization: true },
          interaction: { hover: true, multiselect: false },
          nodes: {
            shape: "dot",
            size: 14,
            font: { color: color("--text-primary"), size: 14 },
            borderWidth: 1.5,
          },
          edges: {
            color: { color: color("--text-muted"), highlight: color("--accent-primary") },
            width: 1.5,
            smooth: true,
          },
        }
      );

      networkInstance.current.on("click", (params) => {
        if (params.nodes && params.nodes.length > 0) {
          const nodeId = params.nodes[0];
          const nodeData = visNodes.get(nodeId);
          alert(`Vous avez cliqué sur : ${nodeData.label || nodeData.id}`);
        }
      });
    };

    if (nodesData && edgesData) {
      // render supplied graph
      build(nodesData, edgesData);
      setLoading(false);
    } else {
      // fetch full graph from backend
      setLoading(true);
      fetch(apiUrl("/graph"))
        .then((res) => res.json())
        .then((data) => {
          if (cancelled) return;
          build(data.nodes || [], data.edges || []);
        })
        .catch(() => {})
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }

    return () => {
      cancelled = true;
      if (networkInstance.current) {
        try {
          networkInstance.current.destroy();
        } catch (e) {}
        networkInstance.current = null;
      }
    };
  }, [nodesData, edgesData]);

  return (
    <section className="panel fade-in">
      <div className="panel-header">
        <span className="panel-title">{title}</span>
        <span className="kpi">{`Nœuds\u00A0: ${nodes.length} · Liens\u00A0: ${edges.length}`}</span>
      </div>
      <div className="panel-body" style={{ padding: 0 }}>
        {loading ? (
          <div style={{ padding: 16 }} className="muted">Chargement du graphe…</div>
        ) : (
          <div
            ref={networkRef}
            style={{
              height: height,
              marginBottom: "8px",
              background: "var(--bg-base)",
              borderRadius: "12px",
              marginTop: "8px",
            }}
          />
        )}
      </div>
    </section>
  );
}
