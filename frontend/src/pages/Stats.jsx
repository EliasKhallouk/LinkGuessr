import {
    ArcElement,
    BarElement,
    CategoryScale,
    Chart as ChartJS,
    Legend,
    LinearScale,
    Title,
    Tooltip,
} from 'chart.js';
import { useEffect, useState } from "react";
import { Bar, Pie } from 'react-chartjs-2';
import { apiUrl } from "../config";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
);

export default function Stats() {
  const [degreeData, setDegreeData] = useState(null);
  const [categoryData, setCategoryData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const [dRes, cRes] = await Promise.all([
          fetch(apiUrl('/degree_distribution')),
          fetch(apiUrl('/category_counts')),
        ]);
        if (!dRes.ok || !cRes.ok) throw new Error('api');
        const dJson = await dRes.json();
        const cJson = await cRes.json();
        if (!mounted) return;
        const deg = Array.isArray(dJson.results) ? dJson.results : [];
        const cat = Array.isArray(cJson.results) ? cJson.results : [];
        setDegreeData({
          labels: deg.map(r => r.degree.toString()),
          datasets: [
            {
              label: 'Number of persons',
              data: deg.map(r => r.persons),
              backgroundColor: 'rgba(75, 192, 192, 0.6)'
            }
          ]
        });
        setCategoryData({
          labels: cat.map(r => r.category || 'unknown'),
          datasets: [
            {
              label: 'Persons per category',
              data: cat.map(r => r.persons),
              backgroundColor: cat.map((_, i) => `hsl(${(i*45)%360} 70% 50%)`)
            }
          ]
        });
      } catch (e) {
        if (!mounted) return;
        setError('Impossible de charger les statistiques');
      } finally {
        if (!mounted) return;
        setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  if (loading) return <div className="panel"><div className="panel-body">Chargement...</div></div>;
  if (error) return <div className="panel"><div className="panel-body">{error}</div></div>;

  return (
    <div>
      <section className="panel fade-in">
        <div className="panel-header"><span className="panel-title">Statistiques</span></div>
        <div className="panel-body">
          <h3>Répartition des personnes par nombre de relations</h3>
          {degreeData && <Bar options={{ responsive: true, plugins: { legend: { display: false } } }} data={degreeData} />}
        </div>
      </section>

      <section className="panel fade-in" style={{ marginTop: 12 }}>
        <div className="panel-header"><span className="panel-title">Répartition par catégorie</span></div>
        <div className="panel-body">
          {categoryData && <Pie options={{ responsive: true }} data={categoryData} />}
        </div>
      </section>
    </div>
  );
}
