import { useEffect, useState } from "react";
import { DataSet, Network } from "vis-network/standalone";

export default function Graph() {
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);

  useEffect(() => {
    // récupérer le graphe depuis le back-end
    fetch("http://127.0.0.1:8000/graph")
      .then(res => res.json())
      .then(data => {
        setNodes(data.nodes);
        setEdges(data.edges);

        const container = document.getElementById("mynetwork");
        const visNodes = new DataSet(data.nodes);
        const visEdges = new DataSet(data.edges);

        const network = new Network(container, { nodes: visNodes, edges: visEdges }, {
          physics: { stabilization: true },
          interaction: { hover: true }
        });

        network.on("click", (params) => {
          if (params.nodes.length > 0) {
            alert("Vous avez cliqué sur : " + params.nodes[0]);
          }
        });
      });
  }, []);

  return <div id="mynetwork" style={{ height: "600px", border: "1px solid black" }} />;
}
