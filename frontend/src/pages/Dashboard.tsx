import { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts';
import api from '../api/client';
import type { AnalyticsOverview, AnalyticsOperator, AnalyticsCategory } from '../api/types';

const PIE_COLORS = ['#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#3b82f6'];

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      <p className="text-sm text-gray-500 mb-1">{label}</p>
      <p className="text-3xl font-bold text-gray-800">{value}</p>
    </div>
  );
}

export default function Dashboard() {
  const today = new Date().toISOString().slice(0, 10);
  const thirtyDaysAgo = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);

  const [from, setFrom] = useState(thirtyDaysAgo);
  const [to, setTo] = useState(today);

  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [operators, setOperators] = useState<AnalyticsOperator[]>([]);
  const [categories, setCategories] = useState<AnalyticsCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError('');
      try {
        const params = { from, to };
        const [overviewRes, operatorsRes, categoriesRes] = await Promise.all([
          api.get('/api/analytics/overview', { params }),
          api.get('/api/analytics/operators', { params }),
          api.get('/api/analytics/categories', { params }),
        ]);
        setOverview(overviewRes.data);
        setOperators(Array.isArray(operatorsRes.data) ? operatorsRes.data : operatorsRes.data.results ?? []);
        setCategories(Array.isArray(categoriesRes.data) ? categoriesRes.data : categoriesRes.data.results ?? []);
      } catch {
        setError('Failed to load analytics data');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [from, to]);

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Dashboard</h2>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600">From</label>
            <input type="date" value={from} onChange={(e) => setFrom(e.target.value)}
              className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600">To</label>
            <input type="date" value={to} onChange={(e) => setTo(e.target.value)}
              className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-4 py-3 mb-6">{error}</div>
      )}

      {loading ? (
        <div className="text-center text-gray-500 py-12">Loading analytics...</div>
      ) : (
        <>
          {/* Overview Cards */}
          {overview && (
            <div className="grid grid-cols-4 gap-4 mb-8">
              <StatCard label="Total Calls" value={overview.total_calls} />
              <StatCard label="Completed Calls" value={overview.done_calls} />
              <StatCard label="Avg Script Score" value={`${overview.avg_script_score ?? 0}%`} />
              <StatCard label="Categories" value={overview.categories_count ?? 0} />
            </div>
          )}

          <div className="grid grid-cols-2 gap-6 mb-8">
            {/* Calls per day */}
            {overview?.calls_per_day && overview.calls_per_day.length > 0 && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                <h3 className="text-base font-semibold text-gray-800 mb-4">Calls Per Day</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={overview.calls_per_day} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Categories Pie */}
            {categories.length > 0 && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                <h3 className="text-base font-semibold text-gray-800 mb-4">Categories Distribution</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie data={categories} dataKey="count" nameKey="category" cx="50%" cy="50%" outerRadius={90} label>
                      {categories.map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Operator Performance */}
          {operators.length > 0 && (
            <>
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-200">
                  <h3 className="text-base font-semibold text-gray-800">Operator Performance Table</h3>
                </div>
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Operator</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Total Calls</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Avg Script Score</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {operators.map((op) => (
                      <tr key={op.operator_id} className="hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-3 text-gray-800 font-medium">{op.username}</td>
                        <td className="px-4 py-3 text-gray-600">{op.total_calls}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <div className="flex-1 bg-gray-200 rounded-full h-2 max-w-24">
                              <div
                                className="bg-indigo-600 h-2 rounded-full"
                                style={{ width: `${Math.min(op.avg_script_score ?? 0, 100)}%` }}
                              />
                            </div>
                            <span className="text-gray-700 text-sm">{op.avg_script_score ?? 0}%</span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {!overview && !loading && (
            <div className="text-center text-gray-400 py-12">No data available for the selected period</div>
          )}
        </>
      )}
    </div>
  );
}
