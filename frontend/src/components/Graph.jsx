import { useEffect, useRef, useState } from "react";
import { DataSet, Network } from "vis-network/standalone";

export default function Graph() {
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [loading, setLoading] = useState(true);
  const networkRef = useRef(null); // ✅ référence vers le conteneur

  useEffect(() => {
    // récupérer le graphe depuis le back-end
    fetch("http://127.0.0.1:8000/graph")
      .then(res => res.json())
      .then(data => {
        setNodes(data.nodes);
        setEdges(data.edges);

        // ✅ attendre que le DOM soit prêt
        if (networkRef.current) {
          const visNodes = new DataSet(data.nodes);
          const visEdges = new DataSet(data.edges);

          const network = new Network(
            networkRef.current,
            { nodes: visNodes, edges: visEdges },
            {
              physics: { stabilization: true },
              interaction: { hover: true },
              nodes: {
                shape: "dot",
                size: 14,
                font: { color: "#fff", size: 14 },
                borderWidth: 1.5,
              },
              edges: {
                color: { color: "#999", highlight: "#f00" },
                width: 1.5,
                smooth: true,
              },
            }
          );

          // ✅ interaction : clic sur un nœud
          network.on("click", (params) => {
            if (params.nodes.length > 0) {
              const nodeId = params.nodes[0];
              const nodeData = visNodes.get(nodeId);
              alert(`Vous avez cliqué sur : ${nodeData.label || nodeData.id}`);
            }
          });
        }
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <section className="panel fade-in">
      <div className="panel-header">
        <span className="panel-title">Graphe des relations</span>
        <span className="kpi">Nœuds: {nodes.length} · Liens: {edges.length}</span>
      </div>
      <div className="panel-body" style={{ padding: 0 }}>
        {loading ? (
          <div style={{ padding: 16 }} className="muted">Chargement du graphe…</div>
        ) : (
          <div
            ref={networkRef} // ✅ au lieu d’un id
            style={{
              height: "656px",
              marginBottom: "8px", 
              background: "#111",
              borderRadius: "12px",
              marginTop: "8px",
            }}
          />
        )}
      </div>
    </section>
  );
}
