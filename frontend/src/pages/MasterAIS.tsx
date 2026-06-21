import { useState, useEffect } from 'react';
import api from '../api/client';

interface CompanyRow {
  id: number;
  name: string;
  plan: string | null;
  billing_type: string | null;
  users: number;
  max_users: number | null;
  monthly_cost: number | null;
  records: number;
  last_activity: string | null;
  api_key: string;
}
interface Totals {
  companies: number;
  monthly_cost: number;
  active_subscriptions: number;
}

export default function MasterAIS() {
  const [rows, setRows] = useState<CompanyRow[]>([]);
  const [totals, setTotals] = useState<Totals | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/api/billing/overview/')
      .then((r) => { setRows(r.data.companies); setTotals(r.data.totals); })
      .catch(() => setError('Не удалось загрузить сводку'))
      .finally(() => setLoading(false));
  }, []);

  const fmt = (v: number | null) => (v != null ? `${v.toLocaleString('ru-RU')} ₸` : '—');
  const ago = (iso: string | null) => {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleString('ru-RU');
  };

  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Главная АИС</h2>
        <p className="text-sm text-gray-500 mt-0.5">Надсистема: компании, подписки, активность</p>
      </div>

      {error && <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-4 py-3 mb-4">{error}</div>}

      {/* Сводные карточки */}
      {totals && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <Card label="Компаний" value={String(totals.companies)} />
          <Card label="Активных подписок" value={String(totals.active_subscriptions)} />
          <Card label="Выручка/мес" value={fmt(totals.monthly_cost)} accent />
        </div>
      )}

      {loading ? (
        <div className="text-center text-gray-400 py-12">Загрузка...</div>
      ) : (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {['Компания', 'Пакет', 'Тариф', 'Польз./лимит', 'Стоимость/мес', 'Записей', 'Последняя активность'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-800">{c.name}</td>
                  <td className="px-4 py-3">
                    {c.plan ? <span className="px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full text-xs">{c.plan}</span>
                      : <span className="text-gray-400">нет</span>}
                  </td>
                  <td className="px-4 py-3 text-gray-600">{c.billing_type ?? '—'}</td>
                  <td className="px-4 py-3 text-gray-600">{c.users}/{c.max_users ?? '∞'}</td>
                  <td className="px-4 py-3 font-medium text-gray-800">{fmt(c.monthly_cost)}</td>
                  <td className="px-4 py-3 text-gray-600">{c.records}</td>
                  <td className="px-4 py-3 text-gray-500">{ago(c.last_activity)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Card({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className={`rounded-lg border p-4 ${accent ? 'bg-indigo-600 border-indigo-600 text-white' : 'bg-white border-gray-200'}`}>
      <p className={`text-xs uppercase tracking-wide ${accent ? 'text-indigo-200' : 'text-gray-500'}`}>{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
    </div>
  );
}
