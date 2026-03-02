import { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import api from '../api/client';
import type { AnalyticsOverview, AnalyticsOperator } from '../api/types';

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      <p className="text-sm text-gray-500 mb-1">{label}</p>
      <p className="text-3xl font-bold text-gray-800">{value}</p>
    </div>
  );
}

export default function Analytics() {
  const today = new Date().toISOString().slice(0, 10);
  const MS_PER_DAY = 86_400_000;
  const sevenDaysAgo = new Date(Date.now() - 7 * MS_PER_DAY).toISOString().slice(0, 10);

  const [from, setFrom] = useState(sevenDaysAgo);
  const [to, setTo] = useState(today);

  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [operators, setOperators] = useState<AnalyticsOperator[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError('');
      try {
        const params = { from, to };
        const [overviewRes, operatorsRes] = await Promise.all([
          api.get('/api/analytics/overview', { params }),
          api.get('/api/analytics/operators', { params }),
        ]);
        setOverview(overviewRes.data);
        setOperators(Array.isArray(operatorsRes.data) ? operatorsRes.data : operatorsRes.data.results ?? []);
      } catch {
        setError('Не удалось загрузить данные аналитики');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [from, to]);

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Аналитика</h2>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600">С</label>
            <input type="date" value={from} onChange={(e) => setFrom(e.target.value)}
              className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600">По</label>
            <input type="date" value={to} onChange={(e) => setTo(e.target.value)}
              className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-4 py-3 mb-6">{error}</div>
      )}

      {loading ? (
        <div className="text-center text-gray-500 py-12">Загрузка...</div>
      ) : (
        <>
          {/* Overview Cards */}
          {overview && (
            <div className="grid grid-cols-3 gap-4 mb-8">
              <StatCard label="Всего звонков" value={overview.total_calls} />
              <StatCard label="Завершённых" value={overview.done_calls} />
              <StatCard label="Неудачных" value={overview.failed_calls} />
            </div>
          )}

          {/* Calls per day chart */}
          {overview && overview.calls_per_day.length > 0 && (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
              <h3 className="text-base font-semibold text-gray-800 mb-4">Звонки по дням</h3>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={overview.calls_per_day} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="count" name="Звонки" fill="#6366f1" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Operator table */}
          {operators.length > 0 && (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200">
                <h3 className="text-base font-semibold text-gray-800">Статистика по операторам</h3>
              </div>
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Оператор</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Всего</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Завершённых</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Неудачных</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Ср. длит. (сек)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {operators.map((op) => (
                    <tr key={op.operator_id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 text-gray-800 font-medium">{op.full_name || op.username}</td>
                      <td className="px-4 py-3 text-gray-600">{op.total_calls}</td>
                      <td className="px-4 py-3 text-gray-600">{op.done_calls}</td>
                      <td className="px-4 py-3 text-gray-600">{op.failed_calls}</td>
                      <td className="px-4 py-3 text-gray-600">
                        {op.avg_duration_sec != null
                          ? op.avg_duration_sec >= 60
                            ? `${Math.floor(op.avg_duration_sec / 60)}м ${op.avg_duration_sec % 60}с`
                            : `${op.avg_duration_sec}с`
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {!overview && !loading && (
            <div className="text-center text-gray-400 py-12">Нет данных за выбранный период</div>
          )}
        </>
      )}
    </div>
  );
}
